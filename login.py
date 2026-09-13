#!/usr/bin/env python3
"""
Aurora Telegram Hoster & Platform Launcher.

Run `python login.py` or `python -m aurora` to start the Aurora Multi-User Platform.
"""

import asyncio
import sys
from aurora.bot import start_aurora_bot
from aurora.core.session_manager import session_manager


async def main():
    print("\n=========================================================")
    print("      Aurora Multi-User Telegram Userbot Platform        ")
    print("=========================================================")
    print("[+] Initializing encrypted database and loading active sessions...")

    # Load existing active sessions from DB
    await session_manager.load_all_sessions()

    # Start Aurora Hoster Bot
    await start_aurora_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Aurora Platform shut down.")
