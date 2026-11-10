"""
Database Session & Connection Management.

Initializes SQLAlchemy database engine, connection pool, scoped sessions, and tables.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from aurora.config import Config
from aurora.db.models import (
    Base,
    User,
    UserSession,
    PluginModel,
    BotGroup,
    GBanUser,
    BlockedUser,
    ApprovedGroupUser,
    AllowedUser,
    SudoUser,
)


def get_engine():
    db_url = Config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    connect_args = {}
    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False

    return create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)


engine = get_engine()
SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db_session = scoped_session(SessionFactory)


def init_db():
    """
    Creates database tables if they do not already exist.
    """
    Base.metadata.create_all(bind=engine)
