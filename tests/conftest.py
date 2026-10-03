"""Shared fixtures: isolated temporary SQLite databases for each test."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import create_schema, make_engine, make_session_factory
from app.seed import run_seed


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def database_url(db_path: Path) -> str:
    # Three slashes + absolute path for Windows-friendly SQLite URLs.
    return f"sqlite:///{db_path.as_posix()}"


@pytest.fixture
def engine(database_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", os.getenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00"))
    monkeypatch.setenv("ADMIN_API_KEY", os.getenv("ADMIN_API_KEY", "change-me"))
    get_settings.cache_clear()
    eng = make_engine(database_url)
    create_schema(eng)
    return eng


@pytest.fixture
def session(engine) -> Iterator[Session]:
    factory = make_session_factory(engine)
    db = factory()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture
def seeded_engine(database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Temporary SQLite DB with Appendix B–E reference data seeded."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")
    monkeypatch.setenv("NOTIFICATIONS_LOG_PATH", str(tmp_path / "notifications.log"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "enquiry_audit.jsonl"))
    get_settings.cache_clear()
    run_seed(database_url, reset=True)
    return make_engine(database_url)


@pytest.fixture
def seeded_session(seeded_engine) -> Iterator[Session]:
    factory = make_session_factory(seeded_engine)
    db = factory()
    try:
        yield db
        db.commit()
    finally:
        db.close()
