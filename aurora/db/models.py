"""
Aurora Database Models.

Defines SQLAlchemy ORM models for Users, Encrypted User Sessions, and Plugin Metadata.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), default="user", nullable=False)  # "user" or "owner"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session_data = relationship(
        "UserSession", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, role={self.role})>"


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    encrypted_session = Column(Text, nullable=False)
    device_model = Column(String(100), default="Android")
    app_version = Column(String(50), default="10.8.2")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="session_data")

    def __repr__(self):
        return f"<UserSession(telegram_id={self.telegram_id})>"


class PluginModel(Base):
    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    version = Column(String(50), default="1.0.0")
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_owner_only = Column(Boolean, default=False, nullable=False)
    permissions = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<Plugin(name={self.name}, enabled={self.is_enabled})>"


class BotGroup(Base):
    __tablename__ = "bot_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GBanUser(Base):
    __tablename__ = "gban_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target = Column(String(255), unique=True, nullable=False, index=True)
    reason = Column(String(255), default="Globally Banned by Admin")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BlockedUser(Base):
    __tablename__ = "blocked_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ApprovedGroupUser(Base):
    __tablename__ = "approved_group_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, nullable=False, index=True)
    target = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
