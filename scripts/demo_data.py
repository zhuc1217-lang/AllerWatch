"""Offline development fixtures only; never patient data or an analysis model."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import math
from pathlib import Path
import random
import sys

# Allow both direct Windows script execution and imports from backend pytest.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from app.database import DEFAULT_DATABASE_PATH, create_database_engine
from app.models import SymptomRecord
from app.services.china_aqi import POLLUTANTS, calculate_china_aqi

DAYS = 90
DEFAULT_SEED = 42
ENVIRONMENT_FIELDS = ("temperature_c", "relative_humidity", *POLLUTANTS, "china_aqi_estimate")
# Keep the original missingness RNG slots, without changing symptom/PM draws.
_MISSING_SLOTS = ("temperature_c", "relative_humidity", "pm2_5", "pm10", "air_index")
NASAL_FIELDS = ("nasal_congestion", "sneezing", "runny_nose", "nasal_itching")


class DemoDataError(Exception):
    """A safe, actionable CLI failure; no records should be partially changed."""


@dataclass(frozen=True)
class GenerationSummary:
    generated: int
    start_date: date
    end_date: date
    real_preserved: int
    missing_environment: int


def default_end_date() -> date:
    return datetime.now(UTC).date() - timedelta(days=1)


def validate_end_date(end_date: date) -> None:
    if not date(1900, 1, 1) <= end_date <= default_end_date():
        raise DemoDataError("End date must be 1900-01-01 or later and before today in UTC.")


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score(value: float, maximum: int = 3) -> int:
    return int(_bounded(round(value), 0, maximum))


def build_demo_records(*, seed: int = DEFAULT_SEED, end_date: date | None = None) -> list[SymptomRecord]:
    """Return unpersisted model entities; deterministic for a seed and end date."""
    end_date = end_date if end_date is not None else default_end_date()
    validate_end_date(end_date)
    start_date = end_date - timedelta(days=DAYS - 1)
    rng = random.Random(seed)  # Never mutate another component's global RNG.
    # A fictional temperate scenario, deliberately independent of real coordinates.
    temperature, humidity, pollution = 22.0, 60.0, 15.0
    susceptibility, flare, pollution_episode = 0.0, 0.0, 0.0
    episode_starts = set(rng.sample(range(5, DAYS - 6), 4))
    flare_starts = set(rng.sample(range(2, DAYS - 3), 4))
    records = []
    # Separate stream: adding gases must not change TNSS, time, medication or PM.
    gas_rng = random.Random(f"{seed}:china-aqi-gases")
    no2, so2, co, ozone = 25.0, 8.0, 500.0, 65.0

    for day_index in range(DAYS):
        day = start_date + timedelta(days=day_index)
        temperature = _bounded(
            0.88 * temperature + 0.12 * (22 + 5 * math.sin(day_index / 20)) + rng.gauss(0, 0.8), 7, 32
        )
        humidity = _bounded(
            0.82 * humidity + 0.18 * (62 + 12 * math.cos(day_index / 13)) + rng.gauss(0, 3), 30, 90
        )
        pollution_episode *= 0.72
        if day_index in episode_starts:
            pollution_episode += rng.uniform(40, 65)
        pollution = _bounded(0.65 * pollution + 0.35 * (14 + pollution_episode) + rng.gauss(0, 2.5), 2, 90)
        susceptibility = 0.55 * susceptibility + rng.gauss(0, 0.55)
        flare *= 0.45
        if day_index in flare_starts:
            flare += rng.uniform(1.1, 1.7)

        # One or two distinct sessions; hours are on a documented fictional UTC clock.
        sessions = sorted(rng.sample([(7, 10), (14, 17), (19, 22)], 2 if rng.random() < 0.5 else 1))
        for first_hour, last_hour in sessions:
            timestamp = datetime.combine(day, time(
                hour=rng.randrange(first_hour, last_hour), minute=rng.randrange(60), second=rng.randrange(60)
            ), tzinfo=UTC)
            afternoon = first_hour == 14
            temp = round(_bounded(temperature + (1.5 if afternoon else -0.6) + rng.gauss(0, 0.4), 5, 35), 1)
            rh = round(_bounded(humidity + (-3 if afternoon else 1) + rng.gauss(0, 1.5), 25, 95), 1)
            pm = round(_bounded(pollution + rng.gauss(0, 1.2), 1, 100), 1)
            pm10 = round(_bounded(pm * 1.45 + 5 + rng.gauss(0, 2), pm, 160), 1)

            # Small environmental terms; independent persistent/noisy factors dominate.
            # AQI shares PM2.5's contribution, so do not count it as a second cause.
            burden = 0.85 + 0.020 * (pm - 18) + 0.004 * (rh - 60)
            burden += susceptibility + flare + rng.gauss(0, 0.30)
            scores = {
                field: _score(burden + offset + rng.gauss(0, 0.65))
                for field, offset in zip(NASAL_FIELDS, (0.18, 0.05, -0.02, -0.15))
            }
            record = SymptomRecord(
                timestamp=timestamp, **scores,
                eye_symptoms=_score(0.8 * burden + rng.gauss(0, 0.9)),
                overall_severity=_score(2.8 * burden + rng.gauss(0, 1.1), 10),
                medication_taken=False, is_synthetic=True,
                notes="Synthetic development observation; not a patient record." if rng.random() < 0.05 else None,
                temperature_c=temp, relative_humidity=rh, pm2_5=pm, pm10=pm10,
                environment_timestamp=timestamp + timedelta(seconds=3),
                weather_timestamp=timestamp.replace(minute=timestamp.minute // 15 * 15, second=0),
                air_quality_timestamp=timestamp.replace(minute=0, second=0),
                environment_latitude=None, environment_longitude=None,
            )
            # Sampling medication never changes current/future symptom states.
            probability = 0.10 + 0.65 / (1 + math.exp(-(record.tnss - 6) / 1.8))
            record.medication_taken = rng.random() < probability
            # No new gas enters the symptom burden formula. Persistent noisy ambient
            # profiles are demonstrations, not fitted to outcomes or target accuracy.
            no2 = _bounded(0.75 * no2 + 0.25 * (15 + 0.55 * pm) + gas_rng.gauss(0, 4), 2, 160)
            so2 = _bounded(0.8 * so2 + 0.2 * (4 + 0.12 * pm) + gas_rng.gauss(0, 1.4), 0.5, 60)
            co = _bounded(0.8 * co + 0.2 * (320 + 12 * pm) + gas_rng.gauss(0, 70), 100, 3000)
            ozone = _bounded(0.7 * ozone + 0.3 * (55 + (35 if afternoon else 0) + 0.5 * temp) + gas_rng.gauss(0, 12), 5, 220)
            record.nitrogen_dioxide, record.sulfur_dioxide = round(no2, 1), round(so2, 1)
            record.carbon_monoxide, record.ozone = round(co, 1), round(ozone, 1)
            records.append(record)

    # Fix an approximately 6% record-level missingness rate; preserve observed zeros.
    for record in rng.sample(records, round(len(records) * 0.06)):
        missing = rng.choice([
            ("temperature_c", "relative_humidity"), ("pm2_5", "pm10", "air_index"),
            (rng.choice(_MISSING_SLOTS),), _MISSING_SLOTS,
        ])
        # Whole-air outages remove every pollutant. A single index-slot outage
        # represents missing O3; never invent the unavailable sixth concentration.
        fields = set(missing) - {"air_index"}
        if "air_index" in missing:
            fields.update(POLLUTANTS if "pm2_5" in missing else ("ozone",))
        for field in fields:
            setattr(record, field, None)
        if record.temperature_c is None and record.relative_humidity is None:
            record.weather_timestamp = None
        if all(getattr(record, field) is None for field in POLLUTANTS):
            record.air_quality_timestamp = None
        if all(getattr(record, field) is None for field in ENVIRONMENT_FIELDS):
            record.environment_timestamp = None
    for record in records:
        estimate = calculate_china_aqi(**{field: getattr(record, field) for field in POLLUTANTS})
        record.china_aqi_estimate = estimate.aqi
        record.china_aqi_primary_pollutant = estimate.primary_pollutant
    return records


@contextmanager
def _write_session(database_path: Path) -> Iterator[Session]:
    path = database_path.resolve()
    if not path.is_file():
        raise DemoDataError(f"Database does not exist: {path}. Start the backend once to initialise it.")
    engine = create_database_engine(path)
    try:
        inspector = inspect(engine)
        expected = {column.name for column in SymptomRecord.__table__.columns}
        if not inspector.has_table("symptom_records") or not expected <= {
            column["name"] for column in inspector.get_columns("symptom_records")
        }:
            raise DemoDataError("Database schema is not current. Start the updated backend before using demo scripts.")
        with Session(engine) as session:
            # Serialise duplicate checks and writes, including concurrent script runs.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
    finally:
        engine.dispose()


def _count(session: Session, synthetic: bool) -> int:
    return session.scalar(select(func.count()).select_from(SymptomRecord).where(
        SymptomRecord.is_synthetic.is_(synthetic)
    ))


def generate_demo_data(database_path: Path = DEFAULT_DATABASE_PATH, *, seed: int = DEFAULT_SEED,
                       end_date: date | None = None) -> GenerationSummary:
    records = build_demo_records(seed=seed, end_date=end_date)
    with _write_session(database_path) as session:
        count = _count(session, True)
        if count:
            raise DemoDataError(
                f"Stopped: {count} synthetic records already exist. "
                "Run scripts/delete_demo_data.py for this database before generating again."
            )
        real = _count(session, False)
        session.add_all(records)
        session.flush()
        summary = GenerationSummary(
            generated=len(records), start_date=records[0].timestamp.date(), end_date=records[-1].timestamp.date(),
            real_preserved=real,
            missing_environment=sum(any(getattr(record, field) is None for field in ENVIRONMENT_FIELDS) for record in records),
        )
    return summary


def delete_demo_data(database_path: Path = DEFAULT_DATABASE_PATH, *, report: Callable[[str], None] = print) -> tuple[int, int]:
    with _write_session(database_path) as session:
        count = _count(session, True)
        real = _count(session, False)
        report(f"Synthetic records to remove: {count}")
        deleted = session.execute(delete(SymptomRecord).where(SymptomRecord.is_synthetic.is_(True))).rowcount
    return deleted, real
