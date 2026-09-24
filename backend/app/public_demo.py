"""Explicitly isolated, synthetic-only public database bootstrap. No private import."""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import DEFAULT_DATABASE_PATH, REPOSITORY_ROOT
from .daily_health import DailyHealthRecord
from .models import SymptomRecord

MARKER_SQL = "SELECT value FROM public_demo_metadata WHERE key = 'purpose'"
MARKER = "allerwatch-public-synthetic-demo-v1"


def check_demo_database_path(path: Path) -> None:
    """Reject private locations/aliases and unrecognized existing DBs before migration."""
    private = DEFAULT_DATABASE_PATH.resolve()
    if path.is_relative_to(private.parent) or (
        path.exists() and private.exists() and path.samefile(private)
    ):
        raise RuntimeError("PUBLIC_DEMO_MODE cannot use the private database or its directory")
    if not path.exists() or path.stat().st_size == 0:
        return
    try:
        # Read only the ownership marker, never legacy health observations.
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            marker = connection.execute(MARKER_SQL).fetchone()
    except sqlite3.Error:
        marker = None
    if marker != (MARKER,):
        raise RuntimeError("Existing database is not an AllerWatch public demo. Choose a new DATABASE_PATH; do not copy private data.")


def initialize_demo_data(engine: Engine) -> None:
    """Seed both tables together, once, only when both are empty. Never reset data."""
    # Reuse the exact existing offline generators. Render must include repository
    # root (scripts/ as well as backend/); no local database is opened by builders.
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from scripts.demo_data import build_demo_records, DEFAULT_SEED
    from scripts.daily_demo_data import build_daily_demo

    with Session(engine) as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        for model in (SymptomRecord, DailyHealthRecord):
            if session.scalar(select(func.count()).select_from(model).where(model.is_synthetic.is_(False))):
                raise RuntimeError("Public demo database contains real records; startup refused without altering them")
        empty = all(session.scalar(select(func.count()).select_from(model)) == 0
                    for model in (SymptomRecord, DailyHealthRecord))
        if empty:
            symptoms = build_demo_records(seed=DEFAULT_SEED)
            daily = build_daily_demo(symptoms, seed=DEFAULT_SEED)
            session.add_all([*symptoms, *daily])
        session.connection().exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS public_demo_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        session.connection().exec_driver_sql(
            "INSERT OR IGNORE INTO public_demo_metadata (key, value) VALUES ('purpose', ?)", (MARKER,)
        )
        session.commit()
