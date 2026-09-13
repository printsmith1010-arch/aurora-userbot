"""
Aurora Customization Plugin.

Commands: .stylish, .changeowner, .setalive, .setalivename, .setalivedp
"""

import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraCustomPlugin")

plugin_manager.register_command("stylish", "custom", "Generate stylish names.", f"{Config.COMMAND_HANDLER}stylish <name>")
plugin_manager.register_command("changeowner", "custom", "Change custom owner tag in .ping & .alive.", f"{Config.COMMAND_HANDLER}changeowner @username")

CUSTOM_OWNER_TAGS = {}

STYLISH_MAP = {
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
    "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ",
    "o": "ᵒ", "p": "ᵖ", "q": "ᵠ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
    "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ"
}


def register_custom_handlers(client):
    """
    Registers customization event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stylish(?:\s+([\s\S]+))?"))
    async def stylish_handler(event):
        name = event.pattern_match.group(1)
        if not name:
            await event.edit("💡 **Usage:** `.stylish Aditya`")
            return

        name_clean = name.strip()
        superscript = "".join(STYLISH_MAP.get(c.lower(), c) for c in name_clean)
        boxed = " ".join(f"[{c.upper()}]" for c in name_clean if c.isalpha())
        bold_gothic = f"𝕬𝖉𝖎𝖙𝖞𝖆" if name_clean.lower() == "aditya" else f"✨ **{name_clean}** ✨"

        res = (
            f"✍️ **Stylish Name Variations For `{name_clean}`:**\n\n"
            f"1. 👑 `{name_clean.upper()} ᵗᵍ`\n"
            f"2. ✨ `{superscript}`\n"
            f"3. 🔲 `{boxed}`\n"
            f"4. 🌟 `꧁★{name_clean}★꧂`"
        )
        await event.edit(res)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.changeowner(?:\s+([\s\S]+))?"))
    async def changeowner_handler(event):
        owner_str = event.pattern_match.group(1)
        if not owner_str:
            await event.edit("💡 **Usage:** `.changeowner @NewOwner`")
            return

        me = await client.get_me()
        CUSTOM_OWNER_TAGS[me.id] = owner_str.strip()
        await event.edit(f"👑 **Custom Owner Tag Updated To:** `{owner_str.strip()}`\n\nThis tag will now display when running `.ping` or `.alive`!")
