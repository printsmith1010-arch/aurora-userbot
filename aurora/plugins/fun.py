"""
Aurora Fun & Entertainment Plugin.

Commands: .joke, .flip, .roll, .rps, .calc, .meme, .slap, .dice
"""

import random
import logging
from telethon import events
from telethon.tl.types import InputMediaDice
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraFunPlugin")

plugin_manager.register_command("joke", "fun", "Get a random Hinglish joke.", f"{Config.COMMAND_HANDLER}joke")
plugin_manager.register_command("flip", "fun", "Flip a coin.", f"{Config.COMMAND_HANDLER}flip")
plugin_manager.register_command("roll", "fun", "Roll a dice.", f"{Config.COMMAND_HANDLER}roll <number>")
plugin_manager.register_command("rps", "fun", "Play rock-paper-scissors.", f"{Config.COMMAND_HANDLER}rps rock|paper|scissors")
plugin_manager.register_command("calc", "fun", "Calculate math expression.", f"{Config.COMMAND_HANDLER}calc <expression>")

HINGLISH_JOKES = [
    "😂 **Teacher:** Pappu, batao pani kahan kahan paya jata hai?\n**Pappu:** Sir, nal me, kuye me, aur jab marksheet hath me aati hai tab aakh me! 🤣",
    "😂 **Pati:** Doctor saab, meri patni baat karte karte achhanak behosh ho jati hai!\n**Doctor:** Ye bimari nahi, chamatkar hai! 🤣",
    "😂 **Pappu:** Papa mujhe naya phone chahiye!\n**Papa:** Phone mangne se pehle padhai pe dhyan do!\n**Pappu:** Papa, phone pe hi to dhyan dunga! 🤣",
    "😂 **Boss:** Tum kaam pe 10 minute late kyu aaye?\n**Employee:** Sir, sapne me aapki tareef sun raha tha, isliye neend khul hi nahi rahi thi! 🤣",
    "😂 **Santa:** Banta, tu itna udaas kyu betha hai?\n**Banta:** Yaar, biwi ne kaha tha market se doodh lene jao to sath me ande bhi le aana agar tamatar mil jaye to...\n**Santa:** Phir?\n**Banta:** Main 6 litre doodh le aaya kyonki tamatar mil gaye the! 🤣"
]

SLAP_OBJECTS = [
    "a massive rubber duck 🦆",
    "a wet newspaper 📰",
    "a giant trout 🐟",
    "a frying pan 🍳",
    "a slice of pepperoni pizza 🍕",
]


def register_fun_handlers(client):
    """
    Registers fun event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]joke$"))
    async def joke_handler(event):
        joke = random.choice(HINGLISH_JOKES)
        await event.edit(joke)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]flip$"))
    async def flip_handler(event):
        result = random.choice(["🪙 **Heads!**", "🪙 **Tails!**"])
        await event.edit(f"🪙 **Flipping coin...**\n\nResult: {result}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]roll(?:\s+(\d+))?"))
    async def roll_handler(event):
        num_str = event.pattern_match.group(1)
        max_val = int(num_str) if num_str else 6
        val = random.randint(1, max_val)
        await event.edit(f"🎲 **Rolled Dice (1-{max_val}):** `{val}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]rps(?:\s+(rock|paper|scissors))?"))
    async def rps_handler(event):
        user_choice = event.pattern_match.group(1)
        if not user_choice:
            await event.edit("💡 **Usage:** `.rps rock` | `.rps paper` | `.rps scissors`")
            return

        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        user_c = user_choice.lower()

        if user_c == bot_choice:
            res = "🤝 **It's a Tie!**"
        elif (user_c == "rock" and bot_choice == "scissors") or \
             (user_c == "paper" and bot_choice == "rock") or \
             (user_c == "scissors" and bot_choice == "paper"):
            res = "🎉 **You Win!**"
        else:
            res = "💻 **Userbot Wins!**"

        await event.edit(f"🎮 **Rock Paper Scissors!**\n\n👤 **You:** `{user_c.capitalize()}`\n🤖 **Bot:** `{bot_choice.capitalize()}`\n\n{res}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]calc(?:\s+([\s\S]+))?"))
    async def calc_handler(event):
        expr = event.pattern_match.group(1)
        if not expr:
            await event.edit("💡 **Usage:** `.calc 2 + 3`")
            return

        try:
            allowed = set("0123456789+-*/(). ")
            if not set(expr).issubset(allowed):
                await event.edit("❌ **Invalid characters in math expression.**")
                return
            result = eval(expr, {"__builtins__": None}, {})
            await event.edit(f"🧮 **Calculation:**\n`{expr}` = `{result}`")
        except Exception as e:
            await event.edit(f"❌ **Calc error:** `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]slap(?:\s+([\s\S]+))?"))
    async def slap_handler(event):
        reply = await event.get_reply_message()
        target_str = event.pattern_match.group(1)

        target = "someone"
        if reply:
            user = await reply.get_sender()
            target = f"[{user.first_name}](tg://user?id={user.id})" if user else "user"
        elif target_str:
            target = target_str.strip()

        obj = random.choice(SLAP_OBJECTS)
        await event.edit(f"👋 **Slapped {target} with {obj}!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]dice$"))
    async def dice_handler(event):
        await event.delete()
        await event.respond(file=InputMediaDice(emoticon="🎲"))
