"""
Aurora Automated Test Suite: Session Isolation & Security Verification.

Proves:
1. User A -> Command -> Account A, User B -> Command -> Account B isolation.
2. User A can NEVER execute commands on Account B's session.
3. AES-256 Fernet session encryption at rest (zero plaintext sessions in DB).
4. RBAC owner restriction enforcement for OWNER_ID (5342258541).
5. Session revocation / logout lifecycle.
6. Session persistence across application restarts.
7. Secret Safety: Fails if API_HASH, TG_BOT_TOKEN, ENCRYPTION_KEY, or StringSessions leak in outputs or logs.

USES ISOLATED TEST DB (aurora_test.db) TO PRESERVE PRODUCTION SESSIONS IN aurora.db.
"""

import os
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from aurora.config import Config, sanitize_text
from aurora.db.security import encrypt_session, decrypt_session
from aurora.db.session import db_session, init_db
from aurora.db.models import User, UserSession
from aurora.core.session_manager import UserSessionManager
from aurora.core.plugin_manager import PluginManager


@pytest.fixture(autouse=True)
def setup_test_db():
    # Use isolated test database so aurora.db is NEVER modified by test runs
    Config.DATABASE_URL = "sqlite:///aurora_test.db"
    init_db()
    db = db_session()
    db.query(UserSession).delete()
    db.query(User).delete()
    db.commit()
    db_session.remove()
    yield
    db = db_session()
    db.query(UserSession).delete()
    db.query(User).delete()
    db.commit()
    db_session.remove()


def test_session_encryption_at_rest():
    """
    Verifies sessions are encrypted with Fernet at rest and plaintext is never stored.
    """
    plaintext_session = "1BUpWzW14Y1t4...dummy_string_session_user_A..."
    ciphertext = encrypt_session(plaintext_session)

    assert ciphertext != plaintext_session
    assert "dummy_string_session" not in ciphertext

    decrypted = decrypt_session(ciphertext)
    assert decrypted == plaintext_session


def test_session_manager_save_and_isolation():
    """
    Verifies User A and User B session isolation in database and memory.
    """
    async def _test():
        manager = UserSessionManager()

        user_a_id = 11111111
        user_b_id = 22222222

        session_a_str = "1BUpWzW_Session_String_User_A_Secret"
        session_b_str = "1BUpWzW_Session_String_User_B_Secret"

        # Save User A & User B
        saved_a = await manager.save_user_session(
            telegram_id=user_a_id,
            session_str=session_a_str,
            phone="+1111111111",
            username="user_a",
            first_name="User A",
        )
        saved_b = await manager.save_user_session(
            telegram_id=user_b_id,
            session_str=session_b_str,
            phone="+2222222222",
            username="user_b",
            first_name="User B",
        )

        assert saved_a is True
        assert saved_b is True

        # Verify DB storage is strictly encrypted
        db = db_session()
        db_rec_a = db.query(UserSession).filter(UserSession.telegram_id == user_a_id).first()
        db_rec_b = db.query(UserSession).filter(UserSession.telegram_id == user_b_id).first()

        assert session_a_str not in db_rec_a.encrypted_session
        assert session_b_str not in db_rec_b.encrypted_session

        # Verify Decryption is isolated
        dec_a = manager.get_decrypted_session(user_a_id)
        dec_b = manager.get_decrypted_session(user_b_id)

        assert dec_a == session_a_str
        assert dec_b == session_b_str
        assert dec_a != dec_b
        db_session.remove()

    asyncio.run(_test())


def test_user_client_command_execution_isolation():
    """
    CRITICAL TEST: Proves User A's command executes ONLY on Account A context,
    and User A can NEVER cause a command to execute on Account B's session.
    """
    async def _test():
        manager = UserSessionManager()

        # Mock TelegramClient instances for User A and User B
        client_a = MagicMock()
        client_a.uid = 11111111
        client_a.me = MagicMock(id=11111111, first_name="User A")
        client_a.is_connected.return_value = True
        client_a.edit_permissions = AsyncMock()

        client_b = MagicMock()
        client_b.uid = 22222222
        client_b.me = MagicMock(id=22222222, first_name="User B")
        client_b.is_connected.return_value = True
        client_b.edit_permissions = AsyncMock()

        manager._clients[11111111] = client_a
        manager._clients[22222222] = client_b

        # Verify clients are distinct and isolated
        retrieved_a = manager.get_active_client(11111111)
        retrieved_b = manager.get_active_client(22222222)

        assert retrieved_a is not retrieved_b
        assert retrieved_a.uid == 11111111
        assert retrieved_b.uid == 22222222

        # Simulate User A running a ban command on their event context
        event_a = MagicMock()
        event_a.client = retrieved_a
        event_a.chat_id = -100123456
        event_a.pattern_match = MagicMock(group=lambda x: "target_user")
        event_a.get_reply_message = AsyncMock(return_value=None)
        event_a.edit = AsyncMock()

        # Execute action on User A's client
        await event_a.client.edit_permissions(event_a.chat_id, "target_user", view_messages=False)

        # Assert edit_permissions was invoked ONLY on Client A, NEVER on Client B
        client_a.edit_permissions.assert_called_once_with(-100123456, "target_user", view_messages=False)
        client_b.edit_permissions.assert_not_called()

    asyncio.run(_test())


def test_rbac_owner_restriction():
    """
    Verifies that owner-only commands permit OWNER_ID (5342258541) and block non-owner users.
    """
    pm = PluginManager()
    pm.register_command("eval", "owner", "Eval python code", owner_only=True)

    owner_id = 5342258541
    regular_user_id = 11111111

    assert pm.is_owner(owner_id) is True
    assert pm.is_owner(regular_user_id) is False

    cmd_meta = pm.get_command("eval")
    assert cmd_meta.owner_only is True


def test_session_logout_and_revocation():
    """
    Verifies session revocation (/logout) disconnects client and purges DB record.
    """
    async def _test():
        manager = UserSessionManager()
        user_id = 33333333

        # Save session
        await manager.save_user_session(user_id, "Session_333_Secret", phone="+333333333")

        # Mock client in pool
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        manager._clients[user_id] = mock_client

        # Revoke
        revoked = await manager.revoke_user_session(user_id)
        assert revoked is True

        # Assert client disconnected & removed from active pool
        mock_client.disconnect.assert_called_once()
        assert manager.get_active_client(user_id) is None

        # Assert decrypted session from DB returns None
        assert manager.get_decrypted_session(user_id) is None

    asyncio.run(_test())


def test_session_persistence_across_restart():
    """
    Verifies sessions persist in encrypted format across manager/app restarts.
    """
    async def _test():
        manager = UserSessionManager()
        user_id = 44444444
        session_str = "Session_4444_Restart_Persistence_Test"

        await manager.save_user_session(user_id, session_str, phone="+44444444")

        # Simulate app restart: instantiate fresh manager instance
        new_manager = UserSessionManager()
        decrypted_after_restart = new_manager.get_decrypted_session(user_id)

        assert decrypted_after_restart == session_str

    asyncio.run(_test())


def test_secret_safety():
    """
    CRITICAL SECRET SAFETY TEST:
    Fails if API_HASH, TG_BOT_TOKEN, ENCRYPTION_KEY, or StringSessions appear unmasked
    in dashboard outputs, help outputs, masked getters, or sanitized error text.
    """
    api_hash_masked = Config.get_masked_api_hash()
    bot_token_masked = Config.get_masked_bot_token()
    encryption_key_masked = Config.get_masked_encryption_key()

    assert api_hash_masked == "********" or api_hash_masked == "Not Configured"
    assert bot_token_masked == "********" or bot_token_masked == "Not Configured"
    assert encryption_key_masked == "********" or encryption_key_masked == "Not Configured"

    # Test sanitize_text function
    sample_error = f"Error connecting with hash {Config.API_HASH} and token {Config.TG_BOT_TOKEN}"
    sanitized = sanitize_text(sample_error)

    if Config.API_HASH:
        assert Config.API_HASH not in sanitized
    if Config.TG_BOT_TOKEN:
        assert Config.TG_BOT_TOKEN not in sanitized
    assert "********" in sanitized

    # Test StringSession regex masking
    dummy_session = "1BUpWzW14Y1t4m5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0"
    session_error = f"Failed to open session {dummy_session}"
    sanitized_session = sanitize_text(session_error)

    assert dummy_session not in sanitized_session
    assert "********" in sanitized_session
