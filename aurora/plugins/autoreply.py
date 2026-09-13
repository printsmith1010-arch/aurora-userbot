"""
Aurora AutoReply & Nuclear Clear Plugin.

Commands: .autoreply <msg>, .dautoreply, .clearall
"""

import asyncio
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraAutoReplyPlugin")

plugin_manager.register_command("autoreply", "autoreply", "Tag/mention auto-reply message.", f"{Config.COMMAND_HANDLER}autoreply <message>")
plugin_manager.register_command("dautoreply", "autoreply", "Disable tag auto-reply.", f"{Config.COMMAND_HANDLER}dautoreply")
plugin_manager.register_command("clearall", "nuclear", "Nuclear clear history command.", f"{Config.COMMAND_HANDLER}clearall")

TAG_AUTOREPLIES = {}  # me.id -> response string
CLEARALL_CONFIRMS = set()


def register_autoreply_handlers(client):
    """
    Registers Tag AutoReply and ClearAll event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoreply(?:\s+([\s\S]+))?"))
    async def tag_autoreply_handler(event):
        msg_text = event.pattern_match.group(1)
        if not msg_text:
            await event.edit("💡 **Usage:** `.autoreply kaisa hai bhai`")
            return

        me = await client.get_me()
        TAG_AUTOREPLIES[me.id] = msg_text.strip()
        await event.edit(f"🤖 **Tag AutoReply Set!**\n\nWhen tagged/mentioned, will reply:\n💬 `{msg_text.strip()}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.dautoreply$"))
    async def dautoreply_handler(event):
        me = await client.get_me()
        TAG_AUTOREPLIES.pop(me.id, None)
        await event.edit("🤖 **Tag AutoReply Disabled.**")

    @client.on(events.NewMessage(incoming=True))
    async def tag_mention_listener(event):
        if event.is_private:
            return

        me = await client.get_me()
        reply_msg = TAG_AUTOREPLIES.get(me.id)
        if not reply_msg:
            return

        if event.mentioned:
            try:
                await event.reply(reply_msg)
            except Exception as e:
                LOGS.error(f"Tag mention reply error: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.clearall(?:\s+(confirm))?"))
    async def clearall_handler(event):
        confirm = event.pattern_match.group(1)
        if confirm == "confirm":
            msg = await event.edit("☢️ **Initiating Nuclear ClearAll...**")
            deleted_chats = 0
            async for dialog in client.iter_dialogs():
                try:
                    await client.delete_dialog(dialog.id)
                    deleted_chats += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
            await msg.edit(f"☢️ **ClearAll Completed! Deleted `{deleted_chats}` dialog history.**")
        else:
            await event.edit(
                "⚠️ **NUCLEAR CLEARALL WARNING!**\n\n"
                "This will wipe chat history across dialogs.\n"
                "👉 To execute, type: `.clearall confirm`"
            )
