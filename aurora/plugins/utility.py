"""
Aurora Utility & General Commands Plugin.

Commands: .ping, .uptime, .info, .logout, .alive, .id
"""

import time
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager
from aurora.core.session_manager import session_manager

plugin_manager.register_command("ping", "general", "Check bot speed.", f"{Config.COMMAND_HANDLER}ping")
plugin_manager.register_command("uptime", "general", "Check uptime.", f"{Config.COMMAND_HANDLER}uptime")
plugin_manager.register_command("info", "general", "Get user/chat info.", f"{Config.COMMAND_HANDLER}info [@username/ID]")
plugin_manager.register_command("logout", "general", "Logout userbot.", f"{Config.COMMAND_HANDLER}logout")


async def respond_or_edit(event, text):
    """Edits event if outgoing, otherwise replies."""
    is_out = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False)
    if is_out:
        try:
            await event.edit(text)
            return
        except Exception:
            pass
    await event.reply(text)


async def get_user_entity_robust(client, target):
    """
    Robustly gets Telethon User/Chat object for target (entity, int ID, username, or reply).
    """
    if not target:
        return None

    if hasattr(target, "id") and (hasattr(target, "first_name") or hasattr(target, "title")):
        return target

    # 1. Try direct get_entity
    try:
        return await client.get_entity(target)
    except Exception:
        pass

    target_str = str(target).strip()

    # 2. Try with @ prefix if username string
    if not target_str.lstrip("-").isdigit():
        uname = target_str if target_str.startswith("@") else f"@{target_str}"
        try:
            return await client.get_entity(uname)
        except Exception:
            pass

    # 3. If numeric ID
    if target_str.lstrip("-").isdigit():
        uid = int(target_str)
        try:
            input_ent = await client.get_input_entity(uid)
            return await client.get_entity(input_ent)
        except Exception:
            pass

        try:
            async for dialog in client.iter_dialogs(limit=200):
                if dialog.id == uid or getattr(dialog.entity, "id", None) == uid:
                    return dialog.entity
        except Exception:
            pass

    return None


def register_utility_handlers(client):
    """
    Registers utility event handlers on client.
    """

    @client.on(events.NewMessage(pattern=r"^[./]alive$"))
    async def alive_handler(event):
        me = await event.client.get_me()
        user_str = f"@{me.username}" if me.username else me.first_name

        alive_text = (
            "🌟 **Aurora Multi-User Userbot is ALIVE & ACTIVE!** 🌟\n\n"
            f"👤 **Account:** {user_str}\n"
            f"🆔 **Telegram ID:** `{me.id}`\n"
            f"🔒 **Session Mode:** Isolated & AES-256 Encrypted\n"
            f"⚡ **Platform:** Aurora v3.4.0 Multi-User"
        )
        await respond_or_edit(event, alive_text)

    @client.on(events.NewMessage(pattern=r"^[./]ping$"))
    async def ping_handler(event):
        start = time.time()
        is_out = getattr(event, "out", False) or getattr(getattr(event, "message", None), "out", False)
        msg = await event.reply("🏓 **Pinging...**") if not is_out else None
        if is_out:
            await event.edit("🏓 **Pinging...**")
        end = time.time()
        ms = round((end - start) * 1000, 2)
        res = f"🏓 **Pong!**\n⚡ **Speed:** `{ms} ms`"
        if is_out:
            await event.edit(res)
        elif msg:
            await msg.edit(res)

    @client.on(events.NewMessage(pattern=r"^[./]uptime$"))
    async def uptime_handler(event):
        await respond_or_edit(event, "⏳ **Uptime:** Active & Operational")

    @client.on(events.NewMessage(pattern=r"^[./]info(?:\s+([\s\S]+))?"))
    async def info_handler(event):
        reply = await event.get_reply_message()
        query = event.pattern_match.group(1)

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
            if event.is_private:
                me = await client.get_me()
                if event.chat_id != me.id:
                    try:
                        target = await event.get_chat()
                    except Exception:
                        target = event.chat_id
                else:
                    target = me
            else:
                try:
                    target = await event.get_sender() or event.sender_id
                except Exception:
                    target = event.sender_id

        user = await get_user_entity_robust(client, target)
        if not user and target:
            try:
                user = await client.get_entity(target)
            except Exception:
                pass

        if user:
            # Check if entity is a Chat/Channel/Supergroup
            if getattr(user, "title", None) and getattr(user, "first_name", None) is None:
                title = getattr(user, "title", "Group/Channel")
                chat_id = user.id
                username = f"@{user.username}" if getattr(user, "username", None) else "None"
                members_count = getattr(user, "participants_count", "Unknown")
                await respond_or_edit(
                    event,
                    f"💬 **Chat / Channel Info:**\n\n"
                    f"📛 **Title:** `{title}`\n"
                    f"🆔 **ID:** `{chat_id}`\n"
                    f"🏷️ **Username:** {username}\n"
                    f"👥 **Members:** `{members_count}`"
                )
                return

            name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip() or "Unknown"
            username = f"@{user.username}" if getattr(user, "username", None) else "None"
            user_id = getattr(user, "id", "Unknown")
            is_bot = getattr(user, "bot", False)
            is_premium = getattr(user, "premium", False)
            is_verified = getattr(user, "verified", False)
            is_scam = getattr(user, "scam", False)

            bio = "None"
            common_chats = "0"
            try:
                from telethon.tl.functions.users import GetFullUserRequest
                full_user = await client(GetFullUserRequest(user))
                full_info = getattr(full_user, "full_user", None)
                if full_info:
                    bio = full_info.about or "None"
                    common_chats = str(getattr(full_info, "common_chats_count", 0))
            except Exception:
                pass

            dc_id = "Unknown"
            if getattr(user, "photo", None):
                dc_id = str(getattr(user.photo, "dc_id", "Unknown"))

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
            await respond_or_edit(event, info_text)
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
            await respond_or_edit(event, info_text)

    @client.on(events.NewMessage(pattern=r"^[./]id(?:\s+([\s\S]+))?"))
    async def id_handler(event):
        reply = await event.get_reply_message()
        chat_id = event.chat_id
        msg_id = event.id

        text = f"💬 **Chat ID:** `{chat_id}`\n📩 **Message ID:** `{msg_id}`\n"
        if reply:
            text += f"👤 **Replied User ID:** `{reply.sender_id}`\n"
            text += f"📄 **Replied Message ID:** `{reply.id}`\n"

        await respond_or_edit(event, text)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]logout$"))
    async def userbot_logout_handler(event):
        me = await client.get_me()
        await respond_or_edit(event, "🔒 **Logging out userbot...**")
        await session_manager.revoke_user_session(me.id)

