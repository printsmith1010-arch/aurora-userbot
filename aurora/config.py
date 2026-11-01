"""
Aurora Multi-User Telegram Platform Configuration.

Loads environment variables from .env and system environment.
Enforces zero exposure of API hashes, bot tokens, database passwords, or encryption keys.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    # Telegram MTProto Application Credentials (Global Platform Credentials)
    API_ID = int(os.environ.get("TELEGRAM_API_ID", "25307036"))
    API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

    # Optional Hoster Bot Token (Optional for userbot, used for aux hoster bot)
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")

    # Owner Credentials
    OWNER_ID = int(os.environ.get("OWNER_ID", "5342258541"))
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "tglegend77")

    # Database URI
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///aurora.db")

    # AES-256 Fernet Encryption Key for Session Storage at Rest
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")

    # Userbot Command Handler Prefix
    COMMAND_HANDLER = os.environ.get("COMMAND_HANDLER", ".")

    # Logging Configuration
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    @classmethod
    def get_masked_api_hash(cls) -> str:
        return "********" if cls.API_HASH else "Not Configured"

    @classmethod
    def get_masked_bot_token(cls) -> str:
        return "********" if cls.TG_BOT_TOKEN else "Not Configured"

    @classmethod
    def get_masked_encryption_key(cls) -> str:
        return "********" if cls.ENCRYPTION_KEY else "Not Configured"

    @classmethod
    def get_masked_db_url(cls) -> str:
        if not cls.DATABASE_URL:
            return "Not Configured"
        if "@" in cls.DATABASE_URL:
            prefix, rest = cls.DATABASE_URL.split("@", 1)
            driver = prefix.split("://")[0] if "://" in prefix else "db"
            return f"{driver}://********@{rest}"
        return cls.DATABASE_URL


def sanitize_text(text: str) -> str:
    """
    Sanitizes any string output by replacing secrets (API_HASH, TG_BOT_TOKEN, ENCRYPTION_KEY, StringSessions)
    with masked placeholders ('********').
    """
    if not text:
        return ""
    s = str(text)
    if Config.API_HASH:
        s = s.replace(Config.API_HASH, "********")
    if Config.TG_BOT_TOKEN:
        s = s.replace(Config.TG_BOT_TOKEN, "********")
    if Config.ENCRYPTION_KEY:
        s = s.replace(Config.ENCRYPTION_KEY, "********")
    # Mask Telethon StringSession pattern (1BUpWzW...)
    s = re.sub(r"1[A-Za-z0-9_-]{50,}", "********", s)
    return s
