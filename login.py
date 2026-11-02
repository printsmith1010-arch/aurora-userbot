#!/usr/bin/env python3
"""
Aurora Telegram Hoster & Platform Launcher.

Runs the Aurora Multi-User Platform with an active HTTP server and self-pinger
to stay alive 24/7 on Render.com free instances.
"""

import os
import asyncio
import sys
import logging
from aiohttp import web, ClientSession
from aurora.bot import start_aurora_bot
from aurora.core.session_manager import session_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuroraLauncher")


async def health(request):
    """Health check endpoint for Render.com, UptimeRobot, and self-ping monitoring."""
    active_count = len(session_manager.get_all_active_users())
    return web.Response(
        text=f"Aurora Userbot Platform is Running 24/7!\nActive Userbots: {active_count}",
        status=200
    )


async def start_web_server():
    """Starts an HTTP server on Render's assigned PORT for instant deploy detection."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/ping", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"HTTP Web Server running on 0.0.0.0:{port} (Render deployment ready)")


async def keep_alive_worker():
    """
    Self-ping worker to prevent Render Free tier from spinning down due to inactivity.
    If RENDER_EXTERNAL_URL is set, pings the public endpoint every 10 minutes (600s).
    Render spins down after 15 minutes of zero inbound HTTP traffic.
    """
    await asyncio.sleep(60)  # Wait for startup
    url = os.environ.get("RENDER_EXTERNAL_URL")
    port = int(os.environ.get("PORT", 8080))

    target_url = url if url else f"http://127.0.0.1:{port}/health"
    logger.info(f"Self-ping keep-alive service initialized. Target: {target_url}")

    while True:
        try:
            async with ClientSession() as session:
                async with session.get(target_url, timeout=15) as resp:
                    if resp.status == 200:
                        logger.info(f"Keep-alive self-ping successful (Status: 200)")
                    else:
                        logger.warning(f"Keep-alive ping returned status: {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive ping error: {e}")

        # Sleep for 10 minutes (600 seconds) - well below Render's 15-minute sleep threshold
        await asyncio.sleep(600)


async def main():
    print("\n=========================================================")
    print("      Aurora Multi-User Telegram Userbot Platform        ")
    print("=========================================================")
    print("[+] Initializing encrypted database and loading active sessions...")

    # 1. Start HTTP server so Render Web Service detects the port immediately
    try:
        await start_web_server()
    except Exception as e:
        logger.error(f"Error starting web server: {e}")

    # 2. Launch background self-ping loop to prevent idle sleep
    asyncio.create_task(keep_alive_worker())

    # 3. Load existing active sessions from DB
    try:
        await session_manager.load_all_sessions()
    except Exception as e:
        logger.error(f"Error loading sessions: {e}")

    # 4. Start Aurora Hoster Bot with auto-restart supervisor
    while True:
        try:
            logger.info("Starting Telegram Bot supervisor loop...")
            await start_aurora_bot()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            logger.error(f"Bot encountered critical error: {e}. Restarting in 10 seconds...", exc_info=True)
            await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Aurora Platform shut down.")
