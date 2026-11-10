"""
Aurora Broadcast Plugin.

Commands: .gcast, .gbroadcast, .broadcast, .glist
- .broadcast: Broadcasts from user account to all joined local groups where user is present.
- .gbroadcast / .gcast: Broadcasts from the Telegram Bot Account across all platform groups where the bot is present.
- .glist: Lists all groups where the bot is present and has admin access.
"""

import asyncio
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraBroadcastPlugin")

plugin_manager.register_command("gcast", "bcast", "Broadcasts message via Bot Account to all bot groups (Admin/Owner).", f"{Config.COMMAND_HANDLER}gcast <message>")
plugin_manager.register_command("gbroadcast", "bcast", "Broadcasts message via Bot Account to all bot groups (Admin/Owner).", f"{Config.COMMAND_HANDLER}gbroadcast <message>")
plugin_manager.register_command("broadcast", "bcast", "Broadcasts message from user account to all joined groups.", f"{Config.COMMAND_HANDLER}broadcast <message>")
plugin_manager.register_command("glist", "bcast", "Lists all groups where bot has admin access.", f"{Config.COMMAND_HANDLER}glist")


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

        msg = await event.edit("📢 **Starting user local broadcast across joined groups...**")
        sent = 0
        failed = 0

        processed_chats = set()

        async for dialog in client.iter_dialogs():
            is_grp = dialog.is_group or (dialog.is_channel and getattr(dialog.entity, "megagroup", False))
            if is_grp and dialog.id not in processed_chats:
                processed_chats.add(dialog.id)
                try:
                    if reply:
                        await client.send_message(dialog.id, reply)
                    else:
                        await client.send_message(dialog.id, msg_text)
                    sent += 1
                    await asyncio.sleep(0.4)
                except Exception as e:
                    LOGS.debug(f"Broadcast failed in {dialog.id}: {e}")
                    failed += 1

        await msg.edit(f"📢 **User Broadcast Complete!**\n\n✅ **Sent from your account to:** `{sent}` groups\n❌ **Failed in:** `{failed}` groups")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](gcast|gbroadcast)(?:\s+([\s\S]+))?"))
    async def gbroadcast_handler(event):
        from aurora.bot import execute_global_broadcast, is_admin_or_owner

        me = await client.get_me()
        if not is_admin_or_owner(me.id, me.username):
            await event.edit("⛔ **Owner or Bot Admin privileges required.**")
            return

        reply = await event.get_reply_message()
        msg_text = event.pattern_match.group(2)

        if not msg_text and reply:
            msg_text = reply.text or reply.message

        if not msg_text:
            await event.edit("❌ **Provide message text or reply to broadcast.**\n💡 **Example:** `.gbroadcast Hello everyone!`")
            return

        msg = await event.edit("📢 **Sending Global Broadcast via Bot Account...**")
        res = await execute_global_broadcast(msg_text, reply_msg=reply, event=event)
        await msg.edit(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]glist$"))
    async def glist_handler(event):
        from aurora.bot import get_bot_admin_groups_list, is_admin_or_owner

        me = await client.get_me()
        if not is_admin_or_owner(me.id, me.username):
            await event.edit("⛔ **Owner or Bot Admin privileges required.**")
            return

        msg = await event.edit("⏳ **Checking groups where bot has admin access...**")
        res = await get_bot_admin_groups_list()
        await msg.edit(res)
