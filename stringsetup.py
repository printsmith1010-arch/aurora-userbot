#!/usr/bin/env python3
# (c) https://t.me/TelethonChat/37677
# This Source Code Form is subject to the terms of the GNU
# General Public License, v.3.0. If a copy of the GPL was not distributed with this
# file, You can obtain one at https://www.gnu.org/licenses/gpl-3.0.en.html.

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

import os
import sys
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

DEFAULT_APP_ID = 25307036
DEFAULT_API_HASH = "11285731405a814dd4b3af1c61bdd482"

print("\n=======================================================")
print("      Aurora Telethon StringSession Generator          ")
print("=======================================================")
app_id_input = input(f"Enter APP ID [press Enter for default {DEFAULT_APP_ID}]: ").strip()
APP_ID = int(app_id_input) if app_id_input else DEFAULT_APP_ID

api_hash_input = input(f"Enter API HASH [press Enter for default]: ").strip()
API_HASH = api_hash_input if api_hash_input else DEFAULT_API_HASH

print("\n[+] Connecting to Telegram...")
with TelegramClient(StringSession(), APP_ID, API_HASH) as client:
    session_string = client.session.save()
    print("\n=======================================================")
    print("YOUR STRING SESSION (Keep this secret!):")
    print("=======================================================")
    print(session_string)
    print("=======================================================\n")
    try:
        client.send_message("me", f"**Your Aurora String Session:**\n`{session_string}`")
        print("[+] Session string has also been sent to your Telegram 'Saved Messages'!")
    except Exception:
        pass
    print("\n👉 To host on your bot, open PM with your bot and send:")
    print(f"/hostsession {session_string}\n")
