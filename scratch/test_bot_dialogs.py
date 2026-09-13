import asyncio
import logging
from telethon import TelegramClient, types
from aurora.config import Config

logging.basicConfig(level=logging.INFO)

async def test_bot():
    bot = TelegramClient("test_bot_sess", Config.API_ID, Config.API_HASH)
    await bot.start(bot_token=Config.TG_BOT_TOKEN)
    print("Bot logged in successfully!")
    
    try:
        dialogs = await bot.get_dialogs(limit=None)
        print(f"Total dialogs returned by bot.get_dialogs(): {len(dialogs)}")
        for d in dialogs:
            print(f"Dialog: {d.name} | ID: {d.id} | is_group: {d.is_group} | is_channel: {d.is_channel}")
    except Exception as e:
        print(f"Error fetching dialogs: {e}")

    await bot.disconnect()

if __name__ == "__main__":
    asyncio.run(test_bot())
