"""
Aurora AntiSafe Shield & Approval Plugin.

Commands: .antisafe on/off, .approve, .disapprove
"""

import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraPMGuardPlugin")

plugin_manager.register_command("antisafe", "antisafe", "Turn on/off hardcore DM protection.", f"{Config.COMMAND_HANDLER}antisafe on/off")
plugin_manager.register_command("approve", "approve", "Save any user from AntiSafe deletion.", f"{Config.COMMAND_HANDLER}approve")
plugin_manager.register_command("disapprove", "approve", "Disapprove user for DM.", f"{Config.COMMAND_HANDLER}disapprove")

ANTISAFE_ACTIVE = {}  # me.id -> bool
APPROVED_USERS = {}   # me.id -> set(user_ids)


def register_pmguard_handlers(client):
    """
    Registers AntiSafe and approval handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]antisafe(?:\s+(on|off))?"))
    async def antisafe_handler(event):
        mode = event.pattern_match.group(1)
        me = await client.get_me()

        if mode == "on":
            ANTISAFE_ACTIVE[me.id] = True
            await event.edit("🛡️ **AntiSafe Hardcore Shield: ACTIVATED!**\n\nAll non-approved incoming DMs will be automatically deleted.")
        elif mode == "off":
            ANTISAFE_ACTIVE[me.id] = False
            await event.edit("🛡️ **AntiSafe Shield: DEACTIVATED**\n\nNormal DM mode active.")
        else:
            status = "ACTIVE" if ANTISAFE_ACTIVE.get(me.id) else "INACTIVE"
            await event.edit(f"🛡️ **AntiSafe Shield Status:** `{status}`\n💡 **Usage:** `.antisafe on` | `.antisafe off`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]approve$"))
    async def approve_handler(event):
        if not event.is_private:
            await event.edit("❌ **Use this command in a private chat.**")
            return

        me = await client.get_me()
        if me.id not in APPROVED_USERS:
            APPROVED_USERS[me.id] = set()

        user_id = event.chat_id
        APPROVED_USERS[me.id].add(user_id)
        await event.edit("✅ **User approved! Saved from AntiSafe deletion.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]disapprove$"))
    async def disapprove_handler(event):
        if not event.is_private:
            await event.edit("❌ **Use this command in a private chat.**")
            return

        me = await client.get_me()
        if me.id in APPROVED_USERS:
            APPROVED_USERS[me.id].discard(event.chat_id)

        await event.edit("🚫 **User disapproved.**")

    @client.on(events.NewMessage(incoming=True))
    async def antisafe_listener(event):
        if not event.is_private:
            return

        me = await client.get_me()
        if not ANTISAFE_ACTIVE.get(me.id):
            return

        sender_id = event.sender_id
        if not sender_id or sender_id == me.id:
            return

        approved_set = APPROVED_USERS.get(me.id, set())
        if sender_id not in approved_set:
            try:
                await event.delete()
                LOGS.info(f"AntiSafe deleted incoming DM from non-approved user {sender_id}")
            except Exception as e:
                LOGS.error(f"AntiSafe delete error: {e}")
