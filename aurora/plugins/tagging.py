"""
Aurora Tagging & Member Mention Plugin.

Commands: .tagall, .stoptagall, .canceltag, .adminstag
"""

import asyncio
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraTaggingPlugin")

plugin_manager.register_command("tagall", "tagging", "Tag all group members.", f"{Config.COMMAND_HANDLER}tagall")
plugin_manager.register_command("stoptagall", "tagging", "Stop tagall.", f"{Config.COMMAND_HANDLER}stoptagall [id]")
plugin_manager.register_command("adminstag", "tagging", "Tag all group administrators.", f"{Config.COMMAND_HANDLER}adminstag [msg]")

CANCEL_TAGS = set()


def register_tagging_handlers(client):
    """
    Registers tagging event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.tagall(?:\s+([\s\S]+))?"))
    async def tagall_handler(event):
        if not event.is_group:
            await event.edit("❌ **This command can only be used in groups.**")
            return

        msg_text = event.pattern_match.group(1) or "Hey everyone!"
        await event.delete()

        CANCEL_TAGS.discard(event.chat_id)

        mentions = []
        async for user in client.iter_participants(event.chat_id):
            if event.chat_id in CANCEL_TAGS:
                break
            if user.bot:
                continue

            first_name = user.first_name or "Member"
            mentions.append(f"[{first_name}](tg://user?id={user.id})")

            if len(mentions) == 5:
                tag_text = f"🔔 **{msg_text}**\n\n" + " ".join(mentions)
                await event.respond(tag_text)
                mentions.clear()
                await asyncio.sleep(1.5)

        if mentions and event.chat_id not in CANCEL_TAGS:
            tag_text = f"🔔 **{msg_text}**\n\n" + " ".join(mentions)
            await event.respond(tag_text)

        CANCEL_TAGS.discard(event.chat_id)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(stoptagall|canceltag)(?:\s+([\s\S]+))?"))
    async def canceltag_handler(event):
        CANCEL_TAGS.add(event.chat_id)
        await event.edit("🛑 **Tagging process stopped for this chat.**")
