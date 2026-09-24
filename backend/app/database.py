from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request
from sqlalchemy import DateTime, create_engine
from sqlalchemy.engine import URL, Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.types import TypeDecorator

from .config import DEFAULT_DATABASE_PATH  # Preserve existing script imports.


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[datetime]):
    """Store UTC in SQLite and restore its timezone on every read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("A timezone-aware timestamp is required")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def create_database_engine(database_path: Path) -> Engine:
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        URL.create("sqlite+pysqlite", database=str(database_path)),
        connect_args={"check_same_thread": False},
    )


def initialize_database(engine: Engine) -> None:
    """Create new tables or safely extend an existing symptom database."""
    from .migrations import migrate_schema
    from .models import SymptomRecord
    from .daily_health import DailyHealthRecord  # Register the additive daily table.

    SymptomRecord.metadata.create_all(bind=engine)
    migrate_schema(engine)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
