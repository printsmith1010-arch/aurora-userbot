"""
Aurora Group Administration & Sudo Plugin.

Commands: .ban, .unban, .mute, .unmute, .kick, .clear, .rmall, /invall, .add, .addsudo, .rmsudo, .activeusers, .gban, .gunban, .gbanlist, .gbroadcast
"""

import asyncio
import logging
from telethon import events
from telethon.tl.functions.channels import InviteToChannelRequest
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager
from aurora.core.session_manager import session_manager
from aurora.db.models import GBanUser, ApprovedGroupUser
from aurora.db.session import db_session
from aurora.plugins.utility import respond_or_edit

LOGS = logging.getLogger("AuroraAdminPlugin")

plugin_manager.register_command("ban", "moderation", "Ban a user.", f"{Config.COMMAND_HANDLER}ban @username [reason]")
plugin_manager.register_command("unban", "moderation", "Unban a user.", f"{Config.COMMAND_HANDLER}unban @username")
plugin_manager.register_command("mute", "moderation", "Mute a user.", f"{Config.COMMAND_HANDLER}mute @username [time] [reason]")
plugin_manager.register_command("unmute", "moderation", "Unmute a user.", f"{Config.COMMAND_HANDLER}unmute @username")
plugin_manager.register_command("kick", "moderation", "Kick a user.", f"{Config.COMMAND_HANDLER}kick @username [reason]")
plugin_manager.register_command("clear", "moderation", "Delete messages.", f"{Config.COMMAND_HANDLER}clear <count>")
plugin_manager.register_command("rmall", "moderation", "Remove all members.", f"{Config.COMMAND_HANDLER}rmall")
plugin_manager.register_command("add", "moderation", "Add users to group.", f"{Config.COMMAND_HANDLER}add @username")
plugin_manager.register_command("addsudo", "admin", "Add a sudo user (owner only).", f"{Config.COMMAND_HANDLER}addsudo @username", aliases=["addsudousers"])
plugin_manager.register_command("rmsudo", "admin", "Remove sudo user.", f"{Config.COMMAND_HANDLER}rmsudo @username", aliases=["removesodousers", "removesudouser"])
plugin_manager.register_command("activeusers", "admin", "Show active userbots.", f"{Config.COMMAND_HANDLER}activeusers")
plugin_manager.register_command("adminlist", "admin", "List all sudo/admin users.", f"{Config.COMMAND_HANDLER}adminlist", aliases=["sudolist", "listsudousers"])
plugin_manager.register_command("gban", "admin", "Globally ban a user across all groups.", f"{Config.COMMAND_HANDLER}gban <@username/id> [reason]")
plugin_manager.register_command("gunban", "admin", "Globally unban a user.", f"{Config.COMMAND_HANDLER}gunban <@username/id>")
plugin_manager.register_command("gbanlist", "admin", "List all globally banned users.", f"{Config.COMMAND_HANDLER}gbanlist", aliases=["listgban"])
plugin_manager.register_command("gbroadcast", "admin", "Broadcast message to all bot/userbot groups.", f"{Config.COMMAND_HANDLER}gbroadcast <message>")
plugin_manager.register_command("gapprove", "admin", "Exempt user from GBAN auto-ban in group.", f"{Config.COMMAND_HANDLER}gapprove <@username/id>")
plugin_manager.register_command("gdisapprove", "admin", "Remove GBAN exemption in group and re-ban if gbanned.", f"{Config.COMMAND_HANDLER}gdisapprove <@username/id>", aliases=["gunapprove"])

SUDO_USERS = set()


def register_admin_handlers(client):
    """
    Registers admin, gban, gbroadcast, and sudo event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ban(?:\s+([\s\S]+))?"))
    async def ban_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif target_str:
            target = target_str.split()[0].strip()

        if not target:
            await event.edit("❌ **Reply to a user or specify @username to ban.**")
            return

        try:
            await client.edit_permissions(event.chat_id, target, view_messages=False)
            await event.edit(f"🚫 **Banned user:** `{target}`")
        except Exception as e:
            await event.edit(f"❌ **Ban failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unban(?:\s+([\s\S]+))?"))
    async def unban_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif target_str:
            target = target_str.strip()

        if not target:
            await event.edit("❌ **Specify @username or reply to unban.**")
            return

        try:
            await client.edit_permissions(event.chat_id, target, view_messages=True, send_messages=True)
            await event.edit(f"✅ **Unbanned user:** `{target}`")
        except Exception as e:
            await event.edit(f"❌ **Unban failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.mute(?:\s+([\s\S]+))?"))
    async def mute_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif target_str:
            target = target_str.split()[0].strip()

        if not target:
            await event.edit("❌ **Specify @username or reply to mute.**")
            return

        try:
            await client.edit_permissions(event.chat_id, target, send_messages=False)
            await event.edit(f"🤐 **Muted user:** `{target}`")
        except Exception as e:
            await event.edit(f"❌ **Mute failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unmute(?:\s+([\s\S]+))?"))
    async def unmute_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif target_str:
            target = target_str.strip()

        if not target:
            await event.edit("❌ **Specify @username or reply to unmute.**")
            return

        try:
            await client.edit_permissions(event.chat_id, target, send_messages=True)
            await event.edit(f"🔊 **Unmuted user:** `{target}`")
        except Exception as e:
            await event.edit(f"❌ **Unmute failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.kick(?:\s+([\s\S]+))?"))
    async def kick_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif target_str:
            target = target_str.split()[0].strip()

        if not target:
            await event.edit("❌ **Specify @username or reply to kick.**")
            return

        try:
            await client.kick_participant(event.chat_id, target)
            await event.edit(f"👢 **Kicked user:** `{target}`")
        except Exception as e:
            await event.edit(f"❌ **Kick failed:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.clear\s+(\d+)"))
    async def clear_handler(event):
        count = int(event.pattern_match.group(1))
        async for msg in client.iter_messages(event.chat_id, limit=count + 1):
            try:
                await msg.delete()
            except Exception:
                pass

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.add\s+([\s\S]+)"))
    async def add_handler(event):
        users_str = event.pattern_match.group(1).split()
        added = 0
        for u in users_str:
            try:
                await client(InviteToChannelRequest(event.chat_id, [u.strip()]))
                added += 1
            except Exception:
                pass
        await event.edit(f"✅ **Added {added} user(s) to group!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(addsudo|addsudousers)\s+([\s\S]+)"))
    async def addsudo_handler(event):
        user_str = event.pattern_match.group(2).strip()
        SUDO_USERS.add(user_str)
        await event.edit(f"👑 **Added `{user_str}` to Sudo/Admin list!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(rmsudo|removesodousers|removesudouser)\s+([\s\S]+)"))
    async def rmsudo_handler(event):
        user_str = event.pattern_match.group(2).strip()
        SUDO_USERS.discard(user_str)
        await event.edit(f"🗑️ **Removed `{user_str}` from Sudo/Admin list.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.activeusers$"))
    async def activeusers_handler(event):
        active = session_manager.get_all_active_users()
        await event.edit(f"👥 **Active Hosted Userbots:** `{len(active)}` online")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.gapprove(?:\s+([\s\S]+))?"))
    async def gapprove_handler(event):
        from aurora.bot import APPROVED_USERS_PER_GROUP
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = str(reply.sender_id)
        elif target_str:
            target = target_str.split()[0].strip()

        if not target:
            await event.edit("💡 **Usage:** Reply to a user or type `.gapprove <@username or user_id>`")
            return

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
            await client.edit_permissions(event.chat_id, target, view_messages=True, send_messages=True)
        except Exception:
            pass

        await event.edit(
            f"✅ **User Approved for this Group!**\n\n"
            f"👤 **Target:** `{target}`\n"
            f"🛡️ *This user is exempted from GBAN auto-ban in this group.*"
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(gdisapprove|gunapprove)(?:\s+([\s\S]+))?"))
    async def gdisapprove_handler(event):
        from aurora.bot import APPROVED_USERS_PER_GROUP, GBAN_LIST
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(2)

        target = None
        if reply:
            target = str(reply.sender_id)
        elif target_str:
            target = target_str.split()[0].strip()

        if not target:
            await event.edit("💡 **Usage:** Reply to a user or type `.gdisapprove <@username or user_id>`")
            return

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
        is_gbanned = (
            t_key in GBAN_LIST or
            t_norm in GBAN_LIST or
            f"@{t_norm}" in GBAN_LIST
        )
        if is_gbanned:
            try:
                await client.edit_permissions(event.chat_id, target, view_messages=False)
                banned_again = True
            except Exception:
                try:
                    await client.kick_participant(event.chat_id, target)
                    banned_again = True
                except Exception:
                    pass

        if banned_again:
            await event.edit(
                f"🛑 **User Disapproved & Banned!**\n\n"
                f"👤 **Target:** `{target}`\n"
                f"⚠️ *Group exemption removed. Target is globally banned and has been banned again from this group.*"
            )
        else:
            await event.edit(
                f"🛑 **User Disapproved for this Group!**\n\n"
                f"👤 **Target:** `{target}`\n"
                f"⚠️ *Group exemption removed.*"
            )

    @client.on(events.NewMessage(pattern=r"^[./]gban(?:\s+([\s\S]+))?"))
    async def gban_handler(event):
        from aurora.bot import execute_global_ban, SUDO_USERS, resolve_gban_event_target
        is_allowed = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False) or event.sender_id == Config.OWNER_ID or event.sender_id in SUDO_USERS or str(event.sender_id) in SUDO_USERS
        if not is_allowed:
            return

        input_str = event.pattern_match.group(1)
        target, target_entity, reason = await resolve_gban_event_target(client, event, input_str)

        if not target:
            await respond_or_edit(event, "❌ **Reply to a message, specify @username/ID, or use in DM.**\n💡 **Usage:** `.gban <@username/id> [reason]`")
            return

        msg = await respond_or_edit(event, f"⚡ **Initiating Global Ban for:** `{target}`...")
        res = await execute_global_ban(target, target_entity=target_entity, reason=reason)
        is_out = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False)
        if is_out:
            await event.edit(res)
        elif msg:
            await msg.edit(res)
        else:
            await event.reply(res)

    @client.on(events.NewMessage(pattern=r"^[./]gunban(?:\s+([\s\S]+))?"))
    async def gunban_handler(event):
        from aurora.bot import execute_global_unban, SUDO_USERS, resolve_gunban_event_target
        is_allowed = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False) or event.sender_id == Config.OWNER_ID or event.sender_id in SUDO_USERS or str(event.sender_id) in SUDO_USERS
        if not is_allowed:
            return

        input_str = event.pattern_match.group(1)
        target, target_entity = await resolve_gunban_event_target(client, event, input_str)

        if not target:
            await respond_or_edit(event, "❌ **Reply to a message, specify @username/ID, or use in DM.**\n💡 **Usage:** `.gunban <@username/id>`")
            return

        msg = await respond_or_edit(event, f"⚡ **Initiating Global Unban for:** `{target}`...")
        res = await execute_global_unban(target, target_entity=target_entity)
        is_out = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False)
        if is_out:
            await event.edit(res)
        elif msg:
            await msg.edit(res)
        else:
            await event.reply(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(gbanlist|listgban)$"))
    async def gbanlist_handler(event):
        from aurora.bot import get_formatted_gban_list
        res = await get_formatted_gban_list(client)
        await event.edit(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(adminlist|sudolist|listsudousers)$"))
    async def adminlist_handler(event):
        from aurora.bot import get_formatted_admin_list
        res = await get_formatted_admin_list(client)
        await event.edit(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]gbroadcast(?:\s+([\s\S]+))?"))
    async def gbroadcast_handler(event):
        from aurora.bot import execute_global_broadcast
        reply = await event.get_reply_message()
        msg_text = event.pattern_match.group(1)

        if not msg_text and reply:
            msg_text = reply.text or reply.message

        if not msg_text:
            await event.edit("❌ **Provide message text or reply to broadcast.**")
            return

        msg = await event.edit("📢 **Sending Global Broadcast across Aurora platform...**")
        res = await execute_global_broadcast(msg_text, reply_msg=reply, event=event)
        await msg.edit(res)

    @client.on(events.NewMessage(incoming=True))
    async def gban_auto_ban_handler(event):
        if not (event.is_group or (event.is_channel and getattr(event.chat, "megagroup", False))):
            return

        from aurora.bot import GBAN_LIST, APPROVED_USERS_PER_GROUP
        if not GBAN_LIST:
            return

        sender_id_str = str(event.sender_id)
        sender_obj = None
        try:
            sender_obj = await event.get_sender()
        except Exception:
            pass
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
                await event.delete()
            except Exception:
                pass

            try:
                await client.edit_permissions(event.chat_id, event.sender_id, view_messages=False)
            except Exception:
                pass

    @client.on(events.ChatAction)
    async def gban_join_auto_ban_handler(event):
        if not (event.is_group or (event.is_channel and getattr(event.chat, "megagroup", False))):
            return

        from aurora.bot import GBAN_LIST, APPROVED_USERS_PER_GROUP
        if not GBAN_LIST:
            return

        if event.user_joined or event.user_added:
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

                        try:
                            await client.edit_permissions(event.chat_id, user.id, view_messages=False)
                        except Exception:
                            try:
                                await client.kick_participant(event.chat_id, user.id)
                            except Exception:
                                pass
            except Exception:
                pass

