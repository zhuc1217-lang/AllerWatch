"""Offline daily context conditional on existing synthetic symptoms, never real data."""
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import random
from statistics import mean

from sqlalchemy import delete, func, inspect, select

from .demo_data import DEFAULT_DATABASE_PATH, DEFAULT_SEED, DemoDataError, _write_session
from app.daily_health import DailyHealthRecord, study_date
from app.models import SymptomRecord


@dataclass(frozen=True)
class DailyGenerationSummary:
    generated: int
    start_date: date
    end_date: date
    real_preserved: int


def build_daily_demo(symptoms: list[SymptomRecord], seed: int = DEFAULT_SEED) -> list[DailyHealthRecord]:
    groups: dict[date, list[int]] = {}
    for record in sorted(symptoms, key=lambda item: (item.timestamp, item.id or 0)):
        if record.is_synthetic:
            groups.setdefault(study_date(record.timestamp), []).append(record.tnss)
    if not groups:
        raise DemoDataError("Generate synthetic symptom records before daily-health demo data.")
    rng = random.Random(seed)
    day, last = min(groups), max(groups)
    records = []
    while day <= last:
        # Fixed modest contributions, substantial independent noise. Not a causal model.
        burden = (mean(groups[day]) - 5) if day in groups else 0
        sleep = round(max(3.5, min(10.5, 7.1 - .10 * burden + rng.gauss(0, 1.05))), 1)
        quality = max(1, min(5, round(3 + .40 * (sleep - 7) + rng.gauss(0, .85))))
        stress = max(1, min(5, round(3 + .13 * burden + rng.gauss(0, 1.05))))
        exercise = 0 if rng.random() < .25 else round(max(0, min(120, rng.gauss(40, 28))))
        records.append(DailyHealthRecord(date=day, sleep_duration_hours=sleep, sleep_quality=quality,
            stress_level=stress, exercise_minutes=exercise, notes=None, is_synthetic=True))
        day += timedelta(days=1)
    return records


def _require_daily_table(session):
    if not inspect(session.connection()).has_table(DailyHealthRecord.__tablename__):
        raise DemoDataError("Daily-health table is missing. Start the updated backend first.")


def generate_daily_demo(database_path: Path = DEFAULT_DATABASE_PATH, seed: int = DEFAULT_SEED) -> DailyGenerationSummary:
    with _write_session(database_path) as session:
        _require_daily_table(session)
        if session.scalar(select(func.count()).select_from(DailyHealthRecord).where(DailyHealthRecord.is_synthetic.is_(True))):
            raise DemoDataError("Synthetic daily-health records already exist. Delete daily demo data explicitly before regenerating.")
        records = build_daily_demo(list(session.scalars(select(SymptomRecord).where(SymptomRecord.is_synthetic.is_(True)))), seed)
        real = session.scalar(select(func.count()).select_from(DailyHealthRecord).where(DailyHealthRecord.is_synthetic.is_(False)))
        session.add_all(records)
        session.flush()
        result = DailyGenerationSummary(len(records), records[0].date, records[-1].date, real)
    return result


def delete_daily_demo(database_path: Path = DEFAULT_DATABASE_PATH, report=print) -> tuple[int, int]:
    with _write_session(database_path) as session:
        _require_daily_table(session)
        count = session.scalar(select(func.count()).select_from(DailyHealthRecord).where(DailyHealthRecord.is_synthetic.is_(True)))
        real = session.scalar(select(func.count()).select_from(DailyHealthRecord).where(DailyHealthRecord.is_synthetic.is_(False)))
        report(f"Synthetic daily-health records to remove: {count}")
        deleted = session.execute(delete(DailyHealthRecord).where(DailyHealthRecord.is_synthetic.is_(True))).rowcount
    return deleted, real
