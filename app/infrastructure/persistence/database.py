"""
Database engine and thread-safe session setup for SQLite persistence (D5).

Hardening applied:
  - SQLAlchemy 2.0 DeclarativeBase (modern typing with `Mapped[]`).
  - `PRAGMA foreign_keys=ON` on every connection so ORM relationships are
    actually enforced by SQLite (previously they were decorative).
  - `journal_mode=WAL` + `busy_timeout` so the daemon loop and any web API
    layer can share the database safely without "database is locked".
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, scoped_session

# SQLite Database Location
DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "careersync.db")
)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy 2.0 ORM models."""


_engine_options = {"echo": False}

if DATABASE_URL.startswith("sqlite"):
    _engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_options)

if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - SQLite-only
        """Enforce referential integrity and WAL concurrency on every connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(SessionLocal)


def init_db():
    """Initializes all database tables (idempotent)."""
    Base.metadata.create_all(bind=engine)


def reset_db():
    """Drops all tables and recreates them. Intended for dev/test reset only.

    Note: destructive — never call from a production daemon path.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)