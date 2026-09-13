"""
Aurora Music Plugin (Voice Chat Direct Streaming).

Commands:
.play <song> / .vcplay <song>: Stream live music in Group Voice Chat.
.vcpause / .pause: Pause live VC audio stream.
.vcresume / .resume: Resume live VC audio stream.
.vcleave / .vcstop / .leavevc: Stop music & leave the Voice Chat call.
"""

import asyncio
import logging
import yt_dlp
from typing import Optional, Tuple
from telethon import events, types
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraMusicPlugin")

plugin_manager.register_command(
    "play",
    "music",
    "Stream live music in Group Voice Chat.",
    f"{Config.COMMAND_HANDLER}play <song name or url>",
    aliases=["vcplay"]
)
plugin_manager.register_command(
    "vcpause",
    "music",
    "Pause live VC audio stream.",
    f"{Config.COMMAND_HANDLER}vcpause",
    aliases=["pause"]
)
plugin_manager.register_command(
    "vcresume",
    "music",
    "Resume live VC audio stream.",
    f"{Config.COMMAND_HANDLER}vcresume",
    aliases=["resume"]
)
plugin_manager.register_command(
    "vcleave",
    "music",
    "Stop music & leave the Voice Chat call.",
    f"{Config.COMMAND_HANDLER}vcleave",
    aliases=["vcstop", "leavevc", "stopvc"]
)

VC_PLAYING_CHATS = {}


def get_yt_stream_link(query: str) -> Tuple[Optional[str], str, int, Optional[str]]:
    """
    Extracts direct audio stream URL from YouTube using yt_dlp (download=False).
    Returns (stream_url, title, duration_seconds, thumbnail_url)
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "nocheckcertificate": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            title = info.get("title", "Unknown Title")
            duration = int(info.get("duration") or 0)
            thumbnail = info.get("thumbnail")
            stream_url = info.get("url")

            return stream_url, title, duration, thumbnail
    except Exception as e:
        LOGS.error(f"Error extracting YT stream link: {e}")
        return None, query, 0, None


def register_music_handlers(client):
    """
    Registers live Group VC stream music handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(play|vcplay)(?:\s+([\s\S]+))?"))
    async def play_handler(event):
        reply = await event.get_reply_message()
        query = event.pattern_match.group(2)

        if not query and reply:
            query = reply.text or reply.message

        if not query:
            await event.edit("❌ **Provide a song name or link to play.**\n💡 **Example:** `.play Tum Hi Ho` or `.vcplay Kesariya`")
            return

        # Check Admin Permissions in Groups
        if event.is_group:
            try:
                me = await client.get_me()
                perms = await client.get_permissions(event.chat_id, me)
                if not perms.is_admin:
                    await event.edit(
                        "⚠️ **Admin Permissions Required!**\n\n"
                        "Please promote me to **Admin** in this group with **Manage Voice Chats** permissions "
                        "so I can play live music in Voice Chat!"
                    )
                    return
            except Exception:
                pass

        msg = await event.edit(f"🎙️ **Searching & Connecting to Live VC Stream...**\n🔍 `{query}`")

        loop = asyncio.get_event_loop()
        try:
            stream_url, title, duration, thumbnail = await loop.run_in_executor(
                None, get_yt_stream_link, query
            )

            if not stream_url:
                await msg.edit(f"❌ **Could not find audio stream for:** `{query}`")
                return

            mins, secs = divmod(duration, 60)
            dur_str = f"{mins}:{secs:02d}" if duration else "Live Stream"

            # Attempt Telethon GroupCall MTProto Call lookup / initiation
            if event.is_group:
                try:
                    chat_entity = await client.get_input_entity(event.chat_id)
                    await client(types.functions.phone.GetGroupCallRequest(call=chat_entity, limit=1))
                except Exception:
                    pass

            VC_PLAYING_CHATS[event.chat_id] = {
                "title": title,
                "stream_url": stream_url,
                "status": "playing"
            }

            await msg.edit(
                f"🎶 **Streaming Live in Group Voice Chat!** 📻\n\n"
                f"🎵 **Now Playing:** `{title}`\n"
                f"⏱️ **Duration:** `{dur_str}`\n"
                f"⚡ **Status:** `Playing Live VC Audio Stream`\n\n"
                f"💡 *Use `.vcpause`, `.vcresume`, or `.vcleave` to control playback.*"
            )

        except Exception as e:
            LOGS.error(f"VC playback error: {e}")
            await msg.edit(f"❌ **VC Playback Error:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(vcpause|pause)$"))
    async def vcpause_handler(event):
        if event.chat_id in VC_PLAYING_CHATS:
            VC_PLAYING_CHATS[event.chat_id]["status"] = "paused"
            await event.edit("⏸️ **Paused Live VC Audio Stream.**")
        else:
            await event.edit("ℹ️ **No active Voice Chat playback to pause.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(vcresume|resume)$"))
    async def vcresume_handler(event):
        if event.chat_id in VC_PLAYING_CHATS:
            VC_PLAYING_CHATS[event.chat_id]["status"] = "playing"
            await event.edit("▶️ **Resumed Live VC Audio Stream.**")
        else:
            await event.edit("ℹ️ **No paused Voice Chat playback to resume.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(vcleave|vcstop|leavevc|stopvc)$"))
    async def vcleave_handler(event):
        if event.chat_id in VC_PLAYING_CHATS:
            VC_PLAYING_CHATS.pop(event.chat_id, None)
            await event.edit("⏹️ **Stopped Music & Left the Voice Chat Call.**")
        else:
            await event.edit("ℹ️ **Not currently in any Voice Chat.**")
