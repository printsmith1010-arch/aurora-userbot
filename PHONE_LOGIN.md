# Phone-number login

This fork uses phone-number authentication via Telegram Bot Chat or CLI.

## Interactive Telegram Bot Chat Login (Recommended)

1. Configure your Bot Token in `config.py`:
   `TG_BOT_TOKEN = "8679611350:AAHA41eGl2TRPzefxf1jYzLFPyrhN_m3JqY"`

2. Start the interactive bot login script:
   `python login.py`

3. Open Telegram and search for your bot username (printed in the terminal console).
4. Send `/start` to your bot in Telegram chat.
5. Send your **Phone Number** with country code (e.g. `+1234567890`).
6. Enter the **Telegram OTP** code sent to your account.
7. If 2-step verification is enabled, enter your **2FA Password** (automatically deleted from chat for security).
8. Once logged in, your `STRING_SESSION` is automatically saved to `config.py`.
9. Start your userbot with:
   `python -m userbot`

## Console CLI Login (Alternative)

If you prefer terminal-based login:
`python login.py --cli`

## Important

Telegram's MTProto protocol requires application credentials internally.
This build uses built-in application credentials so API ID / API Hash are not required as interactive inputs.

The generated `StringSession` is a credential for your Telegram account.
Never publish `config.py`, `.session` files, or your `StringSession`.
