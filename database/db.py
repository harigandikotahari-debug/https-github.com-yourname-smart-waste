"""SQLAlchemy engine/session setup.

Uses SQLite for local development/demo. All models below stick to portable
column types and constraints (no SQLite-only pragmas or types), so pointing
`database.url` in config/settings.yaml at a `postgresql+psycopg2://` URL is
the only change needed to run against Postgres in production.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from utils.config import db_url

_connect_args = {"check_same_thread": False} if db_url().startswith("sqlite") else {}

engine = create_engine(db_url(), echo=False, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
