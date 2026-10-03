"""SQLAlchemy engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def make_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    url = database_url if database_url is not None else get_settings().database_url
    connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
    engine = create_engine(url, echo=echo, future=True, connect_args=connect_args)

    if _is_sqlite(url):

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # WAL improves concurrent writers for double-booking tests under SQLite.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=True, autocommit=False, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    """Idempotent table creation (no Alembic in this assessment)."""
    # Import models so metadata is populated.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
