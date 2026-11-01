"""
Aurora Disappearing Media Saver Plugin.

Commands: .sd, .save
Saves self-destructing/disappearing photos & videos to Saved Messages, then instantly deletes .sd command message.
"""

import os
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraMediaPlugin")

plugin_manager.register_command("sd", "save", "Save a disappearing message to Saved Messages and delete command message.", f"{Config.COMMAND_HANDLER}sd (reply to disappearing msg)")
plugin_manager.register_command("save", "save", "Save disappearing photo/video to Saved Messages.", f"{Config.COMMAND_HANDLER}save <reply>")


def register_media_handlers(client):
    """
    Registers stealth media saver event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](sd|save)$"))
    async def save_handler(event):
        reply = await event.get_reply_message()
        if not reply:
            try:
                await event.delete()
            except Exception:
                pass
            return

        try:
            if reply.media:
                file_path = await client.download_media(reply)
                if not file_path:
                    file_path = await client.download_media(reply.media)

                if file_path and os.path.exists(file_path):
                    caption = f"💾 **Saved Disappearing Media**\n📩 **From Chat ID:** `{event.chat_id}`"
                    await client.send_file("me", file_path, caption=caption)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                else:
                    # Fallback if download failed
                    await client.send_message("me", reply)
            else:
                # If text message, send text to Saved Messages
                msg_content = reply.text or reply.message or ""
                await client.send_message("me", f"💾 **Saved Disappearing Message:**\n\n{msg_content}")
        except Exception as e:
            LOGS.error(f"Disappearing media save error: {e}")

        # Stealth: Instantly delete the .sd / .save command message from chat
        try:
            await event.delete()
        except Exception as e:
            LOGS.error(f"Error deleting .sd command message: {e}")
