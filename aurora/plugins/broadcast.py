"""
Aurora Broadcast Plugin.

Commands: .gcast, .broadcast
Broadcasts a message exactly once to all distinct groups.
"""

import asyncio
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraBroadcastPlugin")

plugin_manager.register_command("gcast", "bcast", "Broadcasts message once to all groups.", f"{Config.COMMAND_HANDLER}gcast <message>")
plugin_manager.register_command("broadcast", "bcast", "Broadcasts a message to all groups where messaging is allowed.", f"{Config.COMMAND_HANDLER}broadcast <message>")


def register_broadcast_handlers(client):
    """
    Registers broadcast event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]broadcast(?:\s+([\s\S]+))?"))
    async def broadcast_handler(event):
        reply = await event.get_reply_message()
        msg_text = event.pattern_match.group(1)

        if not msg_text and reply:
            msg_text = reply.text or reply.message

        if not msg_text:
            await event.edit("❌ **Provide message text or reply to a message to broadcast.**\n💡 **Example:** `.broadcast Hello everyone!`")
            return

        msg = await event.edit("📢 **Starting userbot local broadcast...**")
        sent = 0
        failed = 0

        processed_chats = set()

        async for dialog in client.iter_dialogs():
            if dialog.is_group and dialog.id not in processed_chats:
                processed_chats.add(dialog.id)
                try:
                    if reply:
                        await client.send_message(dialog.id, reply)
                    else:
                        await client.send_message(dialog.id, msg_text)
                    sent += 1
                    await asyncio.sleep(0.4)
                except Exception:
                    failed += 1

        await msg.edit(f"📢 **Broadcast Complete!**\n\n✅ **Sent to:** `{sent}` groups\n❌ **Failed in:** `{failed}` groups")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](gcast|gbroadcast)(?:\s+([\s\S]+))?"))
    async def gbroadcast_handler(event):
        from aurora.bot import execute_global_broadcast

        reply = await event.get_reply_message()
        msg_text = event.pattern_match.group(2)

        if not msg_text and reply:
            msg_text = reply.text or reply.message

        if not msg_text:
            await event.edit("❌ **Provide message text or reply to broadcast.**\n💡 **Example:** `.gcast Hello everyone!`")
            return

        msg = await event.edit("📢 **Sending Global Broadcast across Aurora platform...**")
        res = await execute_global_broadcast(msg_text, reply_msg=reply, event=event)
        await msg.edit(res)
