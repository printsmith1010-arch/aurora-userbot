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
)
from telethon.sessions import MemorySession, StringSession

from aurora.config import Config, sanitize_text
from aurora.core.session_manager import session_manager
from aurora.db.models import User, UserSession, BotGroup, GBanUser, BlockedUser
from aurora.db.session import db_session, init_db

LOGS = logging.getLogger("AuroraHosterBot")

user_login_states = {}
start_time = datetime.utcnow()
BLOCKED_USERS = {}
SUDO_USERS = {Config.OWNER_ID}
GBAN_LIST = {}
APPROVED_USERS_PER_GROUP = {}
BOT_GROUPS = {}


def load_persistent_data():
    """Loads persistent GBan, BlockedUsers, and BotGroups from database."""
    try:
        with db_session() as session:
            # Load Bot Groups
            for g in session.query(BotGroup).all():
                BOT_GROUPS[g.group_id] = g.title or "Group"

            # Load GBan Users
            for gb in session.query(GBanUser).all():
                GBAN_LIST[gb.target.lower()] = gb.reason

            # Load Blocked Users
            for bu in session.query(BlockedUser).all():
                info = {"id": bu.user_id, "username": bu.username or "N/A"}
                BLOCKED_USERS[bu.user_id] = info
                if bu.username:
                    BLOCKED_USERS[bu.username.lower()] = info
        LOGS.info(f"Loaded {len(BOT_GROUPS)} bot groups, {len(GBAN_LIST)} gban users, {len(BLOCKED_USERS)} blocked users from DB.")
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


async def get_all_platform_groups(bot=None):
    """
    Returns a dictionary of all groups {group_id: title} aggregated from:
    1. Persistent DB records (BotGroup) & in-memory BOT_GROUPS
    2. Active hosted userbots' dialogs
    """
    groups = {}

    # Load from DB & in-memory cache
    load_persistent_data()
    for g_id, name in BOT_GROUPS.items():
        groups[g_id] = name

    # Aggregate active userbots dialogs
    for uid in session_manager.get_all_active_users():
        u_client = session_manager.get_active_client(uid)
        if u_client and u_client.is_connected():
            try:
                async for dialog in u_client.iter_dialogs():
                    if is_group_dialog(dialog):
                        groups[dialog.id] = dialog.name
                        save_bot_group(dialog.id, dialog.name)
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
🔹 /sudolist - View Sudo Users (Owners Only)
🔹 /setdp - Set Display Photo (Owners Only)
🔹 /block - Block a User (Owners Only)
🔹 /unblock - Unblock a User (Owners Only)
🔹 /blockeduser - View Blocked Users (Owners Only)
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
        "✨ **Raid 💥 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.raid <count> [chatid] [@username]`\n"
        "📝 **Description:** Raid with abusive messages.\n"
        "💡 **Example:** `.raid 10 @username`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopraid [id]`\n"
        "   📝 **Description:** Stop raid.\n"
        "   💡 **Usage:** `.stopraid 789`\n"
        "   💡 **Example:** `.stopraid 789`"
    ),
    "cat_araid": (
        "✨ **Abusive Raid 🔥 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.araid`\n"
        "📝 **Description:** Send abusive words line-by-line in reply to a message or link. To stop, restart bot with /restart.\n"
        "💡 **Usage:** `.araid <count> [message_link]`\n"
        "💡 **Example:** `.araid 10 https://t.me/c/123456789/123`"
    ),
    "cat_sraid": (
        "✨ **Shayari Raid 💌 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.sraid`\n"
        "📝 **Description:** Send romantic shayari messages.\n"
        "💡 **Usage:** `.sraid <count> [username/userid/reply to user]`\n"
        "💡 **Example:** `.sraid 5 @username`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopsraid`\n"
        "   📝 **Description:** Stop shayari raid.\n"
        "   💡 **Usage:** `.stopsraid`\n"
        "   💡 **Example:** `.stopsraid`"
    ),
    "cat_rraid": (
        "✨ **Reply Raid 🎯 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.replyraid`\n"
        "📝 **Description:** Auto-reply with abusive messages when a user replies or tags you.\n"
        "💡 **Usage:** `.replyraid [username/userid/reply to user]`\n"
        "💡 **Example:** `.replyraid @username`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.dreplyraid`\n"
        "   📝 **Description:** Deactivate reply raid.\n"
        "   💡 **Usage:** `.dreplyraid [username/userid/reply to user]`\n"
        "   💡 **Example:** `.dreplyraid @username`"
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
        "✨ **Welcome 🎉 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.setwlcm <message>`\n"
        "📝 **Description:** Set custom welcome message.\n"
        "💡 **Example:** `.setwlcm Welcome!`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.stopwlcm`  📝 **Description:** Disable welcome.\n"
        "➤ `.wlcmmssg`  📝 **Description:** Reset welcome."
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
        "🔹 `/addsudousers <@username/id>`\n"
        "📝 **Description:** Add a Sudo user (Admin) to the bot.\n"
        "💡 **Example:** `/addsudousers @username`\n\n"
        "🔹 `/removesodousers <@username/id>`\n"
        "📝 **Description:** Remove a Sudo user (Admin) from the bot.\n"
        "💡 **Example:** `/removesodousers @username`\n\n"
        "🔹 `/listsudousers` (or `/sudolist`)\n"
        "📝 **Description:** List all Sudo users (Admins)."
    ),
    "cat_admin": (
        "✨ **Admin 🔧 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `/gban <@username/id> [reason]` (or `.gban`)\n"
        "📝 **Description:** Global ban a user across all groups.\n"
        "💡 **Example:** `/gban @username Spamming`\n\n"
        "🔹 `/gunban <@username/id>` (or `.gunban`)\n"
        "📝 **Description:** Global unban a user across all groups.\n"
        "💡 **Example:** `/gunban @username`\n\n"
        "🔹 `/listgban` (or `/gbanlist`)\n"
        "📝 **Description:** List all globally banned users.\n\n"
        "🔹 `/gbroadcast <message>` (or `.gbroadcast`)\n"
        "📝 **Description:** Broadcast a message to all groups where the bot/userbots are present."
    ),
    "cat_bcast": (
        "✨ **Broadcast Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.broadcast <message>`\n"
        "📝 **Description:** Broadcast a message to all groups where messaging is allowed.\n"
        "💡 **Example:** `.broadcast Hello everyone!`"
    ),
    "cat_craid": (
        "✨ **CRAID Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.craid <count> (reply)`\n"
        "📝 **Description:** Super fast personal raid using messages from your own set channel.\n"
        "💡 **Example:** Reply karke `.craid 100`\n\n"
        "🔗 **Related Commands:**\n"
        "➤ `.setraid <channel_link>` - Set your personal raid channel"
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
        "✨ **Approve Checkmark Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.approve` - Save user from AntiSafe deletion\n"
        "🔹 `.disapprove` - Disapprove user for PM"
    ),
    "cat_autoreply": (
        "✨ **AutoReply Robot Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.autoreply <message>` - Mention/tag automatic reply\n"
        "🔹 `.dautoreply` - Disable tag auto reply"
    ),
    "cat_music": (
        "✨ **Music & Voice 🎵 Commands** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `.play <song>` / `.vcplay <song>`: Stream live music in Group Voice Chat.\n"
        "🔹 `.vcpause` / `.pause`: Pause live VC audio stream.\n"
        "🔹 `.vcresume` / `.resume`: Resume live VC audio stream.\n"
        "🔹 `.vcleave` / `.vcstop` / `.leavevc`: Stop music & leave the Voice Chat call."
    )
}


def get_commands_keyboard():
    return [
        [Button.inline("📨 Spam", data="cat_spam"), Button.inline("⏰ Timed Spam", data="cat_tspam"), Button.inline("💥 Raid", data="cat_raid")],
        [Button.inline("🔥 Abusive Raid", data="cat_araid"), Button.inline("💌 Shayari Raid", data="cat_sraid"), Button.inline("🎯 Reply Raid", data="cat_rraid")],
        [Button.inline("🎵 Music & Voice", data="cat_music"), Button.inline("🔔 Tagging", data="cat_tagging"), Button.inline("🎉 Welcome", data="cat_welcome")],
        [Button.inline("🚫 Moderation", data="cat_mod"), Button.inline("😂 Fun", data="cat_fun"), Button.inline("✍️ Customization", data="cat_custom")],
        [Button.inline("👑 Owner", data="cat_owner"), Button.inline("🔧 Admin", data="cat_admin"), Button.inline("💾 Save Disappearing", data="cat_save")],
        [Button.inline("📢 Broadcast", data="cat_bcast"), Button.inline("🛡️ AntiSafe", data="cat_antisafe"), Button.inline("✅ Approve", data="cat_approve")],
        [Button.inline("⚡ CRAID", data="cat_craid"), Button.inline("🤖 AutoReply", data="cat_autoreply"), Button.inline("ℹ️ General", data="cat_gen")],
    ]


async def start_aurora_bot():
    token = Config.TG_BOT_TOKEN
    if not token:
        LOGS.error("TG_BOT_TOKEN not configured.")
        return

    bot = TelegramClient(
        MemorySession(),
        Config.API_ID,
        Config.API_HASH,
        auto_reconnect=True,
        connection_retries=None,
        retry_delay=5,
    )
    await bot.start(bot_token=token)

    load_persistent_data()

    bot_me = await bot.get_me()
    print(f"\n[+] Aurora Platform Bot RUNNING as @{bot_me.username}!")

    @bot.on(events.ChatAction)
    async def chat_action_handler(event):
        if event.is_group or (event.is_channel and getattr(event.chat, "megagroup", False)):
            try:
                title = getattr(event.chat, "title", "Group") or "Group"
                save_bot_group(event.chat_id, title)
            except Exception:
                pass

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

        # Command: /approve (used in group by group admins / owner)
        if text.startswith("/approve"):
            reply = await event.get_reply_message()
            parts = text.replace("/approve", "").strip().split()
            target = parts[0] if parts else None

            if not target and reply:
                target = str(reply.sender_id)

            if not target:
                await event.reply("💡 **Usage:** Reply to a user or type `/approve <@username or user_id>`")
                return

            # Permission check: Group Admin, Owner, or Sudo User
            is_allowed = (event.sender_id == Config.OWNER_ID or event.sender_id in SUDO_USERS or str(event.sender_id) in SUDO_USERS)
            if not is_allowed:
                try:
                    p = await bot.get_permissions(event.chat_id, event.sender_id)
                    if p.is_admin:
                        is_allowed = True
                except Exception:
                    pass

            if not is_allowed:
                await event.reply("⛔ **Group Admin privileges required to approve users!**")
                return

            if event.chat_id not in APPROVED_USERS_PER_GROUP:
                APPROVED_USERS_PER_GROUP[event.chat_id] = set()

            t_key = str(target).lower()
            APPROVED_USERS_PER_GROUP[event.chat_id].add(t_key)
            await event.reply(
                f"✅ **User Approved for this Group!**\n\n"
                f"👤 **Target:** `{target}`\n"
                f"🛡️ *This user will NOT be auto-banned by GBAN in this group.*"
            )
            return

        # Auto-ban GBANNED users when they send a message in group (if bot has ban rights)
        sender_id_str = str(event.sender_id)
        sender_obj = await event.get_sender()
        uname = getattr(sender_obj, "username", None) or ""
        uname_key = f"@{uname.lower()}" if uname else ""

        is_gbanned = (
            sender_id_str in GBAN_LIST or
            (uname and uname.lower() in GBAN_LIST) or
            (uname_key and uname_key in GBAN_LIST)
        )

        if is_gbanned:
            approved_set = APPROVED_USERS_PER_GROUP.get(event.chat_id, set())
            if (
                sender_id_str in approved_set or
                (uname_key and uname_key in approved_set) or
                (uname and uname.lower() in approved_set)
            ):
                return  # Exempted in this group!

            try:
                bot_me = await bot.get_me()
                perms = await bot.get_permissions(event.chat_id, bot_me)
                if perms.is_admin and getattr(perms, "ban_users", False):
                    await event.delete()
                    await bot.edit_permissions(event.chat_id, event.sender_id, view_messages=False)
                    await event.respond(
                        f"🚫 **GBANNED User Auto-Banned!**\n\n"
                        f"👤 **User:** `{sender_id_str}` ({uname_key or uname})\n"
                        f"⚠️ *This user is globally banned on Aurora network.*"
                    )
            except Exception:
                pass

    @bot.on(events.NewMessage)
    async def handler(event):
        if not event.is_private:
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

        # Slash Commands Handling & Onboarding Reset
        if text.startswith("/"):
            # Reset login state on new command unless it's /cancel
            if chat_id in user_login_states and text not in ["/cancel", "/stop"]:
                old_sess = user_login_states.pop(chat_id)
                if old_sess.get("client"):
                    try:
                        await old_sess["client"].disconnect()
                    except Exception:
                        pass

            if text.startswith("/host") or text.startswith("/login"):
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
                await event.reply("📱 **Enter Phone Number (+91xxxxxxxxxx):**")
                return

            # Command: /start
            if text.startswith("/start"):
                buttons = [
                    [Button.inline("📖 Help", data="cmd_help"), Button.inline("✨ Commands", data="cat_main")],
                    [Button.inline("🚀 Host Userbot", data="cmd_host")]
                ]
                await event.reply(WELCOME_TEXT, buttons=buttons)
                return

            # Command: /help
            if text.startswith("/help"):
                buttons = [
                    [Button.inline("✨ Explore Commands", data="cat_main")],
                    [Button.inline("🚀 Host Userbot", data="cmd_host")]
                ]
                await event.reply(HELP_TEXT, buttons=buttons)
                return

            # Command: /commands, /cmds, /command
            if text in ["/commands", "/cmds", "/command"] or text.startswith("/commands") or text.startswith("/cmds"):
                await event.reply(COMMANDS_HEADER, buttons=get_commands_keyboard())
                return

            # Command: /support
            if text.startswith("/support"):
                await event.reply(f"💬 **Support:** Contact @{Config.OWNER_USERNAME} (Fast Response)")
                return

            # Command: /restart
            if text.startswith("/restart"):
                msg = await event.reply("🔄 **Reviving your hosted userbot session...**")
                client = await session_manager.start_user_session(chat_id)
                if client and client.is_connected():
                    await msg.edit("🟢 **Aurora Userbot Revived & Active!**")
                else:
                    await msg.edit("🔴 **No active session found.** Send /host to deploy your userbot.")
                return

            # Command: /supportraid
            if text.startswith("/supportraid"):
                await event.reply("💥 **Pro Support Raid Command:** Ready for Pro / Premium users.")
                return

            # Command: /restartall (Owner Only)
            if text.startswith("/restartall"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                msg = await event.reply("🔄 **Restarting all userbot sessions...**")
                count = await session_manager.load_all_sessions()
                await msg.edit(f"✅ **Restarted `{count}` userbot sessions!**")
                return

            # Command: /refresh (Owner Only)
            if text.startswith("/refresh"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                await event.reply("✨ **Platform state refreshed successfully!**")
                return

            # Command: /status
            if text.startswith("/status"):
                user_client = session_manager.get_active_client(chat_id)
                if user_client and user_client.is_connected():
                    msg = f"🟢 **Aurora Status:** ACTIVE & HOSTED\n🆔 **User ID:** `{chat_id}`"
                else:
                    msg = f"🔴 **Aurora Status:** NOT ACTIVE (Send /host to deploy your userbot)"
                await event.reply(sanitize_text(msg))
                return

            # Command: /logout
            if text.startswith("/logout"):
                user_client = session_manager.get_active_client(chat_id)
                has_db_session = session_manager.get_decrypted_session(chat_id) is not None

                if user_client or has_db_session:
                    await session_manager.revoke_user_session(chat_id)
                    await event.reply("🔒 **Safely Logged Out!**\nYour encrypted session has been revoked and removed from Aurora DB.")
                else:
                    await event.reply("ℹ️ **You are not currently logged in.** Send /host to deploy your userbot.")
                return

            # Command: /listsudousers & /sudolist (Owner Only)
            if text.startswith("/listsudousers") or text.startswith("/sudolist"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Only platform owner can access this menu!**")
                    return
                s_list = "\n".join([f"• `{u}`" for u in SUDO_USERS]) if SUDO_USERS else "• `@tglegend77` (Owner)"
                await event.reply(f"👑 **Sudo / Admin Users List:**\n\n{s_list}")
                return

            # Command: /addsudousers /addsudo (Owner Only)
            if text.startswith("/addsudousers") or text.startswith("/addsudo"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                target = text.replace("/addsudousers", "").replace("/addsudo", "").strip()
                if not target:
                    await event.reply("💡 **Usage:** `/addsudousers <@username or user_id>`")
                    return
                SUDO_USERS.add(target)
                await event.reply(f"👑 **Added Admin/Sudo User:** `{target}`")
                return

            # Command: /removesodousers /rmsudo /removesudouser (Owner Only)
            if text.startswith("/removesodousers") or text.startswith("/rmsudo") or text.startswith("/removesudouser"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                target = text.replace("/removesodousers", "").replace("/rmsudo", "").replace("/removesudouser", "").strip()
                if not target:
                    await event.reply("💡 **Usage:** `/removesodousers <@username or user_id>`")
                    return
                SUDO_USERS.discard(target)
                await event.reply(f"🛑 **Removed Admin/Sudo User:** `{target}`")
                return

            # Command: /listgroups (Admin & Owner)
            if text.startswith("/listgroups"):
                if chat_id not in SUDO_USERS and chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Admin / Owner privileges required.**")
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

            # Command: /gban (Admin & Owner)
            if text.startswith("/gban"):
                if chat_id not in SUDO_USERS and chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Admin / Owner privileges required.**")
                    return
                parts = text.replace("/gban", "").strip().split(maxsplit=1)
                if not parts or not parts[0]:
                    await event.reply("💡 **Usage:** `/gban <@username or user_id> [reason]`")
                    return
                raw_target = parts[0]
                reason = parts[1] if len(parts) > 1 else "Globally Banned by Admin"

                msg = await event.reply(f"⚡ **Initiating Global Ban for:** `{raw_target}`...")
                all_groups = await get_all_platform_groups(bot)
                target_entity = await resolve_target(bot, raw_target)
                GBAN_LIST[str(raw_target).lower()] = reason

                banned_count = 0
                banned_groups = set()
                bot_me = await bot.get_me()

                # Ban across bot groups where bot has ban rights
                for g_id in list(all_groups.keys()):
                    try:
                        perms = await bot.get_permissions(g_id, bot_me)
                        if perms.is_admin and getattr(perms, "ban_users", False):
                            await bot.edit_permissions(g_id, target_entity, view_messages=False)
                            banned_count += 1
                            banned_groups.add(g_id)
                    except Exception as e:
                        LOGS.debug(f"GBan error in bot group {g_id}: {e}")

                # Also ban across active userbots dialogs for remaining groups
                for uid in session_manager.get_all_active_users():
                    u_client = session_manager.get_active_client(uid)
                    if u_client and u_client.is_connected():
                        try:
                            u_me = await u_client.get_me()
                            for g_id in list(all_groups.keys()):
                                if g_id not in banned_groups:
                                    try:
                                        u_perms = await u_client.get_permissions(g_id, u_me)
                                        if u_perms.is_admin and getattr(u_perms, "ban_users", False):
                                            await u_client.edit_permissions(g_id, target_entity, view_messages=False)
                                            banned_count += 1
                                            banned_groups.add(g_id)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                await msg.edit(f"🚫 **Global Ban Executed!**\n\n👤 **Target:** `{raw_target}`\n💬 **Banned in:** `{banned_count}` groups (where bot/userbots have ban rights)\n📝 **Reason:** `{reason}`")
                return

            # Command: /gunban (Admin & Owner)
            if text.startswith("/gunban"):
                if chat_id not in SUDO_USERS and chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Admin / Owner privileges required.**")
                    return
                target = text.replace("/gunban", "").strip()
                if not target:
                    await event.reply("💡 **Usage:** `/gunban <@username or user_id>`")
                    return
                msg = await event.reply(f"⚡ **Initiating Global Unban for:** `{target}`...")

                all_groups = await get_all_platform_groups(bot)
                target_entity = await resolve_target(bot, target)
                GBAN_LIST.pop(str(target).lower(), None)
                GBAN_LIST.pop(str(target), None)

                unbanned_count = 0
                unbanned_groups = set()
                bot_me = await bot.get_me()

                for g_id in list(all_groups.keys()):
                    try:
                        perms = await bot.get_permissions(g_id, bot_me)
                        if perms.is_admin and getattr(perms, "ban_users", False):
                            await bot.edit_permissions(g_id, target_entity, view_messages=True, send_messages=True)
                            unbanned_count += 1
                            unbanned_groups.add(g_id)
                    except Exception as e:
                        LOGS.debug(f"GUnban error in bot group {g_id}: {e}")

                for uid in session_manager.get_all_active_users():
                    u_client = session_manager.get_active_client(uid)
                    if u_client and u_client.is_connected():
                        try:
                            u_me = await u_client.get_me()
                            for g_id in list(all_groups.keys()):
                                if g_id not in unbanned_groups:
                                    try:
                                        u_perms = await u_client.get_permissions(g_id, u_me)
                                        if u_perms.is_admin and getattr(u_perms, "ban_users", False):
                                            await u_client.edit_permissions(g_id, target_entity, view_messages=True, send_messages=True)
                                            unbanned_count += 1
                                            unbanned_groups.add(g_id)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                await msg.edit(f"✅ **Global Unban Executed!**\n\n👤 **Target:** `{target}`\n💬 **Unbanned in:** `{unbanned_count}` groups")
                return

            # Command: /gbanlist (Admin & Owner)
            if text.startswith("/gbanlist"):
                if chat_id not in SUDO_USERS and chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Admin / Owner privileges required.**")
                    return
                if not GBAN_LIST:
                    await event.reply("ℹ️ **No users globally banned.**")
                    return
                res = "🚫 **Globally Banned Users List:**\n\n"
                for u, r in GBAN_LIST.items():
                    res += f"• `{u}` - *{r}*\n"
                await event.reply(res)
                return

            # Command: /gbroadcast (Admin & Owner) - Dual Fallback Broadcast (Bot -> Active Hosted Userbots)
            if text.startswith("/gbroadcast"):
                if chat_id not in SUDO_USERS and chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Admin / Owner privileges required.**")
                    return
                msg_text = text.replace("/gbroadcast", "").strip()
                if not msg_text:
                    await event.reply("💡 **Usage:** `/gbroadcast <message>`")
                    return

                msg = await event.reply("📢 **Sending Global Broadcast across all platform groups...**")

                all_groups = await get_all_platform_groups(bot)
                if not all_groups:
                    await msg.edit("ℹ️ **No active groups recorded across platform to broadcast.**")
                    return

                sent_bot = 0
                sent_ub = 0
                failed = 0

                active_userbots = []
                for uid in session_manager.get_all_active_users():
                    u_client = session_manager.get_active_client(uid)
                    if u_client and u_client.is_connected():
                        active_userbots.append(u_client)

                for g_id in list(all_groups.keys()):
                    success = False
                    # 1. Try sending via Bot Account first
                    try:
                        await bot.send_message(g_id, msg_text)
                        sent_bot += 1
                        success = True
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        LOGS.debug(f"Bot cannot send to group {g_id}: {e}")

                    # 2. If Bot failed, try active Userbots
                    if not success and active_userbots:
                        for u_client in active_userbots:
                            try:
                                await u_client.send_message(g_id, msg_text)
                                sent_ub += 1
                                success = True
                                await asyncio.sleep(0.3)
                                break  # Sent successfully by userbot
                            except Exception as e:
                                LOGS.debug(f"Userbot cannot send to group {g_id}: {e}")

                    if not success:
                        failed += 1

                total_sent = sent_bot + sent_ub
                total_groups = len(all_groups)
                await msg.edit(
                    f"📢 **Global Broadcast Complete!**\n\n"
                    f"🤖 **Sent by Bot Account in:** `{sent_bot}` groups\n"
                    f"⚡ **Sent by Hosted Userbots in:** `{sent_ub}` groups\n"
                    f"❌ **Failed in:** `{failed}` groups\n"
                    f"📊 **Total Groups Reached:** `{total_sent}` / `{total_groups}` groups"
                )
                return

            # Command: /block (Owner Only) - Works by username or user_id
            if text.startswith("/block"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                target = text.replace("/block", "").strip()
                if not target:
                    await event.reply("💡 **Usage:** `/block <@username or user_id>`")
                    return

                b_id = target
                b_name = ""
                try:
                    entity = await bot.get_entity(target)
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
                if b_name:
                    BLOCKED_USERS[b_name.lower()] = info

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

            # Command: /unblock (Owner Only)
            if text.startswith("/unblock"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return
                target = text.replace("/unblock", "").strip()
                if not target:
                    await event.reply("💡 **Usage:** `/unblock <@username or user_id>`")
                    return

                removed = False
                target_lower = target.lower()
                for k in list(BLOCKED_USERS.keys()):
                    if k.lower() == target_lower or str(BLOCKED_USERS[k].get("id")) == target:
                        r_id = BLOCKED_USERS[k].get("id")
                        BLOCKED_USERS.pop(k, None)
                        removed = True
                        try:
                            with db_session() as session:
                                session.query(BlockedUser).filter(
                                    (BlockedUser.user_id == r_id) | (BlockedUser.username == k)
                                ).delete(synchronize_session=False)
                                session.commit()
                        except Exception:
                            pass

                if removed:
                    await event.reply(f"✅ **Unblocked User:** `{target}`")
                else:
                    await event.reply(f"ℹ️ **User `{target}` is not in blocked list.**")
                return

            # Command: /listblock & /blockeduser (Owner Only) - Shows Username & ID
            if text.startswith("/listblock") or text.startswith("/blockeduser"):
                if chat_id != Config.OWNER_ID:
                    await event.reply("⛔ **Owner privileges required.**")
                    return

                unique_blocked = {}
                for info in BLOCKED_USERS.values():
                    unique_blocked[info["id"]] = info.get("username") or "N/A"

                if not unique_blocked:
                    await event.reply("ℹ️ **No users currently blocked.**")
                    return

                res = "🚫 **Blocked Users List:**\n\n"
                for b_id, b_name in unique_blocked.items():
                    res += f"• `{b_name}` (ID: `{b_id}`)\n"
                await event.reply(res)
                return

            # Command: /stats
            if text.startswith("/stats"):
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

        # Userbot Dot Command Handler (.setwelcome, .broadcast, .ping, etc.)
        if text.startswith("."):
            user_client = session_manager.get_active_client(chat_id)
            if not user_client or not user_client.is_connected():
                user_client = await session_manager.start_user_session(chat_id)

            if user_client and user_client.is_connected():
                cmd_name = text.split()[0][1:].lower()
                if cmd_name in ["setwelcome", "setwlcm"]:
                    val = text.replace(f".{cmd_name}", "").strip()
                    if val:
                        from aurora.plugins.welcome import WELCOME_SETTINGS, GLOBAL_WELCOME
                        me = await user_client.get_me()
                        GLOBAL_WELCOME[me.id] = val
                        WELCOME_SETTINGS[chat_id] = val
                        await event.reply(f"🎉 **Custom Welcome Message Set For First DMs & Groups!**\n\n💬 `{val}`")
                    else:
                        await event.reply("❌ **Provide a welcome message.**\n💡 **Example:** `.setwlcm Welcome!`")
                    return
                elif cmd_name == "broadcast":
                    msg_text = text.replace(".broadcast", "").strip()
                    if not msg_text:
                        await event.reply("❌ **Provide message text to broadcast.**\n💡 **Example:** `.broadcast Hello everyone!`")
                        return
                    msg = await event.reply("📢 **Starting global broadcast...**")
                    sent = 0
                    failed = 0
                    async for dialog in user_client.iter_dialogs():
                        if dialog.is_group:
                            try:
                                await user_client.send_message(dialog.id, msg_text)
                                sent += 1
                                await asyncio.sleep(0.4)
                            except Exception:
                                failed += 1
                    await msg.edit(f"📢 **Global Broadcast Complete!**\n\n✅ **Sent to:** `{sent}` groups\n❌ **Failed in:** `{failed}` groups")
                    return
                elif cmd_name == "ping":
                    start = time.time()
                    msg = await event.reply("🏓 **Pinging...**")
                    end = time.time()
                    ms = round((end - start) * 1000, 2)
                    await msg.edit(f"🏓 **Pong!**\n⚡ **Speed:** `{ms} ms`\n🟢 **Userbot Status:** Active")
                    return
                else:
                    return
            else:
                return

        # Onboarding Flow Handler
        if chat_id in user_login_states:
            state = user_login_states[chat_id]
            step = state.get("step")

            if step == "WAITING_PHONE":
                phone = text.replace(" ", "").replace("-", "")
                if not (phone.startswith("+") and phone[1:].isdigit()):
                    await event.reply("❌ **Invalid phone format.** Enter e.g. `+91xxxxxxxxxx`.")
                    return

                state["phone"] = phone
                msg = await event.reply("⏳ **Connecting to Telegram...**")

                client = TelegramClient(
                    StringSession(),
                    Config.API_ID,
                    Config.API_HASH,
                    device_model="Samsung Galaxy S22",
                    system_version="Android 14",
                    app_version="10.8.2",
                    lang_code="en",
                    system_lang_code="en",
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
                await event.respond("📱 **Enter Phone Number (+91xxxxxxxxxx):**")
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
