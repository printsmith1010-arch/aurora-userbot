"""
Aurora Spam & Timed Spam Plugin.

Commands: .spam, .stopspam, .tspam, .cspam, .delayspam, .bigspam
"""

import asyncio
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraSpamPlugin")

plugin_manager.register_command("spam", "spam", "Spams a message multiple times.", f"{Config.COMMAND_HANDLER}spam <count> [chatid] <message> [@username]")
plugin_manager.register_command("stopspam", "spam", "Stops ongoing active spam.", f"{Config.COMMAND_HANDLER}stopspam [id]")
plugin_manager.register_command("tspam", "tspam", "Spam with a time delay.", f"{Config.COMMAND_HANDLER}tspam <time> [chatid/@username] <count> <message>")

ACTIVE_SPAMS = set()


def register_spam_handlers(client):
    """
    Registers spam event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.spam\s+(\d+)(?:\s+([\s\S]+))?"))
    async def spam_handler(event):
        count = int(event.pattern_match.group(1))
        text = event.pattern_match.group(2) or "Hello!"

        chat = event.chat_id
        ACTIVE_SPAMS.add(chat)

        await event.delete()
        for _ in range(count):
            if chat not in ACTIVE_SPAMS:
                break
            await event.respond(text)
            await asyncio.sleep(0.15)

        ACTIVE_SPAMS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stopspam(?:\s+([\s\S]+))?"))
    async def stopspam_handler(event):
        ACTIVE_SPAMS.discard(event.chat_id)
        ACTIVE_SPAMS.clear()
        await event.edit("🛑 **Spam stopped successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.tspam\s+(\d+)\s+(\d+)\s+([\s\S]+)"))
    async def tspam_handler(event):
        delay = int(event.pattern_match.group(1))
        count = int(event.pattern_match.group(2))
        text = event.pattern_match.group(3)

        chat = event.chat_id
        ACTIVE_SPAMS.add(chat)

        await event.delete()
        for _ in range(count):
            if chat not in ACTIVE_SPAMS:
                break
            await event.respond(text)
            await asyncio.sleep(delay)

        ACTIVE_SPAMS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.cspam\s+([\s\S]+)"))
    async def cspam_handler(event):
        text = event.pattern_match.group(1)

        await event.delete()
        for char in text:
            if char.strip():
                await event.respond(char)
                await asyncio.sleep(0.2)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.delayspam\s+(\d+)\s+(\d+)\s+([\s\S]+)"))
    async def delayspam_handler(event):
        delay = int(event.pattern_match.group(1))
        count = int(event.pattern_match.group(2))
        text = event.pattern_match.group(3)

        await event.delete()
        for _ in range(count):
            await event.respond(text)
            await asyncio.sleep(delay)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.bigspam\s+(\d+)\s+([\s\S]+)"))
    async def bigspam_handler(event):
        count = int(event.pattern_match.group(1))
        text = event.pattern_match.group(2)

        await event.delete()
        for _ in range(min(count, 100)):
            await event.respond(text)
            await asyncio.sleep(0.1)
