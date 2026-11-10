"""
Aurora Telegram Hoster Bot & Platform Core Handler.

Manages interactive onboarding, multi-user session creation, owner controls,
and userbot management commands.
"""

import time
import asyncio
import logging
import psutil
from datetime import datetime
from telethon import TelegramClient, Button, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    FloodWaitError,
)
from telethon.sessions import MemorySession, StringSession

from aurora.config import Config, sanitize_text
from aurora.core.session_manager import session_manager
from aurora.db.models import User, UserSession, BotGroup, GBanUser, BlockedUser, ApprovedGroupUser, AllowedUser, SudoUser
from aurora.db.session import db_session, init_db

LOGS = logging.getLogger("AuroraHosterBot")

user_login_states = {}
start_time = datetime.utcnow()
BLOCKED_USERS = {}
ALLOWED_USERS = {}
SUDO_USERS = {Config.OWNER_ID, str(Config.OWNER_ID)}
GBAN_LIST = {}
APPROVED_USERS_PER_GROUP = {}
BOT_GROUPS = {}
main_bot_client = None
gban_sync_lock = asyncio.Lock()


def is_owner(sender_id, username=None):
    """
    Returns True ONLY for the platform Owner.
    Only the Owner is allowed to add or remove Sudo Users / Admins.
    """
    if sender_id is not None:
        if sender_id == Config.OWNER_ID or str(sender_id) == str(Config.OWNER_ID):
            return True
        try:
            if int(sender_id) == int(Config.OWNER_ID):
                return True
        except Exception:
            pass
    if username and getattr(Config, "OWNER_USERNAME", None):
        u = username.lower().lstrip("@")
        o = Config.OWNER_USERNAME.lower().lstrip("@")
        if u == o:
            return True
    return False


def is_admin_or_owner(sender_id, username=None):
    """
    Returns True for Owner AND Sudo Admins.
    Owner and Admins have identical permissions for all moderation, broadcast, allow/block, and info commands.
    """
    if is_owner(sender_id, username):
        return True

    if sender_id is not None:
        if sender_id in SUDO_USERS or str(sender_id) in SUDO_USERS:
            return True
        try:
            if int(sender_id) in SUDO_USERS:
                return True
        except Exception:
            pass

    if username:
        u = username.lower().lstrip("@")
        if u in SUDO_USERS or f"@{u}" in SUDO_USERS:
            return True

    return False


def is_user_allowed_to_use(user_id, username=None):
    """
    Checks if a user is authorized to use or host the Aurora bot/userbot.
    Owners and Sudo Admins are always authorized.
    Normal users must be explicitly granted access via /allow.
    Blocked users are always denied.
    """
    u_id_str = str(user_id)
    u_name = (username or "").lower().lstrip("@")
    u_name_key = f"@{u_name}" if u_name else ""

    # Check Blocked Users first
    if (
        user_id in BLOCKED_USERS
        or u_id_str in BLOCKED_USERS
        or (u_name and u_name in BLOCKED_USERS)
        or (u_name_key and u_name_key in BLOCKED_USERS)
    ):
        return False

    # Owner & Sudo Admins are always allowed
    if is_admin_or_owner(user_id, username):
        return True

    # Allowed Users check
    if (
        user_id in ALLOWED_USERS
        or u_id_str in ALLOWED_USERS
        or (u_name and u_name in ALLOWED_USERS)
        or (u_name_key and u_name_key in ALLOWED_USERS)
    ):
        return True

    return False


def normalize_gban_target(target):
    """
    Normalizes a GBAN target string.
    Strips leading '@', whitespace, and converts to lowercase.
    Returns cleaned string e.g. 'not_your_type_0091' or '7814478731'.
    """
    if not target:
        return ""
    t_str = str(target).strip()
    if t_str.startswith("@"):
        t_str = t_str[1:]
    return t_str.lower()


RESERVED_GBAN_KEYWORDS = {"list", "gbanlist", "listgban", "help", "start", "cancel", "status", "stop"}


def load_persistent_data():
    """Loads persistent GBan, BlockedUsers, BotGroups, ApprovedGroupUsers, AllowedUsers, and SudoUsers from database."""
    try:
        init_db()
        with db_session() as session:
            # Load Bot Groups
            BOT_GROUPS.clear()
            for g in session.query(BotGroup).all():
                BOT_GROUPS[g.group_id] = g.title or "Group"

            # Load GBan Users (deduplicated & normalized)
            GBAN_LIST.clear()
            for gb in session.query(GBanUser).all():
                norm = normalize_gban_target(gb.target)
                if norm and norm not in RESERVED_GBAN_KEYWORDS:
                    GBAN_LIST[norm] = gb.reason

            # Load Blocked Users
            BLOCKED_USERS.clear()
            for bu in session.query(BlockedUser).all():
                info = {"id": bu.user_id, "username": bu.username or "N/A"}
                BLOCKED_USERS[bu.user_id] = info
                try:
                    BLOCKED_USERS[int(bu.user_id)] = info
                except Exception:
                    pass
                if bu.username:
                    b_clean = bu.username.lower().lstrip("@")
                    BLOCKED_USERS[bu.username.lower()] = info
                    BLOCKED_USERS[b_clean] = info
                    BLOCKED_USERS[f"@{b_clean}"] = info

            # Load Approved Group Users
            APPROVED_USERS_PER_GROUP.clear()
            for ap in session.query(ApprovedGroupUser).all():
                if ap.group_id not in APPROVED_USERS_PER_GROUP:
                    APPROVED_USERS_PER_GROUP[ap.group_id] = set()
                APPROVED_USERS_PER_GROUP[ap.group_id].add(ap.target.lower())

            # Load Allowed Users
            ALLOWED_USERS.clear()
            for al in session.query(AllowedUser).all():
                info = {"id": al.user_id, "username": al.username or "N/A"}
                ALLOWED_USERS[al.user_id] = info
                try:
                    ALLOWED_USERS[int(al.user_id)] = info
                except Exception:
                    pass
                if al.username:
                    a_clean = al.username.lower().lstrip("@")
                    ALLOWED_USERS[al.username.lower()] = info
                    ALLOWED_USERS[a_clean] = info
                    ALLOWED_USERS[f"@{a_clean}"] = info

            # Load Sudo Users (Admins)
            SUDO_USERS.clear()
            SUDO_USERS.add(Config.OWNER_ID)
            SUDO_USERS.add(str(Config.OWNER_ID))
            if getattr(Config, "OWNER_USERNAME", None):
                o_uname = Config.OWNER_USERNAME.lower().lstrip("@")
                SUDO_USERS.add(o_uname)
                SUDO_USERS.add(f"@{o_uname}")

            for su in session.query(SudoUser).all():
                SUDO_USERS.add(su.user_id)
                try:
                    SUDO_USERS.add(int(su.user_id))
                except Exception:
                    pass
                if su.username:
                    s_clean = su.username.lower().lstrip("@")
                    SUDO_USERS.add(su.username.lower())
                    SUDO_USERS.add(s_clean)
                    SUDO_USERS.add(f"@{s_clean}")

        LOGS.info(
            f"Loaded {len(BOT_GROUPS)} bot groups, {len(GBAN_LIST)} gban users, "
            f"{len(BLOCKED_USERS)} blocked users, {len(ALLOWED_USERS)} allowed users, "
            f"{len(SUDO_USERS)} sudo entries from DB."
        )
    except Exception as e:
        LOGS.error(f"Error loading persistent DB data: {e}")


def save_bot_group(group_id: int, title: str):
    """Saves or updates a group in DB and in-memory cache."""
    BOT_GROUPS[group_id] = title
    try:
        with db_session() as session:
            existing = session.query(BotGroup).filter(BotGroup.group_id == group_id).first()
            if not existing:
                session.add(BotGroup(group_id=group_id, title=title))
            else:
                existing.title = title
            session.commit()
    except Exception as e:
        LOGS.error(f"Error saving BotGroup {group_id}: {e}")


def remove_bot_group(group_id: int):
    """Removes a group from DB and in-memory cache."""
    BOT_GROUPS.pop(group_id, None)
    try:
        with db_session() as session:
            session.query(BotGroup).filter(BotGroup.group_id == group_id).delete(synchronize_session=False)
            session.commit()
    except Exception as e:
        LOGS.error(f"Error deleting BotGroup {group_id}: {e}")


async def check_group_eligibility(client, chat_id):
    """
    Verifies if chat_id is a supported group/supergroup and client is an admin with ban_users rights.
    Saves or removes from BOT_GROUPS DB accordingly.
    """
    if not client or not client.is_connected() or not chat_id:
        return False, "Group", chat_id

    try:
        chat = await client.get_entity(chat_id)
        is_group = getattr(chat, "group", False) or getattr(chat, "megagroup", False) or getattr(chat, "gigagroup", False)
        if not is_group and hasattr(chat, "title"):
            is_group = True

        if not is_group:
            remove_bot_group(chat_id)
            return False, getattr(chat, "title", "Group"), chat_id

        title = getattr(chat, "title", "Group") or "Group"
        is_admin = False

        if getattr(chat, "creator", False):
            is_admin = True
        elif getattr(chat, "admin_rights", None):
            ar = chat.admin_rights
            if getattr(ar, "ban_users", False) or getattr(ar, "change_info", False):
                is_admin = True
        else:
            try:
                p = await client.get_permissions(chat_id, "me")
                if getattr(p, "is_admin", False) or getattr(p, "is_creator", False) or getattr(p, "ban_users", False):
                    is_admin = True
            except Exception:
                pass

        if is_admin:
            save_bot_group(chat_id, title)
            return True, title, chat_id
        else:
            remove_bot_group(chat_id)
            return False, title, chat_id
    except Exception as e:
        LOGS.debug(f"Error checking group eligibility for {chat_id}: {e}")
        return False, "Group", chat_id


async def sync_new_group(client, group_id, group_title=None, notify_owner=True):
    """
    Synchronizes ALL existing GBAN users when a new eligible group is discovered/joined.
    Outputs structured log.
    """
    async with gban_sync_lock:
        is_elig, title, g_id = await check_group_eligibility(client, group_id)
        if not is_elig:
            return

        group_title = group_title or title or "Group"
        load_persistent_data()
        gban_targets = list(GBAN_LIST.keys())

        if not gban_targets:
            sync_log = (
                f"🛡️ **Global Ban Sync**\n\n"
                f"📍 **Group:** {group_title}\n"
                f"🆔 **ID:** `{g_id}`\n"
                f"👥 **Existing Global Bans:** `0`\n"
                f"ℹ️ *Nothing to synchronize.*"
            )
            LOGS.info(f"Global Ban Sync: Group {group_title} ({g_id}) - Nothing to synchronize.")
            return sync_log

        total = len(gban_targets)
        newly_banned = 0
        already_banned = 0
        failed = 0

        for target in gban_targets:
            t_key = str(target).lower()
            approved_set = APPROVED_USERS_PER_GROUP.get(g_id, set())
            if (
                t_key in approved_set or
                (t_key.startswith("@") and t_key[1:] in approved_set) or
                (f"@{t_key}" in approved_set)
            ):
                already_banned += 1
                continue

            success = await perform_group_ban(client, g_id, target)
            if success:
                newly_banned += 1
            else:
                failed += 1
            await asyncio.sleep(0.2)

        sync_log = (
            f"🛡️ **Global Ban Sync**\n\n"
            f"📍 **Group:** {group_title}\n"
            f"🆔 **ID:** `{g_id}`\n"
            f"👥 **Existing Global Bans:** `{total}`\n"
            f"🚫 **Newly Banned:** `{newly_banned}`\n"
            f"✅ **Already Banned:** `{already_banned}`\n"
            f"❌ **Failed:** `{failed}`"
        )
        LOGS.info(f"Global Ban Sync for {group_title} ({g_id}): Total={total}, Newly={newly_banned}, Already={already_banned}, Failed={failed}")

        if notify_owner and main_bot_client and Config.OWNER_ID:
            try:
                await main_bot_client.send_message(Config.OWNER_ID, sync_log)
            except Exception:
                pass

        return sync_log


async def reconcile_global_bans(client=None):
    """
    Reconciles all global bans across all currently eligible moderation groups.
    Runs on startup and as a periodic background task.
    """
    if not client:
        client = main_bot_client
    if not client or not client.is_connected():
        return

    async with gban_sync_lock:
        load_persistent_data()
        gban_targets = list(GBAN_LIST.keys())
        all_groups = await get_all_platform_groups(client)

        for g_id in list(BOT_GROUPS.keys()):
            if g_id not in all_groups:
                remove_bot_group(g_id)

        if not gban_targets or not all_groups:
            return

        for g_id, g_name in all_groups.items():
            for target in gban_targets:
                t_key = str(target).lower()
                approved_set = APPROVED_USERS_PER_GROUP.get(g_id, set())
                if (
                    t_key in approved_set or
                    (t_key.startswith("@") and t_key[1:] in approved_set) or
                    (f"@{t_key}" in approved_set)
                ):
                    continue

                await perform_group_ban(client, g_id, target)
                await asyncio.sleep(0.1)


async def refresh_bot_groups(client=None):
    """
    Refreshes group cache for bot/userbot safely.
    For userbots, queries Telegram dialogs.
    For bot account, relies on event-driven BOT_GROUPS tracking (as Telegram restricts bot get_dialogs).
    """
    if not client:
        client = main_bot_client
    if not client or not client.is_connected():
        return
    try:
        me = await client.get_me()
        if getattr(me, "bot", False):
            return
        
        dialogs = await client.get_dialogs()
        current_groups = {}
        for d in dialogs:
            if is_group_dialog(d):
                current_groups[d.id] = d.name
        return current_groups
    except Exception as e:
        LOGS.debug(f"Note refreshing bot groups: {e}")


async def get_all_platform_groups(bot=None):
    """
    Returns a dictionary of all groups {group_id: title} where:
    The Telegram Bot Account or active userbots have admin rights to manage/ban users.
    """
    if bot:
        await refresh_bot_groups(bot)
    elif main_bot_client:
        await refresh_bot_groups(main_bot_client)

    groups = {}
    load_persistent_data()

    # 1. Load Bot Account groups from BOT_GROUPS (saved via events & persistent DB)
    for g_id, name in BOT_GROUPS.items():
        groups[g_id] = name

    # 2. Add active Userbots' groups (only groups where userbot has admin rights or created group)
    for uid in session_manager.get_all_active_users():
        u_client = session_manager.get_active_client(uid)
        if u_client and u_client.is_connected():
            try:
                async for dialog in u_client.iter_dialogs():
                    if is_group_dialog(dialog):
                        is_admin = False
                        ent = getattr(dialog, "entity", None)
                        if ent:
                            if getattr(ent, "creator", False):
                                is_admin = True
                            elif getattr(ent, "admin_rights", None):
                                ar = ent.admin_rights
                                if getattr(ar, "ban_users", False) or getattr(ar, "change_info", False):
                                    is_admin = True
                            elif dialog.id in BOT_GROUPS:
                                is_admin = True
                        if is_admin:
                            groups[dialog.id] = dialog.name
            except Exception as e:
                LOGS.error(f"Error fetching userbot {uid} dialogs: {e}")

    return groups


def is_group_dialog(dialog):
    """
    Checks if a Telethon dialog is a group chat (regular group or supergroup).
    """
    return dialog.is_group or (dialog.is_channel and getattr(dialog.entity, "megagroup", False))


async def resolve_target(client, target):
    """
    Safely resolves user_id or username into an entity or integer ID.
    """
    if isinstance(target, int):
        return target
    target_str = str(target).strip()
    if target_str.isdigit() or (target_str.startswith("-") and target_str[1:].isdigit()):
        return int(target_str)
    try:
        entity = await client.get_entity(target_str)
        return entity
    except Exception:
        return target_str


async def execute_global_broadcast(msg_text, reply_msg=None, event=None):
    """
    Executes a global broadcast strictly via the Telegram Bot Account across all groups where the bot is present.
    """
    b_client = main_bot_client
    if not b_client or not b_client.is_connected():
        return "❌ **Telegram Bot Account is not connected.**"

    load_persistent_data()
    all_groups = list(BOT_GROUPS.keys())
    total_groups = len(all_groups)

    if total_groups == 0:
        return "ℹ️ **No active groups recorded where the bot is present.**"

    sent_bot = 0
    failed = 0

    for g_id in all_groups:
        try:
            if reply_msg:
                await b_client.send_message(g_id, reply_msg)
            else:
                await b_client.send_message(g_id, msg_text)
            sent_bot += 1
            await asyncio.sleep(0.35)
        except Exception as e:
            failed += 1
            LOGS.debug(f"Bot failed to broadcast to group {g_id}: {e}")

    res = (
        f"📢 **Global Broadcast Complete!**\n\n"
        f"🤖 **Sent by Bot Account in:** `{sent_bot}` groups\n"
        f"❌ **Failed in:** `{failed}` groups\n"
        f"📊 **Total Bot Groups:** `{total_groups}`"
    )
    return res


async def get_bot_admin_groups_list(bot=None):
    """
    Returns a formatted list of all groups where the Telegram Bot Account is present and has admin access.
    """
    b_client = bot or main_bot_client
    if not b_client or not b_client.is_connected():
        return "❌ **Telegram Bot Account is not connected.**"

    load_persistent_data()
    if not BOT_GROUPS:
        return "ℹ️ **No groups recorded where the bot is present.**"

    admin_groups = []
    for g_id in list(BOT_GROUPS.keys()):
        try:
            eligible, title, _ = await check_group_eligibility(b_client, g_id)
            if eligible:
                admin_groups.append((g_id, title))
        except Exception as e:
            LOGS.debug(f"Error checking admin status for {g_id}: {e}")

    if not admin_groups:
        return "ℹ️ **The bot is not an admin in any group currently.**"

    res = f"🛡️ **Bot Admin Groups List (`{len(admin_groups)}` groups):**\n\n"
    for g_id, g_name in admin_groups:
        res += f"• **{g_name}** (ID: `{g_id}`)\n"

    if len(res) > 3900:
        res = res[:3900] + "\n\n...[List Truncated]"
    return res


async def perform_group_ban(client, group_id, raw_target, resolved_entity=None, numeric_id=None, norm_username=None):
    """
    Attempts to ban a target in group_id using client (bot or userbot).
    """
    target_to_use = resolved_entity or (numeric_id if numeric_id else raw_target)
    
    try:
        await client.edit_permissions(group_id, target_to_use, view_messages=False)
        return True
    except Exception:
        try:
            await client.kick_participant(group_id, target_to_use)
            return True
        except Exception:
            pass

    if numeric_id or norm_username:
        try:
            search_query = str(numeric_id) if numeric_id else norm_username
            participants = await client.get_participants(group_id, search=search_query)
            for p in participants:
                if (numeric_id and p.id == numeric_id) or (norm_username and p.username and p.username.lower() == norm_username):
                    try:
                        await client.edit_permissions(group_id, p, view_messages=False)
                        return True
                    except Exception:
                        try:
                            await client.kick_participant(group_id, p)
                            return True
                        except Exception:
                            pass
        except Exception:
            pass

    return False


async def perform_group_unban(client, group_id, raw_target, resolved_entity=None, numeric_id=None, norm_username=None):
    """
    Attempts to unban a target in group_id using client (bot or userbot).
    """
    target_to_use = resolved_entity or (numeric_id if numeric_id else raw_target)
    
    try:
        await client.edit_permissions(group_id, target_to_use, view_messages=True, send_messages=True)
        return True
    except Exception:
        if numeric_id or norm_username:
            try:
                search_query = str(numeric_id) if numeric_id else norm_username
                participants = await client.get_participants(group_id, search=search_query)
                for p in participants:
                    if (numeric_id and p.id == numeric_id) or (norm_username and p.username and p.username.lower() == norm_username):
                        try:
                            await client.edit_permissions(group_id, p, view_messages=True, send_messages=True)
                            return True
                        except Exception:
                            pass
            except Exception:
                pass

    return False


async def resolve_gban_event_target(client, event, input_str):
    """
    Extracts target string, target entity, and ban reason from event and input_str.
    Handles:
    - Reply to a message in group or DM (with or without optional reason)
    - Explicit @username or user_id argument (with optional reason)
    - DM chat partner if command typed in DM without reply and without target argument
    """
    reply = await event.get_reply_message()
    target_str = None
    target_entity = None
    reason = "Globally Banned by Admin"

    if reply:
        try:
            target_entity = await reply.get_sender()
        except Exception:
            pass

        if input_str:
            parts = input_str.strip().split(maxsplit=1)
            first = parts[0]
            if first.startswith("@") or first.lstrip("-").isdigit():
                target_str = first
                target_entity = None
                if len(parts) > 1:
                    reason = parts[1]
            else:
                target_str = str(reply.sender_id) if reply.sender_id else (str(getattr(target_entity, "id", "")) if target_entity else None)
                reason = input_str.strip()
        else:
            target_str = str(reply.sender_id) if reply.sender_id else (str(getattr(target_entity, "id", "")) if target_entity else None)
    elif input_str:
        parts = input_str.strip().split(maxsplit=1)
        target_str = parts[0]
        if len(parts) > 1:
            reason = parts[1]
    elif getattr(event, "is_private", False):
        try:
            target_entity = await event.get_chat()
            if target_entity:
                target_str = str(target_entity.id)
        except Exception:
            target_str = str(event.chat_id)

    if not target_entity and target_str and client:
        try:
            from aurora.plugins.utility import get_user_entity_robust
            target_entity = await get_user_entity_robust(client, target_str)
        except Exception:
            pass

    return target_str, target_entity, reason


async def resolve_gunban_event_target(client, event, input_str):
    """
    Extracts target string and target entity for GUNBAN.
    """
    reply = await event.get_reply_message()
    target_str = None
    target_entity = None

    if reply:
        try:
            target_entity = await reply.get_sender()
        except Exception:
            pass

        if input_str:
            first = input_str.strip().split()[0]
            if first.startswith("@") or first.lstrip("-").isdigit():
                target_str = first
                target_entity = None
            else:
                target_str = str(reply.sender_id) if reply.sender_id else (str(getattr(target_entity, "id", "")) if target_entity else None)
        else:
            target_str = str(reply.sender_id) if reply.sender_id else (str(getattr(target_entity, "id", "")) if target_entity else None)
    elif input_str:
        target_str = input_str.strip().split()[0]
    elif getattr(event, "is_private", False):
        try:
            target_entity = await event.get_chat()
            if target_entity:
                target_str = str(target_entity.id)
        except Exception:
            target_str = str(event.chat_id)

    if not target_entity and target_str and client:
        try:
            from aurora.plugins.utility import get_user_entity_robust
            target_entity = await get_user_entity_robust(client, target_str)
        except Exception:
            pass

    return target_str, target_entity


async def execute_global_ban(raw_target, target_entity=None, reason="Globally Banned by Admin"):
    """
    Executes a Global Ban across ALL platform groups.
    Supports user IDs, @usernames, target entities, and un-prefixed usernames.
    """
    async with gban_sync_lock:
        if hasattr(raw_target, "id"):
            target_entity = raw_target
            raw_target = str(raw_target.id)

        raw_target_str = str(raw_target).strip()
        t_norm = normalize_gban_target(raw_target_str)
        if not t_norm or t_norm in RESERVED_GBAN_KEYWORDS:
            return "❌ **Invalid target.** Specify a valid @username or user ID to GBAN."

    all_groups = await get_all_platform_groups(main_bot_client)
    total_groups = len(all_groups)

    b_client = main_bot_client

    # Resolve target details
    resolved_entity = target_entity
    numeric_id = int(t_norm) if t_norm.lstrip("-").isdigit() else None
    norm_username = raw_target_str[1:].lower() if raw_target_str.startswith("@") else (t_norm.lower() if not t_norm.lstrip("-").isdigit() else None)

    if resolved_entity:
        if hasattr(resolved_entity, "id"):
            numeric_id = resolved_entity.id
        if hasattr(resolved_entity, "username") and resolved_entity.username:
            norm_username = resolved_entity.username.lower()

    if not norm_username and b_client and b_client.is_connected():
        try:
            from aurora.plugins.utility import get_user_entity_robust
            ent = await get_user_entity_robust(b_client, raw_target_str)
            if ent:
                resolved_entity = ent
                if hasattr(ent, "id"):
                    numeric_id = ent.id
                if hasattr(ent, "username") and ent.username:
                    norm_username = ent.username.lower()
        except Exception:
            pass

    # Record in GBAN_LIST (save both username and ID if available)
    if t_norm:
        GBAN_LIST[t_norm] = reason
    if norm_username:
        GBAN_LIST[norm_username] = reason
        GBAN_LIST[f"@{norm_username}"] = reason
    if numeric_id:
        GBAN_LIST[str(numeric_id)] = reason

    # Persist in DB
    try:
        with db_session() as session:
            existing = session.query(GBanUser).filter(GBanUser.target == t_norm).first()
            if not existing:
                session.add(GBanUser(target=t_norm, reason=reason))
            else:
                existing.reason = reason
            if numeric_id and str(numeric_id) != t_norm:
                existing_id = session.query(GBanUser).filter(GBanUser.target == str(numeric_id)).first()
                if not existing_id:
                    session.add(GBanUser(target=str(numeric_id), reason=reason))
            session.commit()
    except Exception as e:
        LOGS.error(f"Error persisting GBanUser: {e}")

    banned_bot = 0
    banned_ub = 0
    banned_groups = set()

    # 1. Ban via Bot Account
    if b_client and b_client.is_connected():
        load_persistent_data()
        for g_id in list(BOT_GROUPS.keys()):
            success = await perform_group_ban(b_client, g_id, raw_target_str, resolved_entity, numeric_id, norm_username)
            if success:
                banned_bot += 1
                banned_groups.add(g_id)

    # 2. Ban via Active Hosted Userbots
    active_users = session_manager.get_all_active_users()
    for uid in active_users:
        u_client = session_manager.get_active_client(uid)
        if u_client and u_client.is_connected():
            try:
                ub_entity = resolved_entity
                if not ub_entity:
                    try:
                        from aurora.plugins.utility import get_user_entity_robust
                        ub_entity = await get_user_entity_robust(u_client, raw_target_str)
                    except Exception:
                        pass

                async for dialog in u_client.iter_dialogs():
                    if is_group_dialog(dialog) and dialog.id in all_groups and dialog.id not in banned_groups:
                        g_id = dialog.id
                        success = await perform_group_ban(u_client, g_id, raw_target_str, ub_entity, numeric_id, norm_username)
                        if success:
                            banned_ub += 1
                            banned_groups.add(g_id)
            except Exception as e:
                LOGS.error(f"Error executing userbot GBAN for {uid}: {e}")

    total_banned = len(banned_groups)
    failed = max(0, total_groups - total_banned)
    formatted_target = f"@{norm_username}" if norm_username else (raw_target_str if raw_target_str.startswith("@") else (str(numeric_id) if numeric_id else t_norm))

    res = (
        f"🚫 **Global Ban Executed!**\n\n"
        f"👤 **Target:** `{formatted_target}`\n"
        f"🤖 **Banned by Bot Account in:** `{banned_bot}` groups\n"
        f"⚡ **Banned by Hosted Userbots in:** `{banned_ub}` groups\n"
        f"❌ **Failed / No Admin Rights in:** `{failed}` groups\n"
        f"📊 **Total Groups Banned:** `{total_banned}` / `{total_groups}` groups\n"
        f"📝 **Reason:** `{reason}`\n\n"
        f"🛡️ *Target is saved in DB and will be auto-banned instantly if they message in any group where bot/userbots have admin rights.*"
    )
    return res


async def execute_global_unban(raw_target, target_entity=None):
    """
    Executes a Global Unban across ALL platform groups.
    """
    async with gban_sync_lock:
        if hasattr(raw_target, "id"):
            target_entity = raw_target
            raw_target = str(raw_target.id)

        raw_target_str = str(raw_target).strip()
        t_norm = normalize_gban_target(raw_target_str)
        if not t_norm or t_norm in RESERVED_GBAN_KEYWORDS:
            return "❌ **Invalid target.** Specify a valid @username or user ID to GUNBAN."

    all_groups = await get_all_platform_groups(main_bot_client)
    total_groups = len(all_groups)

    b_client = main_bot_client
    resolved_entity = target_entity
    numeric_id = int(t_norm) if t_norm.lstrip("-").isdigit() else None
    norm_username = raw_target_str[1:].lower() if raw_target_str.startswith("@") else (t_norm.lower() if not t_norm.lstrip("-").isdigit() else None)

    if resolved_entity:
        if hasattr(resolved_entity, "id"):
            numeric_id = resolved_entity.id
        if hasattr(resolved_entity, "username") and resolved_entity.username:
            norm_username = resolved_entity.username.lower()

    if not norm_username and b_client and b_client.is_connected():
        try:
            from aurora.plugins.utility import get_user_entity_robust
            ent = await get_user_entity_robust(b_client, raw_target_str)
            if ent:
                resolved_entity = ent
                if hasattr(ent, "id"):
                    numeric_id = ent.id
                if hasattr(ent, "username") and ent.username:
                    norm_username = ent.username.lower()
        except Exception:
            pass

    # Remove from memory GBAN_LIST
    GBAN_LIST.pop(t_norm, None)
    if norm_username:
        GBAN_LIST.pop(norm_username, None)
        GBAN_LIST.pop(f"@{norm_username}", None)
    if numeric_id:
        GBAN_LIST.pop(str(numeric_id), None)

    # Persist deletion in DB
    try:
        with db_session() as session:
            session.query(GBanUser).filter(
                (GBanUser.target == t_norm) |
                (GBanUser.target == f"@{t_norm}") |
                (GBanUser.target == str(numeric_id) if numeric_id else False)
            ).delete(synchronize_session=False)
            session.commit()
    except Exception as e:
        LOGS.error(f"Error deleting GBanUser DB record: {e}")

    unbanned_bot = 0
    unbanned_ub = 0
    unbanned_groups = set()

    # 1. Unban via Bot Account
    if b_client and b_client.is_connected():
        load_persistent_data()
        for g_id in list(BOT_GROUPS.keys()):
            success = await perform_group_unban(b_client, g_id, raw_target_str, resolved_entity, numeric_id, norm_username)
            if success:
                unbanned_bot += 1
                unbanned_groups.add(g_id)

    # 2. Unban via Active Hosted Userbots
    active_users = session_manager.get_all_active_users()
    for uid in active_users:
        u_client = session_manager.get_active_client(uid)
        if u_client and u_client.is_connected():
            try:
                ub_entity = resolved_entity
                if not ub_entity:
                    try:
                        from aurora.plugins.utility import get_user_entity_robust
                        ub_entity = await get_user_entity_robust(u_client, raw_target_str)
                    except Exception:
                        pass

                async for dialog in u_client.iter_dialogs():
                    if is_group_dialog(dialog) and dialog.id in all_groups and dialog.id not in unbanned_groups:
                        g_id = dialog.id
                        success = await perform_group_unban(u_client, g_id, raw_target_str, ub_entity, numeric_id, norm_username)
                        if success:
                            unbanned_ub += 1
                            unbanned_groups.add(g_id)
            except Exception as e:
                LOGS.error(f"Error executing userbot GUNBAN for {uid}: {e}")

    total_unbanned = len(unbanned_groups)
    failed = max(0, total_groups - total_unbanned)
    formatted_target = f"@{norm_username}" if norm_username else (raw_target_str if raw_target_str.startswith("@") else (str(numeric_id) if numeric_id else t_norm))

    res = (
        f"✅ **Global Unban Executed!**\n\n"
        f"👤 **Target:** `{formatted_target}`\n"
        f"🤖 **Unbanned by Bot Account in:** `{unbanned_bot}` groups\n"
        f"⚡ **Unbanned by Hosted Userbots in:** `{unbanned_ub}` groups\n"
        f"❌ **Failed / No Admin Rights in:** `{failed}` groups\n"
        f"📊 **Total Groups Unbanned:** `{total_unbanned}` / `{total_groups}` groups"
    )
    return res


async def get_formatted_gban_list(client=None):
    """
    Returns formatted GBAN list in format: name(user id) - banned by
    """
    load_persistent_data()
    if not GBAN_LIST:
        return "ℹ️ **No users currently globally banned.**"

    if client is None:
        client = main_bot_client

    seen_keys = set()
    entries = []

    for target, reason in GBAN_LIST.items():
        t_clean = str(target).lower().strip()
        if t_clean in seen_keys or t_clean in RESERVED_GBAN_KEYWORDS:
            continue

        entity = None
        user_id = "Unknown"
        name = None
        username = None

        if t_clean.isdigit() or (t_clean.startswith("-") and t_clean[1:].isdigit()):
            user_id = t_clean
        else:
            username = f"@{t_clean}" if not t_clean.startswith("@") else t_clean

        if client and client.is_connected():
            try:
                entity = await client.get_entity(target)
                if entity:
                    user_id = str(getattr(entity, "id", user_id))
                    u_name = getattr(entity, "first_name", None) or ""
                    l_name = getattr(entity, "last_name", None) or ""
                    full_n = f"{u_name} {l_name}".strip()
                    if full_n:
                        name = full_n
                    if getattr(entity, "username", None):
                        username = f"@{entity.username}"
            except Exception:
                pass

        if not name:
            name = username if username else f"User {user_id}"

        dedup_key = user_id if user_id != "Unknown" else (username.lower() if username else t_clean)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        seen_keys.add(t_clean)

        entries.append(f"• {name}({user_id}) - {reason}")

    if not entries:
        return "ℹ️ **No users currently globally banned.**"

    res = f"🚫 **Globally Banned Users List (`{len(entries)}` users):**\n\n"
    res += "\n".join(entries)
    return res


async def get_formatted_admin_list(client=None):
    """
    Returns formatted Admin/Sudo list in format: name(user id)
    """
    load_persistent_data()

    if client is None:
        client = main_bot_client

    admins = set()
    if Config.OWNER_ID:
        admins.add(Config.OWNER_ID)
    for u in SUDO_USERS:
        admins.add(u)

    try:
        with db_session() as session:
            for db_u in session.query(User).filter(User.role.in_(["owner", "admin"])).all():
                admins.add(db_u.telegram_id)
    except Exception:
        pass

    seen_keys = set()
    entries = []

    for target in admins:
        t_clean = str(target).strip()
        if t_clean in seen_keys or not t_clean:
            continue

        entity = None
        user_id = "Unknown"
        name = None
        username = None

        if t_clean.isdigit() or (t_clean.startswith("-") and t_clean[1:].isdigit()):
            user_id = t_clean
        else:
            username = f"@{t_clean}" if not t_clean.startswith("@") else t_clean

        if client and client.is_connected():
            try:
                entity = await client.get_entity(target)
                if entity:
                    user_id = str(getattr(entity, "id", user_id))
                    u_name = getattr(entity, "first_name", None) or ""
                    l_name = getattr(entity, "last_name", None) or ""
                    full_n = f"{u_name} {l_name}".strip()
                    if full_n:
                        name = full_n
                    if getattr(entity, "username", None):
                        username = f"@{entity.username}"
            except Exception:
                pass

        if not name:
            name = username if username else f"Admin {user_id}"

        dedup_key = user_id if user_id != "Unknown" else (username.lower() if username else t_clean)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        seen_keys.add(t_clean)

        entries.append(f"• {name}({user_id})")

    if not entries:
        entries.append(f"• Owner({Config.OWNER_ID})")

    res = f"👑 **Sudo / Admin Users List (`{len(entries)}` admins):**\n\n"
    res += "\n".join(entries)
    return res

WELCOME_TEXT = """🌟 **Welcome To The Premium Aurora Userbot Platform!** 🌟

🚀 **Unleash The Power Of Multi-User Automation With Style!** 🚀

👑 **Crafted By:** @tglegend77 👑

🔒 **100% Secure, Isolated & Encrypted!** 🔒

✨ **Explore Commands With /help Or Tap Below!** ✨"""

HELP_TEXT = """🔹 /start - Launch the Bot with a Grand Welcome
🔹 /help - Discover All Commands
🔹 /commands - Explore Userbot Features
🔹 /host - Deploy Your Own Userbot
🔹 /support - Request Support from Admin (Fast Response)
🔹 /restart - Revive Your Hosted Userbot
🔹 /supportraid - Pro Support Raid Command (Owners / Premium Users Only)
🔹 /restartall - Restart All Userbots (Owners Only)
🔹 /refresh - Refresh Bot State (Owners Only)
🔹 /status - Check Your Userbot's Pulse
🔹 /logout - Safely Log Out Your Userbot
🔹 /sudolist - View Sudo Users (Owner/Admin)
🔹 /setdp - Set Display Photo (Owners Only)
🔹 /allow - Authorize a User to Host/Use Bot (Owner/Admin)
🔹 /disallow - Revoke User Authorization (Owner/Admin)
🔹 /allowedlist - View Authorized Users (Owner/Admin)
🔹 /block - Block a User (Owner/Admin)
🔹 /unblock - Unblock a User (Owner/Admin)
🔹 /blockeduser - View Blocked Users (Owner/Admin)
🔹 /glist - Groups Where Bot Has Admin Access (Owner/Admin)
🔹 /gbroadcast - Broadcast to All Bot Groups via Bot Account (Owner/Admin)
🔹 .broadcast - Broadcast to All Joined Groups via User Account
🔹 /stats - View Bot Statistics"""

COMMANDS_HEADER = """✨ **Userbot Commands - Premium Aurora!** ✨

💬 **Click a Box To Explore Commands!** 💬

🔹 **Choose A Feature Below** 🔹"""

CATEGORIES_INFO = {
    "cat_spam": (
        "✨ **Spam 📨 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.spam <count> [chatid] <message> [@username]`\n"
        "📝 **Description:** Spam a message multiple times.\n"
        "💡 **Example:** `.spam 5 @username Hello!`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopspam [id]`\n"
        "   📝 **Description:** Stop spam.\n"
        "   💡 **Usage:** `.stopspam 123`\n"
        "   💡 **Example:** `.stopspam 123`"
    ),
    "cat_tspam": (
        "✨ **Timed Spam ⏲️ Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.tspam <time> [chatid/@username] <count> <message>`\n"
        "📝 **Description:** Spam with a time delay.\n"
        "💡 **Example:** `.tspam 1 @username 5 Test`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopspam [id]`\n"
        "   📝 **Description:** Stop timed spam.\n"
        "   💡 **Usage:** `.stopspam 456`\n"
        "   💡 **Example:** `.stopspam 456`"
    ),
    "cat_raid": (
        "✨ **Raid 💥 Commands (Multi-Language)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.raid <count> [lang] [@username/reply]`\n"
        "📝 **Description:** Raid in chosen language (default: Hindi).\n"
        "💡 **Examples:**\n"
        "• `.raid 10 te @user` — Telugu\n"
        "• `.raid 10 hi @user` — Hindi\n"
        "• `.raid 10 en @user` — English\n"
        "• `.raid 10 kn @user` — Kannada\n\n"
        "🌐 **Language Codes:**\n"
        "`hi`=Hindi `te`=Telugu `en`=English `ta`=Tamil\n"
        "`pa`=Punjabi `kn`=Kannada `ml`=Malayalam `mr`=Marathi\n"
        "`bn`=Bengali `gu`=Gujarati `bho`=Bhojpuri `hr`=Haryanvi\n\n"
        "🔗 **Related:** `.stopraid` | `.raidlangs` (view all codes)"
    ),
    "cat_araid": (
        "✨ **Abusive Raid 🔥 Commands (Multi-Language)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.araid <count> [lang] [@username/reply]`\n"
        "📝 **Description:** Send abusive lines in chosen language.\n"
        "💡 **Examples:**\n"
        "• `.araid 10 te @user` — Telugu\n"
        "• `.araid 10 hi @user` — Hindi\n"
        "• `.araid 10 mr @user` — Marathi\n\n"
        "🌐 **Codes:** `hi` `te` `en` `ta` `pa` `kn` `ml` `mr` `bn` `gu` `bho` `hr`\n"
        "🛑 **Stop:** `.stopraid`"
    ),
    "cat_sraid": (
        "✨ **Shayari Raid 💌 Commands (Multi-Language)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.sraid <count> [lang] [@username/reply]`\n"
        "📝 **Description:** Send romantic shayari in chosen language.\n"
        "💡 **Examples:**\n"
        "• `.sraid 5 te @user` — Telugu shayari\n"
        "• `.sraid 5 hi @user` — Hindi shayari\n"
        "• `.sraid 5 en @user` — English shayari\n\n"
        "🌐 **Codes:** `te` `hi` `en` (others fallback to Hindi)\n\n"
        "🔗 **Stop:** `.stopsraid`"
    ),
    "cat_rraid": (
        "✨ **Reply Raid 🎯 Commands (Multi-Language)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.replyraid [lang] [@username/reply]` (also `.rraid`)\n"
        "📝 **Description:** Auto-reply in chosen language when target speaks or tags you.\n"
        "💡 **Examples:**\n"
        "• `.replyraid te @user` — Telugu reply raid\n"
        "• `.replyraid hi @user` — Hindi reply raid\n"
        "• `.replyraid kn @user` — Kannada reply raid\n\n"
        "🌐 **Codes:** `hi` `te` `en` `ta` `pa` `kn` `ml` `mr` `bn` `gu` `bho` `hr`\n\n"
        "🔗 **Stop:** `.dreplyraid [user]`"
    ),
    "cat_tagging": (
        "✨ **Tagging 🔔 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.tagall`\n"
        "📝 **Description:** Tag all group members.\n"
        "💡 **Example:** `.tagall`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stoptagall [id]`\n"
        "   📝 **Description:** Stop tagall.\n"
        "   💡 **Usage:** `.stoptagall 101`\n"
        "   💡 **Example:** `.stoptagall 101`"
    ),
    "cat_welcome": (
        "✨ **Welcome 🎉 Commands (DMs Only)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.setwlcm <message>`\n"
        "📝 **Description:** Set custom welcome message for incoming DMs only (never sent in groups).\n"
        "💡 **Example:** `.setwlcm Welcome!`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopwlcm`  📝 **Description:** Disable DM welcome.\n"
        "➤ `.wlcmmssg`  📝 **Description:** Reset DM welcome."
    ),
    "cat_mod": (
        "✨ **Moderation 🚫 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.ban @username [reason]`\n"
        "📝 **Description:** Ban a user (admin only).\n"
        "💡 **Example:** `.ban @username Spamming`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.unban @username` - Unban a user\n"
        "➤ `.mute @username [time] [reason]` - Mute a user\n"
        "➤ `.unmute @username` - Unmute a user\n"
        "➤ `.kick @username [reason]` - Kick a user\n"
        "➤ `.clear <count>` - Delete messages\n"
        "➤ `.rmall` - Remove all members\n"
        "➤ `/invall <group_link>` - Add members from another group\n"
        "➤ `.add <@username>` - Add users to group"
    ),
    "cat_owner": (
        "✨ **Owner 👑 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 **Owner-Exclusive Permissions:**\n"
        "🔹 `/addsudousers <@username/id>`\n"
        "   📝 Add a Sudo user / Admin to the bot (Owner Only).\n"
        "🔹 `/removesodousers <@username/id>`\n"
        "   📝 Remove a Sudo user / Admin from the bot (Owner Only).\n\n"
        "🛡️ **Admin & Moderation Permissions (Allowed to both Owner & Admins):**\n"
        "🔹 `/allow <@username/id>` - Authorize user to host/use userbot\n"
        "🔹 `/disallow <@username/id>` - Revoke user authorization\n"
        "🔹 `/allowedlist` - List authorized users\n"
        "🔹 `/block <@username/id>` - Block user from bot\n"
        "🔹 `/unblock <@username/id>` - Unblock user\n"
        "🔹 `/blockeduser` - List blocked users\n"
        "🔹 `/gbroadcast <message>` - Broadcast via bot account to bot groups\n"
        "🔹 `/glist` - List groups where bot has admin access\n"
        "🔹 `/listsudousers` - View all Sudo Admins\n"
        "🔹 `/restartall` | `/refresh` - Platform maintenance"
    ),
    "cat_admin": (
        "✨ **Admin 🔧 Commands (Owner & Admins)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `/gban <@username/id> [reason]` (or `.gban`)\n"
        "   📝 Global ban user across all groups.\n"
        "🔹 `/gunban <@username/id>` (or `.gunban`)\n"
        "   📝 Global unban user across all groups.\n"
        "🔹 `/listgban` - View globally banned users.\n\n"
        "🔹 `/allow <@username/id>` (or `.allow`)\n"
        "   📝 Authorize a user to host and use userbot.\n"
        "🔹 `/disallow <@username/id>` (or `.disallow`)\n"
        "   📝 Revoke user authorization.\n"
        "🔹 `/allowedlist` - View all authorized users.\n\n"
        "🔹 `/block <@username/id>` (or `.block`)\n"
        "   📝 Block a user from using the bot.\n"
        "🔹 `/unblock <@username/id>` (or `.unblock`)\n"
        "   📝 Unblock a user.\n"
        "🔹 `/blockeduser` - View all blocked users.\n\n"
        "🔹 `/gbroadcast <message>` (or `.gbroadcast`)\n"
        "   📝 Broadcast via Bot Account to all groups bot is present in.\n"
        "🔹 `/glist` (or `.glist`)\n"
        "   📝 View all groups where the bot is present and has admin access.\n"
        "🔹 `/listgroups` - View all platform group memberships.\n"
        "🔹 `/listsudousers` - View all Sudo Admins."
    ),
    "cat_bcast": (
        "✨ **Broadcast 📢 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.broadcast <message>`\n"
        "   📝 **User Local Broadcast:** Sent from YOUR userbot account to all groups you are joined in.\n"
        "   💡 **Example:** `.broadcast Hello everyone!`\n\n"
        "🔹 `/gbroadcast <message>` (or `.gbroadcast`)\n"
        "   📝 **Bot Global Broadcast:** Sent by the BOT ACCOUNT to all groups where the bot is present (Owner/Admin).\n"
        "   💡 **Example:** `/gbroadcast Welcome to Aurora Userbot Network!`\n\n"
        "🔹 `/glist` (or `.glist`)\n"
        "   📝 **Bot Admin Groups:** Lists all groups where the bot is present and has admin rights (Owner/Admin)."
    ),
    "cat_craid": (
        "✨ **CRAID ⚡ Commands (Multi-Language)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.craid <count> [lang]`\n"
        "📝 **Description:** Super fast raid in chosen language.\n"
        "💡 **Examples:**\n"
        "• `.craid 50 te` — 50 Telugu lines\n"
        "• `.craid 50 hi` — 50 Hindi lines\n\n"
        "🌐 **Codes:** `hi` `te` `en` `ta` `pa` `kn` `ml` `mr` `bn` `gu` `bho` `hr`\n\n"
        "🔗 **Related:** `.setraid <channel_link>` - Set your personal raid channel"
    ),
    "cat_gen": (
        "✨ **General ℹ️ Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.ping` - Check bot speed\n"
        "🔹 `.uptime` - Check uptime\n"
        "🔹 `.info [@username]` - Get user/chat info\n"
        "🔹 `.logout` - Logout userbot"
    ),
    "cat_fun": (
        "✨ **Fun 😂 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.joke` - Get a random Hindi joke\n"
        "🔹 `.flip` - Flip a coin\n"
        "🔹 `.roll <number>` - Roll a dice\n"
        "🔹 `.rps rock|paper|scissors` - Play rock-paper-scissors\n"
        "🔹 `.calc <expression>` - Calculate math"
    ),
    "cat_custom": (
        "✨ **Customization ✍️ Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.stylish <name>` - Generate stylish names\n"
        "🔹 `.changeowner @username` - Change owner tag in .ping"
    ),
    "cat_save": (
        "✨ **Save Disappearing 💾 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.sd` - Save disappearing message to Saved Messages"
    ),
    "cat_antisafe": (
        "✨ **AntiSafe Shield Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.antisafe on/off` - Turn on/off hardcore DM protection"
    ),
    "cat_approve": (
        "✨ **Approve & GBan Exemption Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📩 **DM AntiSafe Approval:**\n"
        "🔹 `.approve` - Save user from AntiSafe DM deletion\n"
        "🔹 `.disapprove` - Remove user DM approval\n\n"
        "👥 **Group GBan Exemption:**\n"
        "🔹 `.gapprove <@username/id>` (or `/gapprove`) - Exempt user from GBAN auto-ban in THIS group only\n"
        "🔹 `.gdisapprove <@username/id>` (or `/gdisapprove`) - Remove GBAN exemption for THIS group"
    ),
    "cat_clone": (
        "✨ **Profile Clone & Revert 🎭 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.clone <@username/reply>`\n"
        "📝 **Description:** Clone a user's profile name, bio, photo, and username (+1).\n"
        "💡 **Example:** `.clone @username`\n\n"
        "🔹 `.dclone` / `.revert`\n"
        "📝 **Description:** Restore your original profile photo, name, bio, and username.\n"
        "💡 **Example:** `.revert`"
    ),
    "cat_autoreply": (
        "✨ **AutoReply Robot Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.autoreply <message>` - Mention/tag automatic reply\n"
        "🔹 `.dautoreply` - Disable tag auto reply"
    )
}


def get_commands_keyboard():
    return [
        [Button.inline("📨 Spam", data="cat_spam"), Button.inline("⏰ Timed Spam", data="cat_tspam"), Button.inline("💥 Raid", data="cat_raid")],
        [Button.inline("🔥 Abusive Raid", data="cat_araid"), Button.inline("💌 Shayari Raid", data="cat_sraid"), Button.inline("🎯 Reply Raid", data="cat_rraid")],
        [Button.inline("🔔 Tagging", data="cat_tagging"), Button.inline("🎉 Welcome", data="cat_welcome"), Button.inline("🚫 Moderation", data="cat_mod")],
        [Button.inline("😂 Fun", data="cat_fun"), Button.inline("✍️ Customization", data="cat_custom"), Button.inline("💾 Save Disappearing", data="cat_save")],
        [Button.inline("👑 Owner", data="cat_owner"), Button.inline("🔧 Admin", data="cat_admin"), Button.inline("📢 Broadcast", data="cat_bcast")],
        [Button.inline("🛡️ AntiSafe", data="cat_antisafe"), Button.inline("✅ Approve", data="cat_approve"), Button.inline("⚡ CRAID", data="cat_craid")],
        [Button.inline("🤖 AutoReply", data="cat_autoreply"), Button.inline("🎭 Profile Clone", data="cat_clone"), Button.inline("ℹ️ General", data="cat_gen")],
    ]


async def start_periodic_reconciliation():
    """Starts background periodic reconciliation task running every 10 minutes."""
    while True:
        try:
            await asyncio.sleep(600)  # Every 10 minutes
            if main_bot_client and main_bot_client.is_connected():
                await reconcile_global_bans(main_bot_client)
        except asyncio.CancelledError:
            break
        except Exception as e:
            LOGS.error(f"Error in periodic reconciliation loop: {e}")
            await asyncio.sleep(60)


async def start_aurora_bot():
    token = Config.TG_BOT_TOKEN
    if not token:
        LOGS.error("TG_BOT_TOKEN not configured.")
        return

    from telethon.sessions import SQLiteSession
    from telethon.errors import FloodWaitError

    bot = TelegramClient(
        SQLiteSession("aurora_hoster_bot"),
        Config.API_ID,
        Config.API_HASH,
        auto_reconnect=True,
        connection_retries=None,
        retry_delay=5,
    )
    await bot.connect()
    if not await bot.is_user_authorized():
        try:
            await bot.start(bot_token=token)
        except FloodWaitError as e:
            LOGS.warning(f"Telegram FloodWait for Bot Token: Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 2)
            await bot.start(bot_token=token)

    global main_bot_client
    main_bot_client = bot

    load_persistent_data()
    try:
        asyncio.create_task(reconcile_global_bans(bot))
    except Exception as e:
        LOGS.error(f"Error launching global ban reconciliation on startup: {e}")

    # Launch periodic reconciliation loop
    asyncio.create_task(start_periodic_reconciliation())

    bot_me = await bot.get_me()
    print(f"\n[+] Aurora Platform Bot RUNNING as @{bot_me.username}!")

    @bot.on(events.ChatAction)
    async def chat_action_handler(event):
        if event.is_group or (event.is_channel and getattr(event.chat, "megagroup", False)):
            title = getattr(event.chat, "title", "Group") or "Group"
            if event.user_left or event.user_kicked:
                try:
                    left_user = await event.get_user()
                    if left_user and left_user.id == bot_me.id:
                        remove_bot_group(event.chat_id)
                        return
                except Exception:
                    pass

            if event.user_joined or event.user_added:
                try:
                    joined_user = await event.get_user()
                    if joined_user and joined_user.id == bot_me.id:
                        # Bot was added to group -> Auto sync!
                        asyncio.create_task(sync_new_group(bot, event.chat_id, title))
                        return
                except Exception:
                    pass
                try:
                    user = await event.get_user()
                    if user:
                        u_id_str = str(user.id)
                        uname = getattr(user, "username", None) or ""
                        uname_key = f"@{uname.lower()}" if uname else ""

                        is_gbanned = (
                            u_id_str in GBAN_LIST or
                            (uname and uname.lower() in GBAN_LIST) or
                            (uname_key and uname_key in GBAN_LIST)
                        )
                        if is_gbanned:
                            approved_set = APPROVED_USERS_PER_GROUP.get(event.chat_id, set())
                            if (
                                u_id_str in approved_set or
                                (uname_key and uname_key in approved_set) or
                                (uname and uname.lower() in approved_set)
                            ):
                                return  # Exempted in this group!

                            # Re-ban gbanned user who entered/was unbanned by local admin
                            try:
                                await bot.edit_permissions(event.chat_id, user.id, view_messages=False)
                            except Exception:
                                try:
                                    await bot.kick_participant(event.chat_id, user.id)
                                except Exception:
                                    pass

                            try:
                                await event.respond(
                                    f"🚫 **GBANNED User Detected & Auto-Banned!**\n\n"
                                    f"👤 **User:** `{u_id_str}` ({uname_key or uname})\n"
                                    f"⚠️ *This user is globally banned across Aurora network. Unbanning by local admin overridden.*"
                                )
                            except Exception:
                                pass
                except Exception as e:
                    LOGS.error(f"Error in chat_action GBAN check: {e}")

    @bot.on(events.NewMessage)
    async def group_moderation_handler(event):
        if not (event.is_group or (event.is_channel and getattr(event.chat, "megagroup", False))):
            return

        try:
            title = getattr(event.chat, "title", "Group") or "Group"
            save_bot_group(event.chat_id, title)
        except Exception:
            pass

        text = (event.raw_text or "").strip()
        if not text:
            return

        sender_id = event.sender_id
        sender_id_str = str(sender_id)
        sender_obj = None
        try:
            sender_obj = await event.get_sender()
        except Exception:
            pass
        uname = getattr(sender_obj, "username", None) or ""
        uname_key = f"@{uname.lower()}" if uname else ""

        # Auto-ban GBANNED users when they send a message in group
        is_gbanned = (
            sender_id_str in GBAN_LIST or
            (uname and uname.lower() in GBAN_LIST) or
            (uname_key and uname_key in GBAN_LIST)
        )

        if is_gbanned:
            approved_set = APPROVED_USERS_PER_GROUP.get(event.chat_id, set())
            if not (
                sender_id_str in approved_set or
                (uname_key and uname_key in approved_set) or
                (uname and uname.lower() in approved_set)
            ):
                try:
                    await event.delete()
                except Exception:
                    pass

                try:
                    await bot.edit_permissions(event.chat_id, sender_id, view_messages=False)
                    await event.respond(
                        f"🚫 **GBANNED User Auto-Banned!**\n\n"
                        f"👤 **User:** `{sender_id_str}` ({uname_key or uname})\n"
                        f"⚠️ *This user is globally banned across Aurora network. Group admins can use `.gapprove` to allow them in this group.*"
                    )
                except Exception:
                    pass
                return

        # Check for command execution in groups (commands starting with . or /)
        if text.startswith(".") or text.startswith("/"):
            first_word = text.split()[0].lower()
            cmd = first_word[1:] if len(first_word) > 1 else ""
            if not cmd:
                return

            is_owner_admin = is_admin_or_owner(sender_id, uname)

            # Owner & Bot Admin commands
            OWNER_ADMIN_COMMANDS = {
                "gban", "gunban", "gbanlist", "listgban",
                "addsudo", "addsudousers", "rmsudo", "removesodousers", "removesudouser",
                "listsudousers", "sudolist", "adminlist",
                "listgroups", "gbroadcast", "gcast", "glist",
                "restartall", "refresh",
                "block", "unblock", "blockeduser", "listblock",
                "allow", "disallow", "allowedlist"
            }

            if cmd in OWNER_ADMIN_COMMANDS:
                if not is_owner_admin:
                    await event.reply("⛔ **Access Denied!** Owner & Bot Admin commands are restricted to platform admins only.")
                    return

                # Execute Owner / Bot Admin command in group for authorized admins
                if cmd in ["listsudousers", "sudolist", "adminlist"]:
                    res = await get_formatted_admin_list(bot)
                    await event.reply(res)
                    return
                elif cmd in ["listgban", "gbanlist"]:
                    res = await get_formatted_gban_list(bot)
                    await event.reply(res)
                    return
                elif cmd == "gban":
                    input_str = text[len(first_word):].strip()
                    raw_target, target_entity, reason = await resolve_gban_event_target(bot, event, input_str)
                    if not raw_target:
                        await event.reply("💡 **Usage:** `.gban <@username or user_id> [reason]` or reply to user")
                        return
                    msg = await event.reply(f"⚡ **Initiating Global Ban for:** `{raw_target}`...")
                    res = await execute_global_ban(raw_target, target_entity=target_entity, reason=reason)
                    await msg.edit(res)
                    return
                elif cmd == "gunban":
                    input_str = text[len(first_word):].strip()
                    target, target_entity = await resolve_gunban_event_target(bot, event, input_str)
                    if not target:
                        await event.reply("💡 **Usage:** `.gunban <@username or user_id>` or reply to user")
                        return
                    msg = await event.reply(f"⚡ **Initiating Global Unban for:** `{target}`...")
                    res = await execute_global_unban(target, target_entity=target_entity)
                    await msg.edit(res)
                    return
                elif cmd in ["gbroadcast", "gcast"]:
                    reply = await event.get_reply_message()
                    msg_text = text[len(first_word):].strip()
                    if not msg_text and reply:
                        msg_text = reply.text or reply.message
                    if not msg_text:
                        await event.reply("💡 **Usage:** `.gbroadcast <message>` or reply to a message")
                        return
                    msg = await event.reply("📢 **Sending Global Broadcast across Aurora platform...**")
                    res = await execute_global_broadcast(msg_text, reply_msg=reply, event=event)
                    await msg.edit(res)
                    return
                elif cmd == "listgroups":
                    msg = await event.reply("⏳ **Fetching all platform group memberships...**")
                    all_groups = await get_all_platform_groups(bot)
                    if not all_groups:
                        await msg.edit("ℹ️ **No active groups recorded across platform.**")
                        return
                    res = f"📊 **Bot Group Membership List (`{len(all_groups)}` groups):**\n\n"
                    for g_id, g_name in all_groups.items():
                        res += f"• **{g_name}** (ID: `{g_id}`)\n"
                    if len(res) > 3900:
                        res = res[:3900] + "\n\n...[List Truncated]"
                    await msg.edit(res)
                    return
                elif cmd == "glist":
                    msg = await event.reply("⏳ **Fetching groups where bot has admin access...**")
                    res = await get_bot_admin_groups_list(bot)
                    await msg.edit(res)
                    return
                elif cmd in ["addsudousers", "addsudo"]:
                    if not is_owner(sender_id, uname):
                        await event.reply("⛔ **Owner privileges required.** Only the platform owner can add sudo admins.")
                        return
                    target = text[len(first_word):].strip()
                    if not target:
                        await event.reply("💡 **Usage:** `.addsudousers <@username or user_id>`")
                        return
                    s_id = target
                    s_name = None
                    try:
                        target_ent = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                        s_id = str(target_ent.id)
                        s_name = getattr(target_ent, "username", None)
                    except Exception:
                        if target.startswith("@"):
                            s_name = target[1:]
                        else:
                            s_id = target

                    SUDO_USERS.add(s_id)
                    try:
                        SUDO_USERS.add(int(s_id))
                    except Exception:
                        pass
                    if s_name:
                        s_clean = s_name.lower().lstrip("@")
                        SUDO_USERS.add(s_name.lower())
                        SUDO_USERS.add(s_clean)
                        SUDO_USERS.add(f"@{s_clean}")

                    try:
                        with db_session() as session:
                            existing = session.query(SudoUser).filter(SudoUser.user_id == s_id).first()
                            if not existing:
                                session.add(SudoUser(user_id=s_id, username=s_name))
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error saving SudoUser: {e}")

                    display = f"@{s_name} (ID: `{s_id}`)" if s_name else f"ID: `{s_id}`"
                    await event.reply(f"👑 **Added Sudo Admin:** {display}")
                    return
                elif cmd in ["removesodousers", "rmsudo", "removesudouser"]:
                    if not is_owner(sender_id, uname):
                        await event.reply("⛔ **Owner privileges required.** Only the platform owner can remove sudo admins.")
                        return
                    target = text[len(first_word):].strip()
                    if not target:
                        await event.reply("💡 **Usage:** `.removesodousers <@username or user_id>`")
                        return
                    target_clean = target.lower().lstrip("@")
                    removed_id = None
                    try:
                        with db_session() as session:
                            for su in session.query(SudoUser).all():
                                if su.user_id == target or (su.username and su.username.lower().lstrip("@") == target_clean):
                                    removed_id = su.user_id
                                    session.delete(su)
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error removing SudoUser: {e}")

                    SUDO_USERS.discard(target)
                    SUDO_USERS.discard(target_clean)
                    SUDO_USERS.discard(f"@{target_clean}")
                    if removed_id:
                        SUDO_USERS.discard(removed_id)
                        try:
                            SUDO_USERS.discard(int(removed_id))
                        except Exception:
                            pass
                    await event.reply(f"🛑 **Removed Sudo Admin:** `{target}`")
                    return
                elif cmd == "block":
                    target = text[len(first_word):].strip()
                    if not target:
                        reply = await event.get_reply_message()
                        if reply and reply.sender_id:
                            target = str(reply.sender_id)
                    if not target:
                        await event.reply("💡 **Usage:** `.block <@username or user_id>` or reply to a user")
                        return
                    b_id = target
                    b_name = ""
                    try:
                        entity = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                        b_id = str(entity.id)
                        if getattr(entity, "username", None):
                            b_name = f"@{entity.username}"
                    except Exception:
                        if target.startswith("@"):
                            b_name = target
                        else:
                            b_id = target
                    info = {"id": b_id, "username": b_name or "N/A"}
                    BLOCKED_USERS[b_id] = info
                    try:
                        BLOCKED_USERS[int(b_id)] = info
                    except Exception:
                        pass
                    if b_name:
                        b_clean = b_name.lower().lstrip("@")
                        BLOCKED_USERS[b_name.lower()] = info
                        BLOCKED_USERS[b_clean] = info
                        BLOCKED_USERS[f"@{b_clean}"] = info
                    try:
                        with db_session() as session:
                            existing = session.query(BlockedUser).filter(BlockedUser.user_id == b_id).first()
                            if not existing:
                                session.add(BlockedUser(user_id=b_id, username=b_name))
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error saving BlockedUser: {e}")
                    u_str = f"{b_name} (ID: `{b_id}`)" if b_name else f"ID: `{b_id}`"
                    await event.reply(f"🚫 **Blocked User:** {u_str}")
                    return
                elif cmd == "unblock":
                    target = text[len(first_word):].strip()
                    if not target:
                        reply = await event.get_reply_message()
                        if reply and reply.sender_id:
                            target = str(reply.sender_id)
                    if not target:
                        await event.reply("💡 **Usage:** `.unblock <@username or user_id>` or reply to a user")
                        return
                    removed = False
                    target_lower = target.lower().lstrip("@")
                    for k in list(BLOCKED_USERS.keys()):
                        if str(k).lower().lstrip("@") == target_lower or str(BLOCKED_USERS[k].get("id")) == target:
                            r_id = BLOCKED_USERS[k].get("id")
                            BLOCKED_USERS.pop(k, None)
                            removed = True
                            try:
                                with db_session() as session:
                                    session.query(BlockedUser).filter(
                                        (BlockedUser.user_id == str(r_id)) | (BlockedUser.username == k)
                                    ).delete(synchronize_session=False)
                                    session.commit()
                            except Exception:
                                pass
                    if removed:
                        await event.reply(f"✅ **Unblocked User:** `{target}`")
                    else:
                        await event.reply(f"ℹ️ **User `{target}` is not in blocked list.**")
                    return
                elif cmd in ["listblock", "blockeduser"]:
                    unique_blocked = {}
                    for info in BLOCKED_USERS.values():
                        unique_blocked[info["id"]] = info.get("username") or "N/A"
                    if not unique_blocked:
                        await event.reply("ℹ️ **No users currently blocked.**")
                        return
                    res = f"🚫 **Blocked Users List (`{len(unique_blocked)}`):**\n\n"
                    for b_id, b_name in unique_blocked.items():
                        res += f"• `{b_name}` (ID: `{b_id}`)\n"
                    await event.reply(res)
                    return
                elif cmd == "allow":
                    target = text[len(first_word):].strip()
                    if not target:
                        reply = await event.get_reply_message()
                        if reply and reply.sender_id:
                            target = str(reply.sender_id)
                    if not target:
                        await event.reply("💡 **Usage:** `.allow <@username or user_id>` or reply to a user")
                        return

                    a_id = target
                    a_name = None
                    try:
                        target_ent = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                        a_id = str(target_ent.id)
                        a_name = getattr(target_ent, "username", None)
                    except Exception:
                        if target.startswith("@"):
                            a_name = target[1:]
                        else:
                            a_id = target

                    info = {"id": a_id, "username": a_name or "N/A"}
                    ALLOWED_USERS[a_id] = info
                    if a_name:
                        ALLOWED_USERS[a_name.lower()] = info

                    try:
                        with db_session() as session:
                            existing = session.query(AllowedUser).filter(AllowedUser.user_id == a_id).first()
                            if not existing:
                                session.add(AllowedUser(user_id=a_id, username=a_name))
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error saving AllowedUser: {e}")

                    u_str = f"@{a_name} (ID: `{a_id}`)" if a_name else f"ID: `{a_id}`"
                    await event.reply(f"✅ **Allowed User:** {u_str}\n\n*User is now authorized to host and use Aurora Userbot.*")
                    return
                elif cmd == "disallow":
                    target = text[len(first_word):].strip()
                    if not target:
                        reply = await event.get_reply_message()
                        if reply and reply.sender_id:
                            target = str(reply.sender_id)
                    if not target:
                        await event.reply("💡 **Usage:** `.disallow <@username or user_id>` or reply to a user")
                        return

                    removed = False
                    target_lower = target.lower().lstrip("@")
                    for k in list(ALLOWED_USERS.keys()):
                        if k.lower() == target_lower or str(ALLOWED_USERS[k].get("id")) == target:
                            r_id = ALLOWED_USERS[k].get("id")
                            ALLOWED_USERS.pop(k, None)
                            removed = True
                            try:
                                with db_session() as session:
                                    session.query(AllowedUser).filter(
                                        (AllowedUser.user_id == r_id) | (AllowedUser.username == k)
                                    ).delete(synchronize_session=False)
                                    session.commit()
                            except Exception:
                                pass

                    if removed:
                        await event.reply(f"🛑 **Disallowed User:** `{target}`\n\n*User can no longer host or use Aurora Userbot.*")
                    else:
                        await event.reply(f"ℹ️ **User `{target}` is not in allowed list.**")
                    return
                elif cmd in ["allowedlist", "listallow", "allowlist"]:
                    unique_allowed = {}
                    for info in ALLOWED_USERS.values():
                        unique_allowed[info["id"]] = info.get("username") or "N/A"

                    if not unique_allowed:
                        await event.reply("ℹ️ **No users currently in allowed list.**\n\n*Only Owner & Sudo Admins have default permission.*")
                        return

                    res = f"📋 **Authorized/Allowed Users List (`{len(unique_allowed)}`):**\n\n"
                    for u_id, u_name in unique_allowed.items():
                        name_display = f"@{u_name}" if u_name != "N/A" else "N/A"
                        res += f"• `{name_display}` (ID: `{u_id}`)\n"
                    await event.reply(res)
                    return
                elif cmd in ["restartall", "refresh"]:
                    if sender_id != Config.OWNER_ID:
                        await event.reply("⛔ **Owner privileges required.**")
                        return
                    if cmd == "restartall":
                        msg = await event.reply("🔄 **Restarting all userbot sessions...**")
                        count = await session_manager.load_all_sessions()
                        await msg.edit(f"✅ **Restarted `{count}` userbot sessions!**")
                    else:
                        await event.reply("✨ **Platform state refreshed successfully!**")
                    return

            # Group Admin Exemption commands (.gapprove, .gdisapprove, .gunapprove)
            if cmd in ["gapprove", "gdisapprove", "gunapprove"]:
                reply = await event.get_reply_message()
                parts = text[len(first_word):].strip().split()
                target = parts[0] if parts else (str(reply.sender_id) if reply else None)

                if not target:
                    await event.reply(f"💡 **Usage:** Reply to a user or type `.{cmd} <@username or user_id>`")
                    return

                is_allowed = is_owner_admin
                if not is_allowed:
                    try:
                        p = await bot.get_permissions(event.chat_id, sender_id)
                        if p.is_admin:
                            is_allowed = True
                    except Exception:
                        pass

                if not is_allowed:
                    await event.reply("⛔ **Group Admin or Bot Admin privileges required!**")
                    return

                if cmd == "gapprove":
                    t_key = str(target).lower()
                    if event.chat_id not in APPROVED_USERS_PER_GROUP:
                        APPROVED_USERS_PER_GROUP[event.chat_id] = set()
                    APPROVED_USERS_PER_GROUP[event.chat_id].add(t_key)
                    try:
                        with db_session() as session:
                            existing = session.query(ApprovedGroupUser).filter(
                                ApprovedGroupUser.group_id == event.chat_id,
                                ApprovedGroupUser.target == t_key
                            ).first()
                            if not existing:
                                session.add(ApprovedGroupUser(group_id=event.chat_id, target=t_key))
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error persisting ApprovedGroupUser: {e}")
                    try:
                        target_entity = await resolve_target(bot, target)
                        await bot.edit_permissions(event.chat_id, target_entity, view_messages=True, send_messages=True)
                    except Exception:
                        pass
                    await event.reply(
                        f"✅ **User Approved for this Group!**\n\n"
                        f"👤 **Target:** `{target}`\n"
                        f"🛡️ *This user is exempted from GBAN auto-ban in this group.*"
                    )
                    return
                else: # gdisapprove / gunapprove
                    t_key = str(target).lower()
                    t_norm = t_key[1:] if t_key.startswith("@") else t_key
                    if event.chat_id in APPROVED_USERS_PER_GROUP:
                        APPROVED_USERS_PER_GROUP[event.chat_id].discard(t_key)
                        APPROVED_USERS_PER_GROUP[event.chat_id].discard(t_norm)
                        APPROVED_USERS_PER_GROUP[event.chat_id].discard(f"@{t_norm}")
                    try:
                        with db_session() as session:
                            session.query(ApprovedGroupUser).filter(
                                ApprovedGroupUser.group_id == event.chat_id,
                                (ApprovedGroupUser.target == t_key) | (ApprovedGroupUser.target == t_norm) | (ApprovedGroupUser.target == f"@{t_norm}")
                            ).delete(synchronize_session=False)
                            session.commit()
                    except Exception as e:
                        LOGS.error(f"Error removing ApprovedGroupUser: {e}")
                    banned_again = False
                    is_gbanned = (t_key in GBAN_LIST or t_norm in GBAN_LIST or f"@{t_norm}" in GBAN_LIST)
                    if is_gbanned:
                        try:
                            target_entity = await resolve_target(bot, target)
                            await bot.edit_permissions(event.chat_id, target_entity, view_messages=False)
                            banned_again = True
                        except Exception:
                            try:
                                await bot.kick_participant(event.chat_id, target)
                                banned_again = True
                            except Exception:
                                pass
                    if banned_again:
                        await event.reply(
                            f"🛑 **User Disapproved & Banned!**\n\n"
                            f"👤 **Target:** `{target}`\n"
                            f"⚠️ *Group exemption removed. Target is globally banned and has been banned again from this group.*"
                        )
                    else:
                        await event.reply(
                            f"🛑 **User Disapproved for this Group!**\n\n"
                            f"👤 **Target:** `{target}`\n"
                            f"⚠️ *Group exemption removed.*"
                        )
                    return

            # General Userbot Commands in Group: Check if sender is a logged-in userbot owner
            has_active_userbot = session_manager.get_active_client(sender_id) is not None
            if not has_active_userbot:
                bot_username = "AuroraVexBot"
                try:
                    if main_bot_client:
                        b_me = await main_bot_client.get_me()
                        if b_me and b_me.username:
                            bot_username = b_me.username
                except Exception:
                    pass

                group_help_text = (
                    "✨ **Aurora Userbot Group Commands!** ✨\n\n"
                    "The following commands can be executed in groups by hosted userbots:\n\n"
                    "📨 **Spam & Raid:** `.spam`, `.tspam`, `.raid`, `.araid`, `.sraid`, `.replyraid`, `.craid`\n"
                    "🔔 **Tagging & Moderation:** `.tagall`, `.ban`, `.unban`, `.mute`, `.unmute`, `.kick`, `.clear`, `.add`\n"
                    "✍️ **Utility & Fun:** `.info`, `.ping`, `.sd`, `.stylish`, `.autoreply`, `.clone`, `.joke`\n\n"
                    "💡 **Want to use these commands?**\n"
                    "🚀 **Host your own userbot now!**\n"
                    f"👉 Open PM with @{bot_username} and send `/host` to deploy your userbot in seconds!"
                )
                await event.reply(group_help_text)
                return

    @bot.on(events.NewMessage)
    async def handler(event):
        if not event.is_private:
            return

        # Ignore outgoing messages sent by the bot itself to prevent infinite self-reply loops!
        if getattr(event, "out", False):
            return

        chat_id = event.chat_id
        sender_id_str = str(chat_id)
        sender_obj = await event.get_sender()
        uname = getattr(sender_obj, "username", None) or ""
        uname_key = f"@{uname.lower()}" if uname else ""

        # Check Blocked & GBAN list
        is_blocked = (
            sender_id_str in BLOCKED_USERS or
            (uname_key and uname_key in BLOCKED_USERS) or
            (uname and uname.lower() in BLOCKED_USERS)
        )
        if is_blocked and chat_id != Config.OWNER_ID:
            await event.reply("🚫 **You are BLOCKED from using Aurora Bot.**\n\nContact platform owner for unblock.")
            return

        is_gbanned = (
            sender_id_str in GBAN_LIST or
            (uname and uname.lower() in GBAN_LIST) or
            (uname_key and uname_key in GBAN_LIST)
        )
        if is_gbanned and chat_id != Config.OWNER_ID:
            await event.reply("🚫 **You are currently GBANNED from using Aurora Userbot!**\n\nAsk platform Owner or Admin for unban.")
            return

        # Authorization check: only Allowed users, Sudo Admins, or Owner can use or host the bot
        if not is_user_allowed_to_use(chat_id, uname):
            await event.reply(
                "⛔ **Access Denied!**\n\n"
                "You do not have permission to use or host this bot.\n"
                "Please take owner/admin permission (`/allow`) to gain access."
            )
            return

        text = (event.raw_text or "").strip()

        # Command: /cancel
        if text in ["/cancel", "/stop"]:
            if chat_id in user_login_states:
                sess = user_login_states.pop(chat_id)
                if sess.get("client"):
                    try:
                        await sess["client"].disconnect()
                    except Exception:
                        pass
            await event.reply("❌ Onboarding cancelled. Send /host whenever you want to begin again.")
            return

        # Command Handling for both Slash (/) and Dot (.) prefixes
        if text.startswith("/") or text.startswith("."):
            clean_text = text[1:].strip()
            first_word = text.split()[0].lower()
            cmd = first_word[1:] if len(first_word) > 1 else ""

            # Reset login state on new command unless it's cancel/stop
            if chat_id in user_login_states and cmd not in ["cancel", "stop"]:
                old_sess = user_login_states.pop(chat_id)
                if old_sess.get("client"):
                    try:
                        await old_sess["client"].disconnect()
                    except Exception:
                        pass

            if cmd in ["host", "login"]:
                user_client = session_manager.get_active_client(chat_id)
                has_db_session = session_manager.get_decrypted_session(chat_id) is not None
                if (user_client and user_client.is_connected()) or has_db_session:
                    await event.reply(
                        "🟢 **Your session is active!**\n\n"
                        "Your Aurora userbot is already hosted and logged in.\n"
                        "💡 Use `/status` to check details or `/logout` if you wish to log out and host a new account."
                    )
                    return

                user_login_states[chat_id] = {
                    "step": "WAITING_PHONE",
                    "phone": None,
                    "client": None,
                    "phone_code_hash": None,
                }
                await event.reply("📱 **Enter Phone Number (+91xxxxxxxxxx for India or +299xxxxxx for Greenland):**")
                return

            # Command: /hostsession or .hostsession (Direct StringSession Login)
            if cmd == "hostsession":
                parts = text.split(maxsplit=1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply(
                        "ℹ️ **Usage:** `/hostsession <string_session>`\n\n"
                        "💡 *Generate a string session on your PC with `python stringsetup.py` and send `/hostsession <string>` to host instantly without needing OTP!*"
                    )
                    return

                session_str_input = parts[1].strip()
                try:
                    await event.delete()
                except Exception:
                    pass

                msg = await event.reply("⏳ **Validating string session...**")
                test_client = TelegramClient(StringSession(session_str_input), Config.API_ID, Config.API_HASH)
                try:
                    await test_client.connect()
                    if not await test_client.is_user_authorized():
                        await test_client.disconnect()
                        await msg.edit("❌ **Invalid or expired string session.** Please generate a fresh session.")
                        return

                    me = await test_client.get_me()
                    await test_client.disconnect()

                    role = "owner" if me.id == Config.OWNER_ID else "user"
                    await session_manager.save_user_session(
                        telegram_id=me.id,
                        session_str=session_str_input,
                        phone=getattr(me, "phone", None),
                        username=getattr(me, "username", None),
                        first_name=me.first_name,
                        role=role,
                    )
                    await session_manager.start_user_session(me.id)

                    user_str = f"@{me.username}" if getattr(me, "username", None) else me.first_name
                    await msg.edit(
                        f"🎉 **Aurora Userbot Successfully Hosted!**\n\n"
                        f"👤 **Account:** {user_str}\n"
                        f"🆔 **Telegram ID:** `{me.id}`\n\n"
                        f"🔒 **Session Status:** AES-256 Encrypted in Aurora DB."
                    )
                except Exception as e:
                    try:
                        await test_client.disconnect()
                    except Exception:
                        pass
                    await msg.edit(sanitize_text(f"❌ **Error activating session:** `{e}`"))
                return

            # Command: /start or .start
            if cmd == "start":
                buttons = [
                    [Button.inline("📖 Help", data="cmd_help"), Button.inline("✨ Commands", data="cat_main")],
                    [Button.inline("🚀 Host Userbot", data="cmd_host")]
                ]
                await event.reply(WELCOME_TEXT, buttons=buttons)
                return

            # Command: /help or .help
            if cmd == "help":
                buttons = [
                    [Button.inline("✨ Explore Commands", data="cat_main")],
                    [Button.inline("🚀 Host Userbot", data="cmd_host")]
                ]
                await event.reply(HELP_TEXT, buttons=buttons)
                return

            # Command: /commands, .commands, /cmds, .cmds, /command, .command
            if cmd in ["commands", "cmds", "command"]:
                await event.reply(COMMANDS_HEADER, buttons=get_commands_keyboard())
                return

            # Command: /support or .support
            if cmd == "support":
                await event.reply(f"💬 **Support:** Contact @{Config.OWNER_USERNAME} (Fast Response)")
                return

            # Command: /restart or .restart
            if cmd == "restart":
                msg = await event.reply("🔄 **Reviving your hosted userbot session...**")
                client = await session_manager.start_user_session(chat_id)
                if client and client.is_connected():
                    await msg.edit("🟢 **Aurora Userbot Revived & Active!**")
                else:
                    await msg.edit("🔴 **No active session found.** Send /host to deploy your userbot.")
                return

            # Command: /supportraid or .supportraid
            if cmd == "supportraid":
                await event.reply("💥 **Pro Support Raid Command:** Ready for Pro / Premium users.")
                return

            # Command: /info or .info
            if cmd == "info":
                reply = await event.get_reply_message()
                query = text[len(text.split()[0]):].strip()

                target = None
                if reply:
                    try:
                        target = await reply.get_sender()
                    except Exception:
                        pass
                    if not target and reply.sender_id:
                        target = reply.sender_id
                elif query:
                    q_str = query.strip()
                    if q_str.isdigit() or (q_str.startswith("-") and q_str[1:].isdigit()):
                        target = int(q_str)
                    else:
                        target = q_str
                else:
                    try:
                        target = await event.get_sender() or event.sender_id
                    except Exception:
                        target = event.sender_id

                from aurora.plugins.utility import get_user_entity_robust
                target_user = await get_user_entity_robust(bot, target)
                if not target_user and target:
                    try:
                        target_user = await bot.get_entity(target)
                    except Exception:
                        pass

                if target_user:
                    if getattr(target_user, "title", None) and getattr(target_user, "first_name", None) is None:
                        title = getattr(target_user, "title", "Group/Channel")
                        chat_id_val = target_user.id
                        username = f"@{target_user.username}" if getattr(target_user, "username", None) else "None"
                        members_count = getattr(target_user, "participants_count", "Unknown")
                        await event.reply(
                            f"💬 **Chat / Channel Info:**\n\n"
                            f"📛 **Title:** `{title}`\n"
                            f"🆔 **ID:** `{chat_id_val}`\n"
                            f"🏷️ **Username:** {username}\n"
                            f"👥 **Members:** `{members_count}`"
                        )
                        return

                    name = f"{getattr(target_user, 'first_name', '') or ''} {getattr(target_user, 'last_name', '') or ''}".strip() or "Unknown"
                    username = f"@{target_user.username}" if getattr(target_user, "username", None) else "None"
                    user_id = getattr(target_user, "id", "Unknown")
                    is_bot = getattr(target_user, "bot", False)
                    is_premium = getattr(target_user, "premium", False)
                    is_verified = getattr(target_user, "verified", False)
                    is_scam = getattr(target_user, "scam", False)

                    bio = "None"
                    common_chats = "0"
                    try:
                        from telethon.tl.functions.users import GetFullUserRequest
                        full_user = await bot(GetFullUserRequest(target_user))
                        full_info = getattr(full_user, "full_user", None)
                        if full_info:
                            bio = full_info.about or "None"
                            common_chats = str(getattr(full_info, "common_chats_count", 0))
                    except Exception:
                        pass

                    dc_id = "Unknown"
                    if getattr(target_user, "photo", None):
                        dc_id = str(getattr(target_user.photo, "dc_id", "Unknown"))

                    permalink = f"[{name}](tg://user?id={user_id})"

                    info_text = (
                        f"👤 **User Info:**\n\n"
                        f"📛 **Name:** {permalink}\n"
                        f"🆔 **User ID:** `{user_id}`\n"
                        f"🏷️ **Username:** {username}\n"
                        f"📝 **Bio:** `{bio}`\n"
                        f"🤖 **Is Bot:** `{is_bot}`\n"
                        f"⭐ **Is Premium:** `{is_premium}`\n"
                        f"🛡️ **Verified:** `{is_verified}` | ⚠️ **Scam:** `{is_scam}`\n"
                        f"🌐 **Data Center (DC):** `{dc_id}`\n"
                        f"💬 **Common Chats:** `{common_chats}`"
                    )
                    await event.reply(info_text)
                else:
                    t_str = str(target or "Unknown")
                    permalink = f"[User {t_str}](tg://user?id={t_str})" if t_str.lstrip("-").isdigit() else f"`{t_str}`"
                    info_text = (
                        f"👤 **User Info:**\n\n"
                        f"📛 **Name:** {permalink}\n"
                        f"🆔 **User ID:** `{t_str}`\n"
                        f"🏷️ **Username:** None\n"
                        f"📝 **Bio:** None\n"
                        f"🤖 **Is Bot:** `False`\n"
                        f"⭐ **Is Premium:** `False`\n"
                        f"🛡️ **Verified:** `False` | ⚠️ **Scam:** `False`\n"
                        f"🌐 **Data Center (DC):** `Unknown`\n"
                        f"💬 **Common Chats:** `0`"
                    )
                    await event.reply(info_text)
                return

            # Command: /restartall or .restartall (Owner Only)
            if cmd == "restartall":
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                msg = await event.reply("🔄 **Restarting all userbot sessions...**")
                count = await session_manager.load_all_sessions()
                await msg.edit(f"✅ **Restarted `{count}` userbot sessions!**")
                return

            # Command: /refresh or .refresh (Owner Only)
            if cmd == "refresh":
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                await event.reply("✨ **Platform state refreshed successfully!**")
                return

            # Command: /status or .status
            if cmd == "status":
                user_client = session_manager.get_active_client(chat_id)
                if user_client and user_client.is_connected():
                    msg = f"🟢 **Aurora Status:** ACTIVE & HOSTED\n🆔 **User ID:** `{chat_id}`"
                else:
                    msg = f"🔴 **Aurora Status:** NOT ACTIVE (Send /host to deploy your userbot)"
                await event.reply(sanitize_text(msg))
                return

            # Command: /logout or .logout
            if cmd == "logout":
                user_client = session_manager.get_active_client(chat_id)
                has_db_session = session_manager.get_decrypted_session(chat_id) is not None

                if user_client or has_db_session:
                    await session_manager.revoke_user_session(chat_id)
                    await event.reply("🔒 **Safely Logged Out!**\nYour encrypted session has been revoked and removed from Aurora DB.")
                else:
                    await event.reply("ℹ️ **You are not currently logged in.** Send /host to deploy your userbot.")
                return

            # Command: /listsudousers & /sudolist & /adminlist & .listsudousers & .sudolist & .adminlist (Owner & Admin)
            if cmd in ["listsudousers", "sudolist", "adminlist"]:
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                res = await get_formatted_admin_list(bot)
                await event.reply(res)
                return

            # Command: /addsudousers /addsudo .addsudousers .addsudo (Owner Only)
            if cmd in ["addsudousers", "addsudo"]:
                if not is_owner(chat_id, uname):
                    await event.reply("⛔ **Owner privileges required.** Only the platform owner can add sudo admins.")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    await event.reply("💡 **Usage:** `/addsudousers <@username or user_id>`")
                    return
                s_id = target
                s_name = None
                try:
                    target_ent = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                    s_id = str(target_ent.id)
                    s_name = getattr(target_ent, "username", None)
                except Exception:
                    if target.startswith("@"):
                        s_name = target[1:]
                    else:
                        s_id = target

                SUDO_USERS.add(s_id)
                try:
                    SUDO_USERS.add(int(s_id))
                except Exception:
                    pass
                if s_name:
                    s_clean = s_name.lower().lstrip("@")
                    SUDO_USERS.add(s_name.lower())
                    SUDO_USERS.add(s_clean)
                    SUDO_USERS.add(f"@{s_clean}")

                try:
                    with db_session() as session:
                        existing = session.query(SudoUser).filter(SudoUser.user_id == s_id).first()
                        if not existing:
                            session.add(SudoUser(user_id=s_id, username=s_name))
                        session.commit()
                except Exception as e:
                    LOGS.error(f"Error saving SudoUser: {e}")

                display = f"@{s_name} (ID: `{s_id}`)" if s_name else f"ID: `{s_id}`"
                await event.reply(f"👑 **Added Sudo Admin:** {display}")
                return

            # Command: /removesodousers /rmsudo /removesudouser .removesodousers .rmsudo (Owner Only)
            if cmd in ["removesodousers", "rmsudo", "removesudouser"]:
                if not is_owner(chat_id, uname):
                    await event.reply("⛔ **Owner privileges required.** Only the platform owner can remove sudo admins.")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    await event.reply("💡 **Usage:** `/removesodousers <@username or user_id>`")
                    return
                target_clean = target.lower().lstrip("@")
                removed_id = None
                try:
                    with db_session() as session:
                        for su in session.query(SudoUser).all():
                            if su.user_id == target or (su.username and su.username.lower().lstrip("@") == target_clean):
                                removed_id = su.user_id
                                session.delete(su)
                        session.commit()
                except Exception as e:
                    LOGS.error(f"Error removing SudoUser: {e}")

                SUDO_USERS.discard(target)
                SUDO_USERS.discard(target_clean)
                SUDO_USERS.discard(f"@{target_clean}")
                if removed_id:
                    SUDO_USERS.discard(removed_id)
                    try:
                        SUDO_USERS.discard(int(removed_id))
                    except Exception:
                        pass
                await event.reply(f"🛑 **Removed Sudo Admin:** `{target}`")
                return

            # Command: /listgroups or .listgroups (Admin & Owner)
            if cmd == "listgroups":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return

                msg = await event.reply("⏳ **Fetching all platform group memberships...**")
                all_groups = await get_all_platform_groups(bot)

                if not all_groups:
                    await msg.edit("ℹ️ **No active groups recorded across platform.**\n\n💡 *Add bot or userbot to a group to register it!*")
                    return

                res = f"📊 **Bot Group Membership List (`{len(all_groups)}` groups):**\n\n"
                for g_id, name in all_groups.items():
                    res += f"• **{name}** (ID: `{g_id}`)\n"

                if len(res) > 3900:
                    res = res[:3900] + "\n\n...[List Truncated]"

                await msg.edit(res)
                return

            # Command: /glist or .glist (Admin & Owner)
            if cmd == "glist":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                msg = await event.reply("⏳ **Fetching groups where bot has admin access...**")
                res = await get_bot_admin_groups_list(bot)
                await msg.edit(res)
                return

            # Command: /clearbotgroups (Owner Only)
            if cmd == "clearbotgroups":
                if not is_owner(chat_id, uname):
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                BOT_GROUPS.clear()
                try:
                    with db_session() as session:
                        session.query(BotGroup).delete()
                        session.commit()
                except Exception:
                    pass
                await event.reply("✅ **Cleared all bot groups cache and database records!**")
                return

            # Command: /gban or .gban (Admin & Owner)
            if cmd == "gban":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                input_str = text[len(first_word):].strip()
                raw_target, target_entity, reason = await resolve_gban_event_target(bot, event, input_str)
                if not raw_target:
                    await event.reply("💡 **Usage:** `/gban <@username or user_id> [reason]` or reply to a user")
                    return

                msg = await event.reply(f"⚡ **Initiating Global Ban for:** `{raw_target}`...")
                res = await execute_global_ban(raw_target, target_entity=target_entity, reason=reason)
                await msg.edit(res)
                return

            # Command: /gunban or .gunban (Admin & Owner)
            if cmd == "gunban":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                input_str = text[len(first_word):].strip()
                target, target_entity = await resolve_gunban_event_target(bot, event, input_str)
                if not target:
                    await event.reply("💡 **Usage:** `/gunban <@username or user_id>` or reply to a user")
                    return
                msg = await event.reply(f"⚡ **Initiating Global Unban for:** `{target}`...")
                res = await execute_global_unban(target, target_entity=target_entity)
                await msg.edit(res)
                return

            # Command: /listgban & /gbanlist & .listgban & .gbanlist (Admin & Owner)
            if cmd in ["listgban", "gbanlist"]:
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return

                res = await get_formatted_gban_list(bot)
                await event.reply(res)
                return

            # Command: /gbroadcast or .gbroadcast or /gcast or .gcast (Admin & Owner)
            if cmd in ["gbroadcast", "gcast"]:
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                reply = await event.get_reply_message()
                msg_text = text[len(text.split()[0]):].strip()
                if not msg_text and reply:
                    msg_text = reply.text or reply.message

                if not msg_text:
                    await event.reply("💡 **Usage:** `/gbroadcast <message>` or reply to a message")
                    return

                msg = await event.reply("📢 **Sending Global Broadcast via Bot Account...**")
                res = await execute_global_broadcast(msg_text, reply_msg=reply, event=event)
                await msg.edit(res)
                return

            # Command: /block or .block (Admin & Owner)
            if cmd == "block":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    reply = await event.get_reply_message()
                    if reply and reply.sender_id:
                        target = str(reply.sender_id)
                if not target:
                    await event.reply("💡 **Usage:** `/block <@username or user_id>` or reply to a user")
                    return

                b_id = target
                b_name = ""
                try:
                    entity = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                    b_id = str(entity.id)
                    if getattr(entity, "username", None):
                        b_name = f"@{entity.username}"
                except Exception:
                    if target.startswith("@"):
                        b_name = target
                    else:
                        b_id = target

                info = {"id": b_id, "username": b_name or "N/A"}
                BLOCKED_USERS[b_id] = info
                try:
                    BLOCKED_USERS[int(b_id)] = info
                except Exception:
                    pass
                if b_name:
                    b_clean = b_name.lower().lstrip("@")
                    BLOCKED_USERS[b_name.lower()] = info
                    BLOCKED_USERS[b_clean] = info
                    BLOCKED_USERS[f"@{b_clean}"] = info

                try:
                    with db_session() as session:
                        existing = session.query(BlockedUser).filter(BlockedUser.user_id == b_id).first()
                        if not existing:
                            session.add(BlockedUser(user_id=b_id, username=b_name))
                        session.commit()
                except Exception as e:
                    LOGS.error(f"Error saving BlockedUser: {e}")

                u_str = f"{b_name} (ID: `{b_id}`)" if b_name else f"ID: `{b_id}`"
                await event.reply(f"🚫 **Blocked User:** {u_str}")
                return

            # Command: /unblock or .unblock (Admin & Owner)
            if cmd == "unblock":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    reply = await event.get_reply_message()
                    if reply and reply.sender_id:
                        target = str(reply.sender_id)
                if not target:
                    await event.reply("💡 **Usage:** `/unblock <@username or user_id>` or reply to a user")
                    return

                removed = False
                target_lower = target.lower().lstrip("@")
                for k in list(BLOCKED_USERS.keys()):
                    if str(k).lower().lstrip("@") == target_lower or str(BLOCKED_USERS[k].get("id")) == target:
                        r_id = BLOCKED_USERS[k].get("id")
                        BLOCKED_USERS.pop(k, None)
                        removed = True
                        try:
                            with db_session() as session:
                                session.query(BlockedUser).filter(
                                    (BlockedUser.user_id == str(r_id)) | (BlockedUser.username == k)
                                ).delete(synchronize_session=False)
                                session.commit()
                        except Exception:
                            pass

                if removed:
                    await event.reply(f"✅ **Unblocked User:** `{target}`")
                else:
                    await event.reply(f"ℹ️ **User `{target}` is not in blocked list.**")
                return

            # Command: /listblock or /blockeduser or .listblock or .blockeduser (Admin & Owner)
            if cmd in ["listblock", "blockeduser"]:
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return

                unique_blocked = {}
                for info in BLOCKED_USERS.values():
                    unique_blocked[info["id"]] = info.get("username") or "N/A"

                if not unique_blocked:
                    await event.reply("ℹ️ **No users currently blocked.**")
                    return

                res = f"🚫 **Blocked Users List (`{len(unique_blocked)}`):**\n\n"
                for b_id, b_name in unique_blocked.items():
                    res += f"• `{b_name}` (ID: `{b_id}`)\n"
                await event.reply(res)
                return

            # Command: /allow or .allow (Owner & Admin)
            if cmd == "allow":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    reply = await event.get_reply_message()
                    if reply and reply.sender_id:
                        target = str(reply.sender_id)
                if not target:
                    await event.reply("💡 **Usage:** `/allow <@username or user_id>` or reply to a user")
                    return

                a_id = target
                a_name = None
                try:
                    target_ent = await bot.get_entity(target if not target.lstrip("-").isdigit() else int(target))
                    a_id = str(target_ent.id)
                    a_name = getattr(target_ent, "username", None)
                except Exception:
                    if target.startswith("@"):
                        a_name = target[1:]
                    else:
                        a_id = target

                info = {"id": a_id, "username": a_name or "N/A"}
                ALLOWED_USERS[a_id] = info
                try:
                    ALLOWED_USERS[int(a_id)] = info
                except Exception:
                    pass
                if a_name:
                    a_clean = a_name.lower().lstrip("@")
                    ALLOWED_USERS[a_name.lower()] = info
                    ALLOWED_USERS[a_clean] = info
                    ALLOWED_USERS[f"@{a_clean}"] = info

                try:
                    with db_session() as session:
                        existing = session.query(AllowedUser).filter(AllowedUser.user_id == a_id).first()
                        if not existing:
                            session.add(AllowedUser(user_id=a_id, username=a_name))
                        session.commit()
                except Exception as e:
                    LOGS.error(f"Error saving AllowedUser: {e}")

                u_str = f"@{a_name} (ID: `{a_id}`)" if a_name else f"ID: `{a_id}`"
                await event.reply(f"✅ **Allowed User:** {u_str}\n\n*User is now authorized to host and use Aurora Userbot.*")
                return

            # Command: /disallow or .disallow (Owner & Admin)
            if cmd == "disallow":
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return
                target = text[len(text.split()[0]):].strip()
                if not target:
                    reply = await event.get_reply_message()
                    if reply and reply.sender_id:
                        target = str(reply.sender_id)
                if not target:
                    await event.reply("💡 **Usage:** `/disallow <@username or user_id>` or reply to a user")
                    return

                removed = False
                target_lower = target.lower().lstrip("@")
                for k in list(ALLOWED_USERS.keys()):
                    if str(k).lower().lstrip("@") == target_lower or str(ALLOWED_USERS[k].get("id")) == target:
                        r_id = ALLOWED_USERS[k].get("id")
                        ALLOWED_USERS.pop(k, None)
                        removed = True
                        try:
                            with db_session() as session:
                                session.query(AllowedUser).filter(
                                    (AllowedUser.user_id == str(r_id)) | (AllowedUser.username == k)
                                ).delete(synchronize_session=False)
                                session.commit()
                        except Exception:
                            pass

                if removed:
                    await event.reply(f"🛑 **Disallowed User:** `{target}`\n\n*User can no longer host or use Aurora Userbot.*")
                else:
                    await event.reply(f"ℹ️ **User `{target}` is not in allowed list.**")
                return

            # Command: /allowedlist or .allowedlist (Owner & Admin)
            if cmd in ["allowedlist", "listallow", "allowlist"]:
                if not is_admin_or_owner(chat_id, uname):
                    await event.reply("⛔ **Owner or Bot Admin privileges required.**")
                    return

                unique_allowed = {}
                for info in ALLOWED_USERS.values():
                    unique_allowed[info["id"]] = info.get("username") or "N/A"

                if not unique_allowed:
                    await event.reply("ℹ️ **No users currently in allowed list.**\n\n*Only Owner & Sudo Admins have default permission.*")
                    return

                res = f"📋 **Authorized/Allowed Users List (`{len(unique_allowed)}`):**\n\n"
                for u_id, u_name in unique_allowed.items():
                    name_display = f"@{u_name}" if u_name != "N/A" else "N/A"
                    res += f"• `{name_display}` (ID: `{u_id}`)\n"
                await event.reply(res)
                return

            # Command: .broadcast or /broadcast (User Local Broadcast)
            if cmd == "broadcast":
                reply = await event.get_reply_message()
                msg_text = text[len(first_word):].strip()
                if not msg_text and reply:
                    msg_text = reply.text or reply.message

                if not msg_text:
                    await event.reply("❌ **Provide message text or reply to a message to broadcast.**\n💡 **Example:** `.broadcast Hello everyone!`")
                    return

                user_client = session_manager.get_active_client(chat_id)
                if not user_client or not user_client.is_connected():
                    user_client = await session_manager.start_user_session(chat_id)

                if not user_client or not user_client.is_connected():
                    await event.reply("❌ **Active userbot session required!**\n\n*You must have a hosted userbot to broadcast to your groups. Send /host to login.*")
                    return

                status_msg = await event.reply("📢 **Starting user local broadcast across your groups...**")
                sent = 0
                failed = 0
                processed_chats = set()

                try:
                    async for dialog in user_client.iter_dialogs():
                        is_grp = dialog.is_group or (dialog.is_channel and getattr(dialog.entity, "megagroup", False))
                        if is_grp and dialog.id not in processed_chats:
                            processed_chats.add(dialog.id)
                            try:
                                if reply:
                                    await user_client.send_message(dialog.id, reply)
                                else:
                                    await user_client.send_message(dialog.id, msg_text)
                                sent += 1
                                await asyncio.sleep(0.4)
                            except Exception:
                                failed += 1
                    await status_msg.edit(f"📢 **User Broadcast Complete!**\n\n✅ **Sent from your account to:** `{sent}` groups\n❌ **Failed in:** `{failed}` groups")
                except Exception as e:
                    await status_msg.edit(f"❌ **Broadcast error:** `{e}`")
                return

            # Command: .setwelcome / .setwlcm
            if cmd in ["setwelcome", "setwlcm"]:
                user_client = session_manager.get_active_client(chat_id)
                if not user_client or not user_client.is_connected():
                    user_client = await session_manager.start_user_session(chat_id)
                if not user_client or not user_client.is_connected():
                    await event.reply("❌ **Active userbot session required!** Send /host to deploy your userbot.")
                    return
                val = text[len(first_word):].strip()
                if val:
                    from aurora.plugins.welcome import WELCOME_SETTINGS, GLOBAL_WELCOME
                    me = await user_client.get_me()
                    GLOBAL_WELCOME[me.id] = val
                    WELCOME_SETTINGS[chat_id] = val
                    await event.reply(f"🎉 **Custom Welcome Message Set For First DMs & Groups!**\n\n💬 `{val}`")
                else:
                    await event.reply("❌ **Provide a welcome message.**\n💡 **Example:** `.setwlcm Welcome!`")
                return

            # Command: .ping / /ping
            if cmd == "ping":
                start_p = time.time()
                msg_p = await event.reply("🏓 **Pinging...**")
                end_p = time.time()
                ms_p = round((end_p - start_p) * 1000, 2)
                await msg_p.edit(f"🏓 **Pong!**\n⚡ **Speed:** `{ms_p} ms`\n🟢 **Status:** Active")
                return

            # Command: /stats or .stats
            if cmd == "stats":
                total_active = len(session_manager.get_all_active_users())
                cpu_usage = psutil.cpu_percent()
                ram_usage = psutil.virtual_memory().percent
                uptime = str(datetime.utcnow() - start_time).split(".")[0]
                stats_msg = (
                    "📊 **Aurora Bot Statistics**\n\n"
                    f"⚡ **Active Userbots:** `{total_active}`\n"
                    f"💻 **CPU Usage:** `{cpu_usage}%`\n"
                    f"🧠 **RAM Usage:** `{ram_usage}%`\n"
                    f"⏳ **Uptime:** `{uptime}`"
                )
                await event.reply(stats_msg)
                return

            # Any other recognized command or non-phone input should return here
            return

        # Onboarding Flow Handler
        if chat_id in user_login_states:
            state = user_login_states[chat_id]
            step = state.get("step")

            if step == "WAITING_PHONE":
                phone = text.replace(" ", "").replace("-", "")
                if not (phone.startswith("+") and phone[1:].isdigit()):
                    await event.reply("❌ **Invalid phone format.** Enter e.g. `+91xxxxxxxxxx` or `+299xxxxxx`.")
                    return

                state["phone"] = phone
                msg = await event.reply("⏳ **Connecting to Telegram...**")

                client = TelegramClient(
                    StringSession(),
                    Config.API_ID,
                    Config.API_HASH,
                )

                try:
                    await asyncio.wait_for(client.connect(), timeout=15)
                    code_req = await asyncio.wait_for(client.send_code_request(phone), timeout=25)
                    state["client"] = client
                    state["phone_code_hash"] = getattr(code_req, "phone_code_hash", None)
                    state["step"] = "WAITING_OTP"
                    await msg.edit(
                        "🔑 **Enter OTP (e.g., 1 2 3 4 5):**\n\n"
                        "📲 **IMPORTANT:** Check your **official Telegram app** (Service Notifications chat) for your 5-digit login code!\n"
                        "⚡ *OTP expires in 2 minutes.*"
                    )
                except FloodWaitError as e:
                    await client.disconnect()
                    user_login_states.pop(chat_id, None)
                    await msg.edit(f"⏳ **Telegram Rate Limit (FloodWait):** Telegram requires waiting `{e.seconds}` seconds before requesting another code.\n\n💡 *Tip: You can also generate a session string on your PC with `python stringsetup.py` and send `/hostsession <string>` to host instantly without waiting.*")
                except PhoneNumberInvalidError:
                    await client.disconnect()
                    user_login_states.pop(chat_id, None)
                    await msg.edit("❌ **Invalid Phone Number.** Check and try /host again.")
                except asyncio.TimeoutError:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    user_login_states.pop(chat_id, None)
                    await msg.edit("⏰ **Connection timed out.** Telegram servers didn't respond. Send /host to try again.")
                except Exception as e:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    user_login_states.pop(chat_id, None)
                    await msg.edit(sanitize_text(f"❌ **Error requesting code:** `{e}`"))

            elif step == "WAITING_OTP":
                code = text.replace(" ", "").replace("-", "")
                if not code.isdigit():
                    await event.reply("❌ **Invalid OTP.** Enter digits e.g. `1 2 3 4 5`.")
                    return

                client = state.get("client")
                phone = state.get("phone")
                phone_code_hash = state.get("phone_code_hash")
                msg = await event.reply("⏳ Verifying OTP...")

                try:
                    await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                except PhoneCodeInvalidError:
                    await msg.edit("❌ **Invalid OTP code.** Try again.")
                    return
                except SessionPasswordNeededError:
                    state["step"] = "WAITING_2FA"
                    await msg.edit("🔐 **Enter 2-Step Verification Password:**\n\n*(Password will be auto-deleted)*")
                    return
                except Exception as e:
                    await msg.edit(sanitize_text(f"❌ **Sign-in error:** `{e}`"))
                    return

                # Success
                me = await client.get_me()
                session_str = client.session.save()
                await client.disconnect()

                role = "owner" if me.id == Config.OWNER_ID else "user"
                await session_manager.save_user_session(
                    telegram_id=me.id,
                    session_str=session_str,
                    phone=phone,
                    username=getattr(me, "username", None),
                    first_name=me.first_name,
                    role=role,
                )
                await session_manager.start_user_session(me.id)
                user_login_states.pop(chat_id, None)

                user_str = f"@{me.username}" if getattr(me, "username", None) else me.first_name
                await msg.edit(
                    f"🎉 **Aurora Userbot Successfully Hosted!**\n\n"
                    f"👤 **Account:** {user_str}\n"
                    f"🆔 **Telegram ID:** `{me.id}`\n\n"
                    f"🔒 **Session Status:** AES-256 Encrypted in Aurora DB."
                )

            elif step == "WAITING_2FA":
                password = text
                client = state.get("client")
                phone = state.get("phone")

                try:
                    await event.delete()
                except Exception:
                    pass

                msg = await event.reply("⏳ Verifying 2FA...")

                try:
                    await client.sign_in(password=password)
                except PasswordHashInvalidError:
                    await msg.edit("❌ **Incorrect 2FA password.** Try again.")
                    return
                except Exception as e:
                    await msg.edit(sanitize_text(f"❌ **2FA error:** `{e}`"))
                    return

                # Success
                me = await client.get_me()
                session_str = client.session.save()
                await client.disconnect()

                role = "owner" if me.id == Config.OWNER_ID else "user"
                await session_manager.save_user_session(
                    telegram_id=me.id,
                    session_str=session_str,
                    phone=phone,
                    username=getattr(me, "username", None),
                    first_name=me.first_name,
                    role=role,
                )
                await session_manager.start_user_session(me.id)
                user_login_states.pop(chat_id, None)

                user_str = f"@{me.username}" if getattr(me, "username", None) else me.first_name
                await msg.edit(
                    f"🎉 **Aurora Userbot Successfully Hosted!**\n\n"
                    f"👤 **Account:** {user_str}\n"
                    f"🆔 **Telegram ID:** `{me.id}`\n\n"
                    f"🔒 **Session Status:** AES-256 Encrypted in Aurora DB."
                )

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        try:
            await event.answer()
        except Exception:
            pass

        data = event.data.decode("utf-8")

        if data == "cmd_help":
            buttons = [
                [Button.inline("✨ Explore Commands", data="cmd_main")],
                [Button.inline("🚀 Host Userbot", data="cmd_host")]
            ]
            try:
                await event.edit(HELP_TEXT, buttons=buttons)
            except Exception:
                pass
            return

        if data == "cmd_host":
            sender_obj = await event.get_sender()
            uname = getattr(sender_obj, "username", None) or ""
            if not is_user_allowed_to_use(event.chat_id, uname):
                try:
                    await event.respond(
                        "⛔ **Access Denied!**\n\n"
                        "You do not have permission to host this bot.\n"
                        "Please take owner/admin permission (`/allow`) to gain access."
                    )
                except Exception:
                    pass
                return

            user_client = session_manager.get_active_client(event.chat_id)
            has_db_session = session_manager.get_decrypted_session(event.chat_id) is not None
            if (user_client and user_client.is_connected()) or has_db_session:
                try:
                    await event.respond(
                        "🟢 **Your session is active!**\n\n"
                        "Your Aurora userbot is already hosted and logged in.\n"
                        "💡 Use `/status` to check details or `/logout` if you wish to log out and host a new account."
                    )
                except Exception:
                    pass
                return

            user_login_states[event.chat_id] = {
                "step": "WAITING_PHONE",
                "phone": None,
                "client": None,
                "phone_code_hash": None,
            }
            try:
                await event.respond("📱 **Enter Phone Number (+91xxxxxxxxxx for India or +299xxxxxx for Greenland):**")
            except Exception:
                pass
            return

        if data == "cat_main":
            try:
                await event.edit(COMMANDS_HEADER, buttons=get_commands_keyboard())
            except Exception:
                pass
            return

        if data == "cat_owner":
            if event.sender_id != Config.OWNER_ID:
                try:
                    await event.answer("⛔ Only platform owner can access this menu!", alert=True)
                except Exception:
                    pass
                return

        if data == "cat_admin":
            is_owner = (event.sender_id == Config.OWNER_ID)
            sender_obj = await event.get_sender()
            uname = getattr(sender_obj, "username", None) or ""
            is_admin = (
                event.sender_id in SUDO_USERS or
                str(event.sender_id) in SUDO_USERS or
                uname in SUDO_USERS or
                f"@{uname}" in SUDO_USERS
            )
            if not is_owner and not is_admin:
                try:
                    await event.answer("⛔ Only admins can access this menu!", alert=True)
                except Exception:
                    pass
                return

        if data in CATEGORIES_INFO:
            back_btn = [[Button.inline("« Back to Categories", data="cat_main")]]
            try:
                await event.edit(CATEGORIES_INFO[data], buttons=back_btn)
            except Exception:
                pass
            return

    while True:
        try:
            if not bot.is_connected():
                await bot.connect()
            await bot.run_until_disconnected()
        except (ConnectionError, OSError) as e:
            LOGS.warning(f"Aurora Bot connection lost ({e}). Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            LOGS.error(f"Unexpected error in bot run loop: {e}")
            await asyncio.sleep(5)
