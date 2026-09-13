# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.
#
# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from telethon import Button, events
from telethon.events import CallbackQuery

from userbot import Config, catub

WELCOME_TEXT = """🌟 **Welcome To The Premium Userbot Hoster Bot!** 🌟

🚀 **Unleash The Power Of Automation With Style!** 🚀

👑 **Crafted By:** @TgCatUB 👑

🔒 **100% Secure & Lightning Fast!** 🔒

✨ **Explore Commands With /help Or Tap Below!** ✨"""

HELP_TEXT = """🔹 /start - **Launch the Bot with a Grand Welcome**
🔹 /help - **Discover All Commands**
🔹 /commands - **Explore Userbot Features**
🔹 /host - **Deploy Your Own Userbot**
🔹 /support - **Request Support from Admin (Fast Response)**
🔹 /restart - **Revive Your Hosted Userbot**
🔹 /supportraid - **Pro Support Raid Command (Owners / Premium Users Only)**
🔹 /restartall - **Restart All Userbots (Owners Only)**
🔹 /refresh - **Refresh Bot State (Owners Only)**
🔹 /status - **Check Your Userbot's Pulse**
🔹 /logout - **Safely Log Out Your Userbot**
🔹 /sudolist - **View Sudo Users (Owners Only)**
🔹 /setdp - **Set Display Photo (Owners Only)**
🔹 /block - **Block a User (Owners Only)**
🔹 /unblock - **Unblock a User (Owners Only)**
🔹 /blockeduser - **View Blocked Users (Owners Only)**
🔹 /stats - **View Bot Statistics**"""

COMMANDS_HEADER = """✨ **Userbot Commands - Premium!** ✨

💬 ***Click a Box To Explore Commands!*** 💬

________________________________________
Full Tutorial Bot Cmds - t.me/catuserbot_support

🔹 **Choose A Feature** 🔹"""

CATEGORIES_INFO = {
    "cat_spam": "📨 **Spam Module Commands:**\n\n• `.spam <count> <text>` : Spams a message N times.\n• `.cspam <text>` : Spams letter by letter.\n• `.delayspam <delay> <count> <text>` : Spams with delay.\n• `.bigspam <count> <text>` : Heavy volume spam.",
    "cat_tspam": "⏰ **Timed Spam Module Commands:**\n\n• `.tspam <seconds> <text>` : Spams continuously with timer intervals.",
    "cat_raid": "💥 **Raid Module Commands:**\n\n• `.raid <count> <username/reply>` : Initiates raid on specified user.\n• `.mraid <count> <username>` : Mention raid on target user.",
    "cat_araid": "🔥 **Abusive Raid Module Commands:**\n\n• `.araid <count> <username>` : Sends abusive raid messages.\n• `.daraid` : Deactivates active abusive raid.",
    "cat_sraid": "💌 **Shayari Raid Module Commands:**\n\n• `.sraid <count> <username>` : Sends Shayari raid on target user.",
    "cat_rraid": "🎯 **Reply Raid Module Commands:**\n\n• `.rraid <reply/username>` : Activates auto-reply raid on target user.\n• `.drraid <reply/username>` : Deactivates reply raid.",
    "cat_tagging": "🔔 **Tagging Module Commands:**\n\n• `.tagall <msg>` : Tags all group members with custom message.\n• `.adminstag <msg>` : Tags all group admins.\n• `.canceltag` : Cancels ongoing tag process.",
    "cat_welcome": "🎉 **Welcome Module Commands:**\n\n• `.setwelcome <msg>` : Sets custom welcome message for group.\n• `.clearwelcome` : Clears custom welcome message.",
    "cat_mod": "🚫 **Moderation Module Commands:**\n\n• `.ban <user>` : Bans target user.\n• `.unban <user>` : Unbans target user.\n• `.mute <user>` : Mutes target user.\n• `.unmute <user>` : Unmutes target user.\n• `.kick <user>` : Kicks user from group.",
    "cat_fun": "😂 **Fun Module Commands:**\n\n• `.meme` : Generates random meme.\n• `.slap <user>` : Slaps user with random item.\n• `.dice` : Rolls an animated dice.\n• `.roll` : Rolls random numbers.",
    "cat_custom": "✍️ **Customization Module Commands:**\n\n• `.setalive <text>` : Customizes `.alive` message.\n• `.setalivename <name>` : Sets ALIVE_NAME.\n• `.setalivedp <link>` : Sets custom ALIVE display photo.",
    "cat_gen": "ℹ️ **General Module Commands:**\n\n• `.alive` : Checks if userbot is online & responsive.\n• `.ping` : Checks response latency.\n• `.id` : Displays chat/user ID details.\n• `.info <user>` : Shows detailed user info.",
    "cat_admin": "🔧 **Admin Module Commands:**\n\n• `.promote <user>` : Promotes user to group admin.\n• `.demote <user>` : Demotes admin back to member.\n• `.gban <user>` : Globally bans user across managed groups.\n• `.ungban <user>` : Removes global ban.",
    "cat_save": "💾 **Save Disappearing Module Commands:**\n\n• `.save <reply>` : Saves self-destructing / disappearing photos to Saved Messages.",
    "cat_bcast": "📢 **Broadcast Module Commands:**\n\n• `.gcast <msg>` : Broadcasts message across all joined groups.\n• `.broadcast <msg>` : Broadcasts to bot starters.",
    "cat_antisafe": "🛡️ **AntiSafe Module Commands:**\n\n• `.antisafe on/off` : Enables or disables anti-safety protections.",
    "cat_approve": "✅ **Approve Module Commands:**\n\n• `.approve` : Approves user to PM you.\n• `.disapprove` : Disapproves user from PM.",
    "cat_craid": "⚡ **CRAID Module Commands:**\n\n• `.craid <count> <username>` : Launches high-speed custom raid.",
    "cat_autoreply": "🤖 **AutoReply Module Commands:**\n\n• `.setreply <trigger> | <response>` : Sets automated reply rule.\n• `.delreply <trigger>` : Deletes automated reply rule.",
    "cat_nuclear": "☢️ **Nuclear Clear Module Commands:**\n\n• `.purge` : Deletes all messages from replied message downwards.\n• `.del` : Deletes replied message."
}


def get_commands_keyboard():
    return [
        [Button.inline("📨 Spam", data="cat_spam"), Button.inline("⏰ Timed Spam", data="cat_tspam"), Button.inline("💥 Raid", data="cat_raid")],
        [Button.inline("🔥 Abusive Raid", data="cat_araid"), Button.inline("💌 Shayari Raid", data="cat_sraid"), Button.inline("🎯 Reply Raid", data="cat_rraid")],
        [Button.inline("🔔 Tagging", data="cat_tagging"), Button.inline("🎉 Welcome", data="cat_welcome"), Button.inline("🚫 Moderation", data="cat_mod")],
        [Button.inline("😂 Fun", data="cat_fun"), Button.inline("✍️ Customization", data="cat_custom"), Button.inline("ℹ️ General", data="cat_gen")],
        [Button.inline("🔧 Admin", data="cat_admin"), Button.inline("💾 Save Disappearing", data="cat_save"), Button.inline("📢 Broadcast", data="cat_bcast")],
        [Button.inline("🛡️ AntiSafe", data="cat_antisafe"), Button.inline("✅ Approve", data="cat_approve"), Button.inline("⚡ CRAID", data="cat_craid")],
        [Button.inline("🤖 AutoReply", data="cat_autoreply"), Button.inline("☢️ Nuclear Clear", data="cat_nuclear")],
    ]


@catub.bot_cmd(pattern="^/start$", func=lambda e: e.is_private)
async def bot_start_handler(event):
    buttons = [[Button.inline("📖 Help", data="cmd_help")]]
    await event.reply(WELCOME_TEXT, buttons=buttons)


@catub.bot_cmd(pattern="^/help$", func=lambda e: e.is_private)
async def bot_help_handler(event):
    await event.reply(HELP_TEXT)


@catub.bot_cmd(pattern="^/commands$", func=lambda e: e.is_private)
async def bot_commands_handler(event):
    await event.reply(COMMANDS_HEADER, buttons=get_commands_keyboard())


@catub.bot_cmd(pattern="^/support$", func=lambda e: e.is_private)
async def bot_support_handler(event):
    await event.reply("💬 **Support & Group:**\nhttps://t.me/catuserbot_support")


@catub.bot_cmd(pattern="^/status$", func=lambda e: e.is_private)
async def bot_status_handler(event):
    session_active = bool(getattr(Config, "STRING_SESSION", ""))
    status_msg = "🟢 **Userbot Status:** ACTIVE & HOSTED" if session_active else "🔴 **Userbot Status:** NOT HOSTED (Run /host to deploy)"
    await event.reply(f"📊 **Userbot Pulse Check:**\n\n{status_msg}")


@catub.tgbot.on(CallbackQuery)
async def bot_callback_handler(event):
    data = event.data.decode("utf-8")
    if data == "cmd_help":
        await event.edit(HELP_TEXT)
        return
    if data == "cat_main":
        await event.edit(COMMANDS_HEADER, buttons=get_commands_keyboard())
        return
    if data in CATEGORIES_INFO:
        back_btn = [[Button.inline("« Back to Categories", data="cat_main")]]
        await event.edit(CATEGORIES_INFO[data], buttons=back_btn)
        return
