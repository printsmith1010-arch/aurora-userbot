"""
Multi-User Telethon Session Manager.

Manages isolated TelegramClient instances for multiple concurrent users.
Encrypts sessions at rest using Fernet AES-256 and handles client connection lifecycles.
Enforces strict session isolation per Telegram account.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession

from aurora.config import Config
from aurora.db.models import User, UserSession
from aurora.db.security import decrypt_session, encrypt_session
from aurora.db.session import db_session, init_db

LOGS = logging.getLogger("AuroraSessionManager")


class UserSessionManager:
    def __init__(self):
        self._clients: Dict[int, TelegramClient] = {}
        self._lock = asyncio.Lock()
        init_db()

    async def save_user_session(
        self,
        telegram_id: int,
        session_str: str,
        phone: Optional[str] = None,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        role: str = "user",
    ) -> bool:
        """
        Encrypts session string and saves/updates User & UserSession in database.
        """
        async with self._lock:
            try:
                db = db_session()
                # Check if user is platform owner
                if telegram_id == Config.OWNER_ID:
                    role = "owner"

                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    user = User(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        phone=phone,
                        role=role,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        last_login=datetime.utcnow(),
                    )
                    db.add(user)
                    db.flush()
                else:
                    user.username = username or user.username
                    user.first_name = first_name or user.first_name
                    user.phone = phone or user.phone
                    user.role = role
                    user.is_active = True
                    user.last_login = datetime.utcnow()

                encrypted_str = encrypt_session(session_str)

                session_rec = (
                    db.query(UserSession)
                    .filter(UserSession.telegram_id == telegram_id)
                    .first()
                )
                if not session_rec:
                    session_rec = UserSession(
                        user_id=user.id,
                        telegram_id=telegram_id,
                        encrypted_session=encrypted_str,
                        device_model="Samsung Galaxy S22",
                        app_version="10.8.2",
                        created_at=datetime.utcnow(),
                    )
                    db.add(session_rec)
                else:
                    session_rec.encrypted_session = encrypted_str
                    session_rec.updated_at = datetime.utcnow()

                db.commit()
                LOGS.info(f"Successfully saved encrypted session for user {telegram_id}")
                return True
            except Exception as e:
                LOGS.error(f"Error saving user session for {telegram_id}: {e}")
                db.rollback()
                return False
            finally:
                db_session.remove()

    def get_decrypted_session(self, telegram_id: int) -> Optional[str]:
        """
        Retrieves and decrypts the StringSession for a user from database.
        """
        db = db_session()
        try:
            rec = (
                db.query(UserSession)
                .filter(UserSession.telegram_id == telegram_id)
                .first()
            )
            if not rec or not rec.encrypted_session:
                return None
            return decrypt_session(rec.encrypted_session)
        except Exception as e:
            LOGS.error(f"Error decrypting session for {telegram_id}: {e}")
            return None
        finally:
            db_session.remove()

    async def start_user_session(self, telegram_id: int) -> Optional[TelegramClient]:
        """
        Decrypts session string, instantiates an isolated TelegramClient, and connects.
        """
        async with self._lock:
            if telegram_id in self._clients:
                client = self._clients[telegram_id]
                if client.is_connected():
                    return client

            session_str = self.get_decrypted_session(telegram_id)
            if not session_str:
                LOGS.warning(f"No encrypted session found for user {telegram_id}")
                return None

            try:
                client = TelegramClient(
                    StringSession(session_str),
                    Config.API_ID,
                    Config.API_HASH,
                    device_model="Samsung Galaxy S22",
                    system_version="Android 14",
                    app_version="10.8.2",
                    lang_code="en",
                    system_lang_code="en",
                    auto_reconnect=True,
                    connection_retries=None,
                    retry_delay=5,
                )
                await client.connect()

                if not await client.is_user_authorized():
                    LOGS.warning(f"Session for user {telegram_id} is no longer authorized.")
                    await client.disconnect()
                    return None

                me = await client.get_me()
                client.me = me
                client.uid = me.id

                # Attach Aurora plugin handlers to isolated user client
                from aurora.plugins.admin import register_admin_handlers
                from aurora.plugins.owner import register_owner_handlers
                from aurora.plugins.utility import register_utility_handlers
                from aurora.plugins.clone import register_clone_handlers
                from aurora.plugins.welcome import register_welcome_handlers
                from aurora.plugins.spam import register_spam_handlers
                from aurora.plugins.raid import register_raid_handlers
                from aurora.plugins.tagging import register_tagging_handlers
                from aurora.plugins.fun import register_fun_handlers
                from aurora.plugins.custom import register_custom_handlers
                from aurora.plugins.media import register_media_handlers
                from aurora.plugins.broadcast import register_broadcast_handlers
                from aurora.plugins.pmguard import register_pmguard_handlers
                from aurora.plugins.autoreply import register_autoreply_handlers
                from aurora.plugins.music import register_music_handlers

                register_admin_handlers(client)
                register_owner_handlers(client)
                register_utility_handlers(client)
                register_clone_handlers(client)
                register_welcome_handlers(client)
                register_spam_handlers(client)
                register_raid_handlers(client)
                register_tagging_handlers(client)
                register_fun_handlers(client)
                register_custom_handlers(client)
                register_media_handlers(client)
                register_broadcast_handlers(client)
                register_pmguard_handlers(client)
                register_autoreply_handlers(client)
                register_music_handlers(client)

                self._clients[telegram_id] = client
                LOGS.info(f"Started isolated session for user @{getattr(me, 'username', None) or me.id}")
                return client
            except Exception as e:
                LOGS.error(f"Failed to start session for user {telegram_id}: {e}")
                return None

    async def stop_user_session(self, telegram_id: int) -> bool:
        """
        Disconnects client for a given user and removes from active pool.
        """
        async with self._lock:
            if telegram_id in self._clients:
                client = self._clients.pop(telegram_id)
                try:
                    await client.disconnect()
                    LOGS.info(f"Stopped session for user {telegram_id}")
                    return True
                except Exception as e:
                    LOGS.error(f"Error disconnecting user {telegram_id}: {e}")
            return False

    async def revoke_user_session(self, telegram_id: int) -> bool:
        """
        Revokes user session: disconnects client, deletes encrypted session from DB.
        """
        await self.stop_user_session(telegram_id)
        db = db_session()
        try:
            db.query(UserSession).filter(UserSession.telegram_id == telegram_id).delete()
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.is_active = False
            db.commit()
            LOGS.info(f"Revoked and deleted session for user {telegram_id}")
            return True
        except Exception as e:
            LOGS.error(f"Error revoking session for user {telegram_id}: {e}")
            db.rollback()
            return False
        finally:
            db_session.remove()

    def get_active_client(self, telegram_id: int) -> Optional[TelegramClient]:
        """
        Returns active TelegramClient instance for specified user ID if connected.
        """
        return self._clients.get(telegram_id)

    def get_all_active_users(self) -> List[int]:
        """
        Returns list of all active telegram_ids currently connected.
        """
        return list(self._clients.keys())

    async def load_all_sessions(self) -> int:
        """
        Loads and starts all active sessions registered in database upon platform launch.
        """
        db = db_session()
        try:
            records = db.query(UserSession).all()
            started_count = 0
            for rec in records:
                client = await self.start_user_session(rec.telegram_id)
                if client:
                    started_count += 1
            LOGS.info(f"Loaded {started_count}/{len(records)} active user sessions.")
            return started_count
        finally:
            db_session.remove()


# Global Singleton Instance
session_manager = UserSessionManager()
