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
from aurora.core.session_manager import session_manager

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
plugin_manager.register_command("gban", "admin", "Globally ban a user across all groups.", f"{Config.COMMAND_HANDLER}gban <@username/id> [reason]")
plugin_manager.register_command("gunban", "admin", "Globally unban a user.", f"{Config.COMMAND_HANDLER}gunban <@username/id>")
plugin_manager.register_command("gbanlist", "admin", "List all globally banned users.", f"{Config.COMMAND_HANDLER}gbanlist", aliases=["listgban"])
plugin_manager.register_command("gbroadcast", "admin", "Broadcast message to all bot/userbot groups.", f"{Config.COMMAND_HANDLER}gbroadcast <message>")

SUDO_USERS = set()
GBAN_LIST = {}


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

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.gban(?:\s+([\s\S]+))?"))
    async def gban_handler(event):
        reply = await event.get_reply_message()
        input_str = event.pattern_match.group(1)

        target = None
        reason = "Globally Banned"
        if reply:
            target = reply.sender_id
            if input_str:
                reason = input_str.strip()
        elif input_str:
            parts = input_str.strip().split(maxsplit=1)
            target = parts[0]
            if len(parts) > 1:
                reason = parts[1]

        if not target:
            await event.edit("❌ **Reply to a user or pass @username/ID to GBAN.**")
            return

        msg = await event.edit(f"⚡ **Initiating Global Ban for:** `{target}`...")
        GBAN_LIST[str(target).lower()] = reason

        banned_chats = 0
        me = await client.get_me()
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                try:
                    perms = await client.get_permissions(dialog.id, me)
                    if perms.is_admin and getattr(perms, "ban_users", False):
                        await client.edit_permissions(dialog.id, target, view_messages=False)
                        banned_chats += 1
                except Exception:
                    pass

        await msg.edit(f"🚫 **Global Ban Executed!**\n\n👤 **Target:** `{target}`\n💬 **Banned In:** `{banned_chats}` groups (where bot has ban rights)\n📝 **Reason:** `{reason}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.gunban(?:\s+([\s\S]+))?"))
    async def gunban_handler(event):
        reply = await event.get_reply_message()
        input_str = event.pattern_match.group(1)

        target = None
        if reply:
            target = reply.sender_id
        elif input_str:
            target = input_str.strip()

        if not target:
            await event.edit("❌ **Reply to a user or pass @username/ID to GUNBAN.**")
            return

        msg = await event.edit(f"⚡ **Initiating Global Unban for:** `{target}`...")
        GBAN_LIST.pop(str(target).lower(), None)
        GBAN_LIST.pop(str(target), None)

        unbanned_chats = 0
        me = await client.get_me()
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                try:
                    perms = await client.get_permissions(dialog.id, me)
                    if perms.is_admin and getattr(perms, "ban_users", False):
                        await client.edit_permissions(dialog.id, target, view_messages=True, send_messages=True)
                        unbanned_chats += 1
                except Exception:
                    pass

        await msg.edit(f"✅ **Global Unban Executed!**\n\n👤 **Target:** `{target}`\n💬 **Unbanned In:** `{unbanned_chats}` groups")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(gbanlist|listgban)$"))
    async def gbanlist_handler(event):
        if not GBAN_LIST:
            await event.edit("ℹ️ **No users globally banned.**")
            return

        res = "🚫 **Globally Banned Users List:**\n\n"
        for user, reason in GBAN_LIST.items():
            res += f"• `{user}` - *{reason}*\n"
        await event.edit(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.gbroadcast(?:\s+([\s\S]+))?"))
    async def gbroadcast_handler(event):
        reply = await event.get_reply_message()
        msg_text = event.pattern_match.group(1)

        if not msg_text and reply:
            msg_text = reply.text or reply.message

        if not msg_text:
            await event.edit("❌ **Provide message text or reply to broadcast.**")
            return

        msg = await event.edit("📢 **Sending Global Broadcast across all groups...**")
        sent = 0
        failed = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                try:
                    await client.send_message(dialog.id, msg_text)
                    sent += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    failed += 1

        await msg.edit(f"📢 **Global Broadcast Complete!**\n\n✅ **Sent to:** `{sent}` groups\n❌ **Failed in:** `{failed}` groups")
