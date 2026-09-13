"""
Aurora Welcome & DM Onboarding Plugin.

Commands: .setwlcm, .setwelcome, .stopwlcm, .stopwelcome, .wlcmmssg, .clearwelcome
Auto-sends custom welcome message on first incoming DM or group join.
"""

import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraWelcomePlugin")

plugin_manager.register_command("setwlcm", "welcome", "Sets custom welcome message for DMs & groups.", f"{Config.COMMAND_HANDLER}setwlcm <message>")
plugin_manager.register_command("stopwlcm", "welcome", "Disables welcome message.", f"{Config.COMMAND_HANDLER}stopwlcm")
plugin_manager.register_command("wlcmmssg", "welcome", "Resets welcome message.", f"{Config.COMMAND_HANDLER}wlcmmssg")

# Per userbot account settings
# GLOBAL_WELCOME[me.id] = welcome_text
GLOBAL_WELCOME = {}

# WELCOME_SETTINGS[chat_id] = welcome_text
WELCOME_SETTINGS = {}

# Track users greeted per userbot: GREETED_USERS[me.id] = set(sender_ids)
GREETED_USERS = {}


def register_welcome_handlers(client):
    """
    Registers DM and Group welcome event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(setwlcm|setwelcome)(?:\s+([\s\S]+))?"))
    async def setwelcome_handler(event):
        msg = event.pattern_match.group(2)
        reply = await event.get_reply_message()

        if not msg and reply:
            msg = reply.raw_text

        if not msg:
            await event.edit("❌ **Provide a welcome message or reply to a message.**\n💡 **Example:** `.setwlcm Welcome!`")
            return

        me = await client.get_me()
        GLOBAL_WELCOME[me.id] = msg
        WELCOME_SETTINGS[event.chat_id] = msg

        # Reset greeted users list for new welcome message
        GREETED_USERS[me.id] = set()

        await event.edit(f"🎉 **Custom Welcome Message Set For First DMs & Group Joins!**\n\n💬 `{msg}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(stopwlcm|clearwelcome|stopwelcome|wlcmmssg)$"))
    async def clearwelcome_handler(event):
        me = await client.get_me()
        GLOBAL_WELCOME.pop(me.id, None)
        WELCOME_SETTINGS.pop(event.chat_id, None)
        GREETED_USERS.pop(me.id, None)

        await event.edit("🗑️ **Welcome Message Disabled.**")

    @client.on(events.NewMessage(incoming=True))
    async def dm_first_msg_welcome_listener(event):
        if not event.is_private:
            return

        sender_id = event.sender_id
        if not sender_id:
            return

        me = await client.get_me()
        if sender_id == me.id:
            return

        # Check if welcome is enabled for this userbot
        welcome_msg = GLOBAL_WELCOME.get(me.id) or WELCOME_SETTINGS.get(event.chat_id)
        if not welcome_msg:
            return

        if me.id not in GREETED_USERS:
            GREETED_USERS[me.id] = set()

        # Check if sender has already been welcomed
        if sender_id not in GREETED_USERS[me.id]:
            GREETED_USERS[me.id].add(sender_id)

            sender = await event.get_sender()
            first_name = sender.first_name if sender else "Friend"
            mention = f"[{first_name}](tg://user?id={sender_id})" if sender else first_name

            formatted_msg = welcome_msg.replace("{mention}", mention).replace("{name}", first_name)

            try:
                await event.reply(formatted_msg)
                LOGS.info(f"Auto-sent DM welcome message to {sender_id}")
            except Exception as e:
                LOGS.error(f"Failed to send DM welcome message: {e}")

    @client.on(events.ChatAction)
    async def chat_welcome_listener(event):
        if event.user_joined or event.user_added:
            me = await client.get_me()
            welcome_msg = WELCOME_SETTINGS.get(event.chat_id) or GLOBAL_WELCOME.get(me.id)

            if welcome_msg:
                user = await event.get_user()
                first_name = user.first_name if user else "Member"
                mention = f"[{first_name}](tg://user?id={user.id})" if user else first_name

                text = welcome_msg.replace("{mention}", mention).replace("{name}", first_name)
                try:
                    await event.respond(text)
                except Exception as e:
                    LOGS.error(f"Failed to send group welcome message: {e}")
