"""
Aurora Raid & Reply Raid Plugin.

Commands: .raid, .stopraid, .araid, .sraid, .stopsraid, .replyraid, .dreplyraid, .craid, .setraid
Uses intense Hinglish abusive language for raids.
"""

import asyncio
import random
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraRaidPlugin")

plugin_manager.register_command("raid", "raid", "Raid with Hinglish abusive messages.", f"{Config.COMMAND_HANDLER}raid <count> [chatid] [@username]")
plugin_manager.register_command("stopraid", "raid", "Stop ongoing raid.", f"{Config.COMMAND_HANDLER}stopraid [id]")
plugin_manager.register_command("araid", "araid", "Send abusive words line-by-line.", f"{Config.COMMAND_HANDLER}araid <count> [message_link]")
plugin_manager.register_command("sraid", "sraid", "Send romantic shayari messages.", f"{Config.COMMAND_HANDLER}sraid <count> [username/userid/reply]")
plugin_manager.register_command("stopsraid", "sraid", "Stop shayari raid.", f"{Config.COMMAND_HANDLER}stopsraid")
plugin_manager.register_command("replyraid", "rraid", "Auto-reply with abusive messages when user replies or tags you.", f"{Config.COMMAND_HANDLER}replyraid [username/userid/reply]")
plugin_manager.register_command("dreplyraid", "rraid", "Deactivate reply raid.", f"{Config.COMMAND_HANDLER}dreplyraid [username/userid/reply]")
plugin_manager.register_command("craid", "craid", "Super fast personal raid using messages from channel.", f"{Config.COMMAND_HANDLER}craid <count> (reply)")
plugin_manager.register_command("setraid", "craid", "Set personal raid channel link.", f"{Config.COMMAND_HANDLER}setraid <channel_link>")

HINGLISH_ABUSIVE_RAID_LINES = [
    "teri ma ka bsdk 💥",
    "gand maraye bsdk 🔥",
    "laude ke baal nikal bsdk ⚡",
    "teri behan ki chudai 💥",
    "bsdk ke aukat me reh 🔥",
    "bhadwe ke pille tmkc ⚡",
    "gand me danda daal dunga bsdk 💥",
    "chutiye chal nikal yahan se 🔥",
    "madarchod bhadwe bsdk ⚡",
    "teri ammi ko chhod dunga bsdk 💥",
    "teri gaand tod dunga bsdk ⚡",
    "bhadwe tmkc maderchod 🔥",
    "chutiye ke patthe nikal bsdk 💥"
]

SHAYARI_LINES = [
    "🌹 Tadap ke dekho kisi ke pyar mein, to pata chale ki intazaar kya hota hai...",
    "✨ Teri dosti ne diya sukoon itna, ki har gham bhool gaye hum...",
    "🔥 Mohabbat bhi ek ajeeb sa khel hai, jo haar gaya woh jeet gaya...",
    "💫 Dil se nikli dua hai hamari, zindagani bane tumhari pyari...",
]

ACTIVE_RAIDS = set()
ACTIVE_RRAIDS = set()
PERSONAL_RAID_CHANNELS = {}


def register_raid_handlers(client):
    """
    Registers raid event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]raid\s+(\d+)(?:\s+([\s\S]+))?"))
    async def raid_handler(event):
        count = int(event.pattern_match.group(1))
        target_str = event.pattern_match.group(2)
        reply = await event.get_reply_message()

        target = None
        if reply:
            target = f"[{reply.sender.first_name}](tg://user?id={reply.sender_id})" if reply.sender else reply.sender_id
        elif target_str:
            target = target_str.strip()

        chat = event.chat_id
        ACTIVE_RAIDS.add(chat)

        await event.delete()

        for _ in range(count):
            if chat not in ACTIVE_RAIDS:
                break
            line = random.choice(HINGLISH_ABUSIVE_RAID_LINES)
            if target:
                await event.respond(f"{target} {line}")
            else:
                await event.respond(line)
            await asyncio.sleep(0.2)

        ACTIVE_RAIDS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]araid(?:\s+(\d+))?(?:\s+([\s\S]+))?"))
    async def araid_handler(event):
        count = int(event.pattern_match.group(1) or 10)
        target_str = event.pattern_match.group(2)
        reply = await event.get_reply_message()

        target = None
        if reply:
            target = f"[{reply.sender.first_name}](tg://user?id={reply.sender_id})" if reply.sender else reply.sender_id
        elif target_str:
            target = target_str.strip()

        chat = event.chat_id
        ACTIVE_RAIDS.add(chat)

        await event.delete()
        for _ in range(count):
            if chat not in ACTIVE_RAIDS:
                break
            line = random.choice(HINGLISH_ABUSIVE_RAID_LINES)
            if target:
                await event.respond(f"{target} {line}")
            else:
                await event.respond(line)
            await asyncio.sleep(0.2)

        ACTIVE_RAIDS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]stopraid(?:\s+([\s\S]+))?"))
    async def stopraid_handler(event):
        ACTIVE_RAIDS.discard(event.chat_id)
        ACTIVE_RAIDS.clear()
        await event.edit("🛑 **Raid stopped successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]sraid\s+(\d+)(?:\s+([\s\S]+))?"))
    async def sraid_handler(event):
        count = int(event.pattern_match.group(1))
        target_str = event.pattern_match.group(2)

        chat = event.chat_id
        ACTIVE_RAIDS.add(chat)

        await event.delete()
        for _ in range(count):
            if chat not in ACTIVE_RAIDS:
                break
            line = random.choice(SHAYARI_LINES)
            if target_str:
                await event.respond(f"{target_str} {line}")
            else:
                await event.respond(line)
            await asyncio.sleep(0.3)

        ACTIVE_RAIDS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]stopsraid$"))
    async def stopsraid_handler(event):
        ACTIVE_RAIDS.discard(event.chat_id)
        await event.edit("🛑 **Shayari raid stopped successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](replyraid|rraid)(?:\s+([\s\S]+))?"))
    async def replyraid_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(2)

        target_id = None
        if reply:
            target_id = reply.sender_id
        elif target_str:
            try:
                entity = await client.get_entity(target_str.strip())
                target_id = entity.id
            except Exception:
                pass

        if not target_id:
            await event.edit("❌ **Reply to a user or pass username to enable reply raid.**")
            return

        ACTIVE_RRAIDS.add(target_id)
        await event.edit(f"🎯 **Hinglish Reply Raid Activated On User:** `{target_id}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](dreplyraid|drraid)(?:\s+([\s\S]+))?"))
    async def dreplyraid_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(2)

        target_id = None
        if reply:
            target_id = reply.sender_id
        elif target_str:
            try:
                entity = await client.get_entity(target_str.strip())
                target_id = entity.id
            except Exception:
                pass

        if target_id and target_id in ACTIVE_RRAIDS:
            ACTIVE_RRAIDS.remove(target_id)
            await event.edit(f"🛑 **Reply Raid Deactivated For User:** `{target_id}`")
        else:
            ACTIVE_RRAIDS.clear()
            await event.edit("🛑 **All Active Reply Raids Stopped.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]setraid\s+([\s\S]+)"))
    async def setraid_handler(event):
        link = event.pattern_match.group(1).strip()
        me = await client.get_me()
        PERSONAL_RAID_CHANNELS[me.id] = link
        await event.edit(f"⚡ **Personal Raid Channel Set To:** `{link}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]craid\s+(\d+)"))
    async def craid_handler(event):
        count = int(event.pattern_match.group(1))
        await event.delete()
        for _ in range(count):
            line = random.choice(HINGLISH_ABUSIVE_RAID_LINES)
            await event.respond(f"⚡ {line}")
            await asyncio.sleep(0.1)

    @client.on(events.NewMessage(incoming=True))
    async def rraid_listener(event):
        if event.sender_id in ACTIVE_RRAIDS:
            line = random.choice(HINGLISH_ABUSIVE_RAID_LINES)
            try:
                await event.reply(line)
            except Exception as e:
                LOGS.error(f"Reply raid error: {e}")
