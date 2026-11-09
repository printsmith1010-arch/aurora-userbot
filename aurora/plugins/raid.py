"""
Aurora Raid & Reply Raid Plugin.

Commands: .raid, .stopraid, .araid, .sraid, .stopsraid, .replyraid, .dreplyraid, .craid, .setraid, .raidlangs
Supports multi-language raids including:
Hindi (hi), Telugu (te), English (en), Tamil (ta), Punjabi (pa), Kannada (kn),
Malayalam (ml), Marathi (mr), Bengali (bn), Gujarati (gu), Bhojpuri (bho), Haryanvi (hr).
"""

import asyncio
import random
import logging
from telethon import events
from aurora.config import Config
from aurora.core.plugin_manager import plugin_manager

LOGS = logging.getLogger("AuroraRaidPlugin")

plugin_manager.register_command("raid", "raid", "Raid with language option (hi, te, en, etc.).", f"{Config.COMMAND_HANDLER}raid <count> [lang] [chatid] [@username]")
plugin_manager.register_command("stopraid", "raid", "Stop ongoing raid.", f"{Config.COMMAND_HANDLER}stopraid [id]")
plugin_manager.register_command("araid", "araid", "Send abusive words line-by-line with language option.", f"{Config.COMMAND_HANDLER}araid <count> [lang] [message_link]")
plugin_manager.register_command("sraid", "sraid", "Send romantic shayari messages with language option.", f"{Config.COMMAND_HANDLER}sraid <count> [lang] [username/userid/reply]")
plugin_manager.register_command("stopsraid", "sraid", "Stop shayari raid.", f"{Config.COMMAND_HANDLER}stopsraid")
plugin_manager.register_command("replyraid", "rraid", "Auto-reply with abusive messages in chosen language when user replies or tags you.", f"{Config.COMMAND_HANDLER}replyraid [lang] [username/userid/reply]")
plugin_manager.register_command("dreplyraid", "rraid", "Deactivate reply raid.", f"{Config.COMMAND_HANDLER}dreplyraid [username/userid/reply]")
plugin_manager.register_command("craid", "craid", "Super fast personal raid with chosen language.", f"{Config.COMMAND_HANDLER}craid <count> [lang]")
plugin_manager.register_command("setraid", "craid", "Set personal raid channel link.", f"{Config.COMMAND_HANDLER}setraid <channel_link>")
plugin_manager.register_command("raidlangs", "raid", "Show all supported language codes for raids.", f"{Config.COMMAND_HANDLER}raidlangs")

# ==================== LANGUAGE METADATA & CODES ====================
LANG_INFO = {
    "hi": {"name": "Hindi / Hinglish", "aliases": ["hi", "hindi", "hinglish", "h"]},
    "te": {"name": "Telugu", "aliases": ["te", "telugu", "tel", "t"]},
    "en": {"name": "English", "aliases": ["en", "english", "eng"]},
    "ta": {"name": "Tamil", "aliases": ["ta", "tamil"]},
    "pa": {"name": "Punjabi", "aliases": ["pa", "punjabi"]},
    "kn": {"name": "Kannada", "aliases": ["kn", "kannada"]},
    "ml": {"name": "Malayalam", "aliases": ["ml", "malayalam"]},
    "mr": {"name": "Marathi", "aliases": ["mr", "marathi"]},
    "bn": {"name": "Bengali", "aliases": ["bn", "bengali", "bangla"]},
    "gu": {"name": "Gujarati", "aliases": ["gu", "gujarati"]},
    "bho": {"name": "Bhojpuri", "aliases": ["bho", "bhojpuri"]},
    "hr": {"name": "Haryanvi", "aliases": ["hr", "haryanvi"]},
}

LANG_MAP = {}
for code, data in LANG_INFO.items():
    for alias in data["aliases"]:
        LANG_MAP[alias] = code

# ==================== RAID LINES PER LANGUAGE ====================

RAID_LINES_HI = [
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
    "chutiye ke patthe nikal bsdk 💥",
    "teri aukaat kya hai be lodu ⚡",
    "baap se panga mat le chutiye 🔥",
    "gandu ki aulaad chup baith 💥",
    "randi rona band kar bsdk ⚡",
    "muh me le le madarchod 🔥",
    "kutta bana ke chodenge bsdk 💥",
    "tere jaise kutte sadak pe ghumte hai ⚡"
]

RAID_LINES_TE = [
    "nee amma puku ra lanjakodaka 💥",
    "gudha muskoni kurcho ra boke 🔥",
    "nee akkani dengina lanjodaka ⚡",
    "dengithe dimaak kharab avuddi ra 💥",
    "nee avva gudha pagilipodhi ra 🔥",
    "lanjakodaka aukaat lo undu ⚡",
    "moddalo gola dengaku ra waste naayala 💥",
    "nee amma denga ra pitchi puka 🔥",
    "gudha pagalgodtha ra lanjakodaka ⚡",
    "kukkala moragaku ra erripuka 💥",
    "nee bondha ra lanjodaka 🔥",
    "dengu ikkadanunchi lekapothe sachipothav ⚡",
    "puku pagilipodhi ra badacow 💥",
    "nee thalli dengina mundakodaka 🔥",
    "gudhalo dammunte direct ra lanjodaka ⚡",
    "lanja puttinoda aagaleka chasthunnav ra 💥",
    "moosukuni dengai ra kukka na kodaka 🔥",
    "nee bathuku cheppu theeskoni kottali ⚡",
    "baap tho pettukoku ra chetta puka 💥",
    "nee amma mogudu vachadu ra ikkada 🔥"
]

RAID_LINES_EN = [
    "get lost you piece of trash 💥",
    "shut the fuck up bitch 🔥",
    "fuck off you clown ⚡",
    "sit the fuck down bastard 💥",
    "you have no existence here loser 🔥",
    "cry more you little bitch ⚡",
    "fuck outta here motherfucker 💥",
    "know your place trash 🔥",
    "dont bark in front of your daddy ⚡",
    "worthless piece of shit get lost 💥"
]

RAID_LINES_TA = [
    "otha moodra sunni 💥",
    "thevadiya payale olunga po 🔥",
    "ommala okka un aukaat enna da ⚡",
    "moodittu kelambu da baadu 💥",
    "koothi magane oolu vidatha 🔥",
    "un appan vandhutan da sunni payale ⚡",
    "otha un mandaiya polanthruven 💥",
    "thevidiya mavane poidu ingirundu 🔥"
]

RAID_LINES_PA = [
    "teri maa di fudi kanjra 💥",
    "chup kar bhenchod kuttay 🔥",
    "teri bhen da phuda maran ⚡",
    "teri aukaat ki ae kanjra 💥",
    "gand marva lalli deya 🔥",
    "kutta bana ke kuttan ge bhenchod ⚡",
    "dallay nikal itthon 🔥"
]

RAID_LINES_KN = [
    "nin amman sule magane 💥",
    "baddi magane bay mucchu 🔥",
    "nin gulthe hodeyala baddi magane ⚡",
    "hogli bidi sule magane 💥",
    "nin aukaat yenu kanro 🔥",
    "thika mucchu sule magane ⚡",
    "nin appan bandidane nodu 💥",
    "hogi thika tholkolo loafer 🔥",
    "dammidre eduru baa sule magane ⚡"
]

RAID_LINES_ML = [
    "ninte thanthedo thendi 💥",
    "poda myre vaaya moodi irikada 🔥",
    "patti thendi mone ⚡",
    "ninte thallayude poottu 💥",
    "polayadi mone podaarunnu 🔥",
    "kollathirunnu koovada pulle ⚡",
    "enthoru kanjiyaada nee 💥",
    "mone puzhu kuthya thendi 🔥"
]

RAID_LINES_MR = [
    "tuzya aai chi gand bsdk 💥",
    "zhavadya chup bas lavdya 🔥",
    "tuzi aai ghalin bhadvyachya ⚡",
    "aai zhavli tuzya bapachi 💥",
    "lavdya tuzi aukaat kay ahe 🔥",
    "gandit dum asel tar samor ye ⚡",
    "chal nigh bhenchya ithe kay kartoy 💥",
    "chutya sarkha bolu nako lavdya 🔥"
]

RAID_LINES_BN = [
    "tor maar heda khanki magi 💥",
    "bokachoda mukh bondho kor 🔥",
    "tor boner heda mara khankir chele ⚡",
    "chudmarani r baal nikal eikhan theke 💥",
    "tor aukaat koto re baal 🔥",
    "damm thakle samne aaye khankir pola ⚡",
    "gand mara bokachoda 💥"
]

RAID_LINES_GU = [
    "tari maani laudo bsdk 💥",
    "chup bes lavda tari aukaat nathi 🔥",
    "tari ben ni pungi bsdk ⚡",
    "gand marav bhadva 💥",
    "chal nikal ahiya thi gando 🔥",
    "tara bapa ne olkhe che lavad ⚡"
]

RAID_LINES_BHO = [
    "tohar mai ke chodo bsdk 💥",
    "muh me leba ka bhosadi ke 🔥",
    "tohar bahin ke chudai ⚡",
    "chup chaap baith lodu na ta gand faad deb 💥",
    "bhadwa ke jaat chup raha 🔥",
    "aukaat me raha na ta goli maar deb ⚡"
]

RAID_LINES_HR = [
    "teri maa ki choot gadhe ke lund 💥",
    "gand tod dange bsdk aade te bhag le 🔥",
    "chup baith ja kute ki nasal ⚡",
    "tere jaise kutte gelya na bolte hum 💥",
    "aukaat me rah bhadve lath baj jaaga 🔥",
    "baap te panga na liye chhore ⚡"
]

# Backward compatibility reference
HINGLISH_ABUSIVE_RAID_LINES = RAID_LINES_HI

RAID_LANGUAGES = {
    "hi": RAID_LINES_HI,
    "te": RAID_LINES_TE,
    "en": RAID_LINES_EN,
    "ta": RAID_LINES_TA,
    "pa": RAID_LINES_PA,
    "kn": RAID_LINES_KN,
    "ml": RAID_LINES_ML,
    "mr": RAID_LINES_MR,
    "bn": RAID_LINES_BN,
    "gu": RAID_LINES_GU,
    "bho": RAID_LINES_BHO,
    "hr": RAID_LINES_HR,
}

# ==================== SHAYARI PER LANGUAGE ====================

SHAYARI_LINES_HI = [
    "🌹 Tadap ke dekho kisi ke pyar mein, to pata chale ki intazaar kya hota hai...",
    "✨ Teri dosti ne diya sukoon itna, ki har gham bhool gaye hum...",
    "🔥 Mohabbat bhi ek ajeeb sa khel hai, jo haar gaya woh jeet gaya...",
    "💫 Dil se nikli dua hai hamari, zindagani bane tumhari pyari...",
    "🥀 Kabhi tooti hui cheezon se ishq karke dekho, khud se nafrat bhool jaoge...",
    "🌸 Aankhon me aansu lekar muskurana padta hai, yahi to zindagi ka dastoor hai..."
]

SHAYARI_LINES_TE = [
    "🌹 Nee choopu nannu maarchi vesindhi, nee prema na gundello nilichi poyindhi...",
    "✨ Prathi kshanam nee thalaputho, na hrudayam paravasisthundhi...",
    "🔥 Preminchadam oka varam, adi nee meeda kalagadam na adrushtam...",
    "💫 Kalalu kanna kanulaloki neeve veluguvi ayyavu...",
    "🌸 Maruvagalanena nee madhura smruthulani, na chirunavvuku kaaranam nuvve..."
]

SHAYARI_LINES_EN = [
    "🌹 In a sea of people, my eyes will always search for you...",
    "✨ Distance means so little when someone means so much...",
    "🔥 You are my favorite thought in a noisy world...",
    "💫 If love had a name, it would simply be yours..."
]

SHAYARI_LANGUAGES = {
    "hi": SHAYARI_LINES_HI,
    "te": SHAYARI_LINES_TE,
    "en": SHAYARI_LINES_EN,
    "ta": SHAYARI_LINES_HI,
    "pa": SHAYARI_LINES_HI,
    "kn": SHAYARI_LINES_TE,
    "ml": SHAYARI_LINES_TE,
    "mr": SHAYARI_LINES_HI,
    "bn": SHAYARI_LINES_HI,
    "gu": SHAYARI_LINES_HI,
    "bho": SHAYARI_LINES_HI,
    "hr": SHAYARI_LINES_HI,
}

# Backward compatibility reference
SHAYARI_LINES = SHAYARI_LINES_HI

def get_raid_line(lang="hi"):
    lang_code = LANG_MAP.get(str(lang).lower(), "hi")
    lines = RAID_LANGUAGES.get(lang_code, RAID_LINES_HI)
    return random.choice(lines)

def get_shayari_line(lang="hi"):
    lang_code = LANG_MAP.get(str(lang).lower(), "hi")
    lines = SHAYARI_LANGUAGES.get(lang_code, SHAYARI_LINES_HI)
    return random.choice(lines)

def parse_raid_args(args_str, default_count=10):
    count = default_count
    lang = "hi"
    target_tokens = []

    if args_str:
        tokens = args_str.strip().split()
        for token in tokens:
            tl = token.lower()
            if tl in LANG_MAP and lang == "hi":
                lang = LANG_MAP[tl]
            elif token.isdigit():
                count = int(token)
            else:
                target_tokens.append(token)

    target = " ".join(target_tokens) if target_tokens else None
    return count, lang, target

def get_language_help_text():
    text = (
        "🌐 **Aurora Raid Supported Languages & Codes:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for code, data in LANG_INFO.items():
        aliases_str = ", ".join(f"`{a}`" for a in data["aliases"])
        text += f"• **{data['name']}**: {aliases_str}\n"

    text += (
        "\n💡 **How To Use In Raids:**\n"
        "• `.raid 10 te @user` — 10 Telugu raid messages\n"
        "• `.raid 10 hi` — 10 Hindi raid messages on reply\n"
        "• `.araid 10 kn @user` — 10 Kannada abusive lines\n"
        "• `.sraid 5 te` — 5 Telugu romantic shayari lines\n"
        "• `.replyraid te @user` — Auto-reply raid in Telugu\n"
        "• `.craid 20 mr` — 20 Marathi high-speed raid lines\n"
        "• `.stopraid` — Stop ongoing raid"
    )
    return text

ACTIVE_RAIDS = set()
ACTIVE_RRAIDS = set()
ACTIVE_RRAID_LANGS = {}
PERSONAL_RAID_CHANNELS = {}


def register_raid_handlers(client):
    """
    Registers raid event handlers on client.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](raidlangs?|raidlanguages?)$"))
    async def raidlangs_handler(event):
        await event.edit(get_language_help_text())

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](raid|mraid)(?:\s+([\s\S]+))?"))
    async def raid_handler(event):
        args_str = event.pattern_match.group(2)
        if args_str and args_str.strip().lower() in ["help", "langs", "languages"]:
            await event.edit(get_language_help_text())
            return

        count, lang, target_str = parse_raid_args(args_str, default_count=10)
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
            line = get_raid_line(lang)
            if target:
                await event.respond(f"{target} {line}")
            else:
                await event.respond(line)
            await asyncio.sleep(0.2)

        ACTIVE_RAIDS.discard(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]araid(?:\s+([\s\S]+))?"))
    async def araid_handler(event):
        args_str = event.pattern_match.group(1)
        if args_str and args_str.strip().lower() in ["help", "langs", "languages"]:
            await event.edit(get_language_help_text())
            return

        count, lang, target_str = parse_raid_args(args_str, default_count=10)
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
            line = get_raid_line(lang)
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

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]sraid(?:\s+([\s\S]+))?"))
    async def sraid_handler(event):
        args_str = event.pattern_match.group(1)
        if args_str and args_str.strip().lower() in ["help", "langs", "languages"]:
            await event.edit(get_language_help_text())
            return

        count, lang, target_str = parse_raid_args(args_str, default_count=5)
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
            line = get_shayari_line(lang)
            if target:
                await event.respond(f"{target} {line}")
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
        raw_args = event.pattern_match.group(2)
        if raw_args and raw_args.strip().lower() in ["help", "langs", "languages"]:
            await event.edit(get_language_help_text())
            return

        _, lang, target_str = parse_raid_args(raw_args, default_count=1)

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
        ACTIVE_RRAID_LANGS[target_id] = lang
        lang_name = LANG_INFO.get(lang, {}).get("name", lang.upper())
        await event.edit(f"🎯 **Reply Raid Activated On User:** `{target_id}` | **Language:** `{lang_name}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./](dreplyraid|drraid)(?:\s+([\s\S]+))?"))
    async def dreplyraid_handler(event):
        reply = await event.get_reply_message()
        raw_args = event.pattern_match.group(2)
        _, _, target_str = parse_raid_args(raw_args, default_count=1)

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
            ACTIVE_RRAIDS.discard(target_id)
            ACTIVE_RRAID_LANGS.pop(target_id, None)
            await event.edit(f"🛑 **Reply Raid Deactivated For User:** `{target_id}`")
        else:
            ACTIVE_RRAIDS.clear()
            ACTIVE_RRAID_LANGS.clear()
            await event.edit("🛑 **All Active Reply Raids Stopped.**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]setraid\s+([\s\S]+)"))
    async def setraid_handler(event):
        link = event.pattern_match.group(1).strip()
        me = await client.get_me()
        PERSONAL_RAID_CHANNELS[me.id] = link
        await event.edit(f"⚡ **Personal Raid Channel Set To:** `{link}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^[./]craid(?:\s+([\s\S]+))?"))
    async def craid_handler(event):
        args_str = event.pattern_match.group(1)
        if args_str and args_str.strip().lower() in ["help", "langs", "languages"]:
            await event.edit(get_language_help_text())
            return

        count, lang, _ = parse_raid_args(args_str, default_count=10)
        await event.delete()
        for _ in range(count):
            line = get_raid_line(lang)
            await event.respond(f"⚡ {line}")
            await asyncio.sleep(0.1)

    @client.on(events.NewMessage(incoming=True))
    async def rraid_listener(event):
        if event.sender_id in ACTIVE_RRAIDS:
            lang = ACTIVE_RRAID_LANGS.get(event.sender_id, "hi")
            line = get_raid_line(lang)
            try:
                await event.reply(line)
            except Exception as e:
                LOGS.error(f"Reply raid error: {e}")
