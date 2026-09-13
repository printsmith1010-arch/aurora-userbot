"""
Session Security & Encryption Module.

Provides AES-256 Fernet encryption and decryption for sensitive Telegram session strings at rest.
Ensures zero plaintext session strings are written to disk or database.
"""

import base64
import hashlib
from cryptography.fernet import Fernet
from aurora.config import Config


def _get_fernet() -> Fernet:
    """
    Derives a valid 32-byte URL-safe base64 Fernet key from the ENCRYPTION_KEY config string.
    """
    raw_key = str(Config.ENCRYPTION_KEY).encode("utf-8")
    digest = hashlib.sha256(raw_key).digest()
    key_b64 = base64.urlsafe_b64encode(digest)
    return Fernet(key_b64)


def encrypt_session(session_str: str) -> str:
    """
    Encrypts a Telethon StringSession plaintext into a Fernet AES-256 ciphertext token.
    """
    if not session_str:
        return ""
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(session_str.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_session(encrypted_str: str) -> str:
    """
    Decrypts a Fernet AES-256 ciphertext token back to Telethon StringSession plaintext.
    """
    if not encrypted_str:
        return ""
    fernet = _get_fernet()
    decrypted_bytes = fernet.decrypt(encrypted_str.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")
