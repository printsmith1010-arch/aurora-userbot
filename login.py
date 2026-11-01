#!/usr/bin/env python3
"""
Aurora Telegram Hoster & Platform Launcher.

Run `python login.py` or `python -m aurora` to start the Aurora Multi-User Platform.
"""

import os
import asyncio
import sys
from aiohttp import web
from aurora.bot import start_aurora_bot
from aurora.core.session_manager import session_manager


async def health(request):
    """Health check endpoint for Render.com and UptimeRobot monitoring."""
    return web.Response(text="Aurora Userbot Platform is Running 24/7!", status=200)


async def start_web_server():
    """Starts an HTTP server on Render's assigned PORT for instant deploy detection."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[+] HTTP Web Server running on 0.0.0.0:{port} (Render deployment ready)")


async def main():
    print("\n=========================================================")
    print("      Aurora Multi-User Telegram Userbot Platform        ")
    print("=========================================================")
    print("[+] Initializing encrypted database and loading active sessions...")

    # Start HTTP server so Render Web Service detects the port immediately
    try:
        await start_web_server()
    except Exception as e:
        print(f"[!] Warning starting web server: {e}")

    # Load existing active sessions from DB
    await session_manager.load_all_sessions()

    # Start Aurora Hoster Bot
    await start_aurora_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Aurora Platform shut down.")

