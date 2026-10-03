"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import make_engine, make_session_factory, create_schema
from app.llm import LLMClient, get_llm_client

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = make_engine(settings.database_url)
        create_schema(_engine)
    return _engine


def get_db() -> Iterator[Session]:
    factory = make_session_factory(get_engine())
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_llm() -> LLMClient:
    return get_llm_client()
