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
plugin_manager.register_command("info", "general", "Get user/chat info.", f"{Config.COMMAND_HANDLER}info [@username]")
plugin_manager.register_command("logout", "general", "Logout userbot.", f"{Config.COMMAND_HANDLER}logout")


def register_utility_handlers(client):
    """
    Registers utility event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.alive$"))
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
        await event.edit(alive_text)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
    async def ping_handler(event):
        start = time.time()
        await event.edit("🏓 **Pinging...**")
        end = time.time()
        ms = round((end - start) * 1000, 2)
        await event.edit(f"🏓 **Pong!**\n⚡ **Speed:** `{ms} ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.uptime$"))
    async def uptime_handler(event):
        await event.edit("⏳ **Uptime:** Active & Operational")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.info(?:\s+([\s\S]+))?"))
    async def info_handler(event):
        reply = await event.get_reply_message()
        query = event.pattern_match.group(1)

        user = None
        if reply:
            user = await reply.get_sender()
        elif query:
            try:
                user = await client.get_entity(query.strip())
            except Exception:
                pass
        else:
            user = await client.get_me()

        if user:
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            username = f"@{user.username}" if getattr(user, "username", None) else "None"
            await event.edit(
                f"👤 **User Info:**\n\n"
                f"📛 **Name:** {name}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"🏷️ **Username:** {username}\n"
                f"🤖 **Is Bot:** `{user.bot}`"
            )
        else:
            await event.edit("❌ **User info not found.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.id(?:\s+([\s\S]+))?"))
    async def id_handler(event):
        reply = await event.get_reply_message()
        chat_id = event.chat_id
        msg_id = event.id

        text = f"💬 **Chat ID:** `{chat_id}`\n📩 **Message ID:** `{msg_id}`\n"
        if reply:
            text += f"👤 **Replied User ID:** `{reply.sender_id}`\n"
            text += f"📄 **Replied Message ID:** `{reply.id}`\n"

        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.logout$"))
    async def userbot_logout_handler(event):
        me = await client.get_me()
        await event.edit("🔒 **Logging out userbot...**")
        await session_manager.revoke_user_session(me.id)
