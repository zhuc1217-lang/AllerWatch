"""Additive nullable-column migrations; back up first and preserve legacy values."""

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy.engine import Engine

# Fixed identifiers only: no SQL names or definitions come from user input.
ENVIRONMENT_COLUMNS = {
    "temperature_c": "FLOAT",
    "relative_humidity": "FLOAT",
    "pm2_5": "FLOAT",
    "pm10": "FLOAT",
    "us_aqi": "FLOAT",
    "environment_timestamp": "DATETIME",
    "weather_timestamp": "DATETIME",
    "air_quality_timestamp": "DATETIME",
    "environment_latitude": "FLOAT",
    "environment_longitude": "FLOAT",
}


def _backup_database(database_path: Path) -> Path:
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"{database_path.stem}-before-migration-{stamp}-{uuid4().hex[:8]}.sqlite3"
    # SQLite's backup API includes committed WAL data; copying the file may not.
    # Use a separate read connection while the migration holds a reserved lock.
    with closing(sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
    return backup


def migrate_schema(engine: Engine) -> Path | None:
    """Back up once, then add missing nullable columns atomically; never rebuild."""
    with engine.connect() as connection:
        # Explicit BEGIN is needed for transactional DDL with Python's SQLite driver.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            additions = {
                "symptom_records": {**ENVIRONMENT_COLUMNS, "received_at": "DATETIME"},
                "daily_health_records": {"updated_at": "DATETIME"},
            }
            missing = []
            for table, columns in additions.items():
                existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
                if not existing:
                    raise RuntimeError(f"Create {table} before applying its migration")
                missing.extend((table, name, kind) for name, kind in columns.items() if name not in existing)
            if not missing:
                connection.commit()
                return None
            backup = _backup_database(Path(engine.url.database).resolve())
            for table, name, kind in missing:
                # No default: old observations retain NULL, never today's conditions.
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
            connection.commit()
            return backup
        except Exception:
            connection.rollback()
            raise
