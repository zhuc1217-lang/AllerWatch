from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import random
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete

from app.models import SymptomRecord
from app.schemas import SymptomRecordCreate
from scripts import demo_data as demo

END_DATE = date(2025, 3, 31)
ROOT = Path(__file__).resolve().parents[2]


def fields(record):
    return {column.name: getattr(record, column.name) for column in SymptomRecord.__table__.columns if column.name != "id"}


def database_rows(path, *, real_only=False):
    with closing(sqlite3.connect(path)) as connection:
        predicate = " WHERE is_synthetic=0" if real_only else ""
        return connection.execute(f"SELECT * FROM symptom_records{predicate} ORDER BY id").fetchall()


@pytest.fixture
def real_records(client, database_path, valid_record):
    values = SymptomRecordCreate.model_validate(valid_record | {"is_synthetic": False}).model_dump()
    with client.app.state.session_factory() as session:
        session.add(SymptomRecord(**(values | {"notes": "Preservation fixture — 鼻炎", "temperature_c": 0.0, "pm2_5": 0.0})))
        session.add(SymptomRecord(**(values | {"notes": None})))
        session.commit()
    return database_rows(database_path, real_only=True)


@pytest.mark.parametrize("seed", [0, 1, 42, 99])
def test_generated_fields_ranges_missingness_and_tnss(seed):
    records = demo.build_demo_records(seed=seed, end_date=END_DATE)
    assert 90 <= len(records) <= 180
    assert all(record.is_synthetic is True for record in records)
    assert all(record.id is None for record in records)
    assert "tnss" not in SymptomRecord.__table__.columns
    bounds = {"temperature_c": (5, 35), "relative_humidity": (25, 95), "pm2_5": (1, 100), "pm10": (1, 160), "us_aqi": (0, 200)}
    missing = 0
    for record in records:
        for field in (*demo.NASAL_FIELDS, "eye_symptoms"):
            assert type(getattr(record, field)) is int and 0 <= getattr(record, field) <= 3
        assert type(record.overall_severity) is int and 0 <= record.overall_severity <= 10
        assert type(record.medication_taken) is bool
        assert record.tnss == sum(getattr(record, field) for field in demo.NASAL_FIELDS)
        old_tnss = record.tnss
        record.eye_symptoms = 3 - record.eye_symptoms
        assert record.tnss == old_tnss
        for field, (low, high) in bounds.items():
            value = getattr(record, field)
            assert value is None or (isinstance(value, (int, float)) and low <= value <= high)
        if record.pm2_5 is not None and record.pm10 is not None:
            assert record.pm10 >= record.pm2_5
        if record.pm2_5 is not None and record.us_aqi is not None:
            assert record.us_aqi == demo._synthetic_aqi(record.pm2_5)
        missing += any(getattr(record, field) is None for field in demo.ENVIRONMENT_FIELDS)
        assert record.environment_latitude is record.environment_longitude is None
        if record.environment_timestamp is not None:
            assert 0 <= (record.environment_timestamp - record.timestamp).total_seconds() <= 10
        if record.weather_timestamp is not None:
            assert timedelta(0) <= record.timestamp - record.weather_timestamp < timedelta(minutes=15)
        if record.air_quality_timestamp is not None:
            assert timedelta(0) <= record.timestamp - record.air_quality_timestamp < timedelta(hours=1)
    assert 0.03 <= missing / len(records) <= 0.08
    assert sum(record.notes is None for record in records) > len(records) * 0.85


def test_temporal_coverage_varied_plausible_times_and_continuity():
    records = demo.build_demo_records(seed=42, end_date=END_DATE)
    days = Counter(record.timestamp.date() for record in records)
    assert len(days) == 90
    assert min(days) == END_DATE - timedelta(days=89) and max(days) == END_DATE
    assert set(days.values()) == {1, 2}
    assert len({record.timestamp for record in records}) == len(records)
    assert len({record.timestamp.time() for record in records}) > 50
    assert all(record.timestamp.tzinfo == UTC and record.timestamp.hour in {*range(7, 10), *range(14, 17), *range(19, 22)} for record in records)
    temperatures = [r.temperature_c for r in records if r.temperature_c is not None]
    assert max(abs(a-b) for a, b in zip(temperatures, temperatures[1:])) < 8
    particles = [r.pm2_5 for r in records if r.pm2_5 is not None]
    assert any(a > 35 and b > 35 for a, b in zip(particles, particles[1:]))
    assert max(abs(a-b) for a, b in zip(particles, particles[1:])) < 45


def test_varied_symptoms_and_probabilistic_medication_without_correlation_analysis():
    records = demo.build_demo_records(seed=42, end_date=END_DATE)
    assert sum(1 <= r.tnss <= 7 for r in records) > len(records) // 2
    assert any(r.tnss >= 9 for r in records)
    assert any(r.tnss >= 9 and not r.medication_taken for r in records)
    assert any(4 <= r.tnss <= 7 and r.medication_taken for r in records)
    # A range of symptom scores under similar simulated pollution; no correlation calculation.
    scores_by_pollution_band = defaultdict(set)
    for r in records:
        if r.pm2_5 is not None:
            scores_by_pollution_band[int(r.pm2_5 // 10)].add(r.tnss)
    assert any(len(scores) >= 6 for scores in scores_by_pollution_band.values())


def test_seed_and_end_date_reproduce_values_without_global_rng_side_effects():
    state = random.getstate()
    first = [fields(r) for r in demo.build_demo_records(seed=42, end_date=END_DATE)]
    second = [fields(r) for r in demo.build_demo_records(seed=42, end_date=END_DATE)]
    different = [fields(r) for r in demo.build_demo_records(seed=43, end_date=END_DATE)]
    assert first == second and first != different
    assert random.getstate() == state


def test_default_window_ends_on_previous_utc_day():
    before = datetime.now(UTC).date()
    result = demo.build_demo_records()
    after = datetime.now(UTC).date()
    assert result[-1].timestamp.date() in {before - timedelta(days=1), after - timedelta(days=1)}


@pytest.mark.parametrize("end_date", [date(1899, 12, 31), datetime.now(UTC).date(), date(9999, 12, 31)])
def test_invalid_end_date_is_rejected(end_date):
    with pytest.raises(demo.DemoDataError):
        demo.build_demo_records(end_date=end_date)


@pytest.mark.parametrize("pm,expected", [(0, 0), (9, 50), (9.1, 51), (35.4, 100), (35.5, 101), (55.4, 150), (55.5, 151)])
def test_synthetic_aqi_breakpoints(pm, expected):
    assert demo._synthetic_aqi(pm) == expected


def test_generate_api_delete_regenerate_preserve_all_real_fields(client, database_path, real_records):
    summary = demo.generate_demo_data(database_path, seed=42, end_date=END_DATE)
    assert summary.real_preserved == 2 and summary.generated == 140 and summary.missing_environment == 8
    assert database_rows(database_path, real_only=True) == real_records
    response = client.get("/symptoms")
    assert response.status_code == 200
    generated = [record for record in response.json() if record["is_synthetic"] is True]
    assert len(generated) == summary.generated
    assert len([r for r in response.json() if r["is_synthetic"] is False]) == 2
    assert sum(any(r[field] is None for field in demo.ENVIRONMENT_FIELDS) for r in generated) == 8
    for r in generated:
        assert r["tnss"] == sum(r[field] for field in demo.NASAL_FIELDS)
    assert client.get(f"/symptoms/{generated[0]['id']}").json() == generated[0]
    before = database_rows(database_path)
    with pytest.raises(demo.DemoDataError, match="already exist"):
        demo.generate_demo_data(database_path, seed=43, end_date=END_DATE)
    assert database_rows(database_path) == before

    messages = []
    def before_deletion(message):
        # The callback runs before DELETE, while all generated rows are still present.
        assert len(database_rows(database_path)) == 142
        messages.append(message)
    assert demo.delete_demo_data(database_path, report=before_deletion) == (140, 2)
    assert messages == ["Synthetic records to remove: 140"]
    assert database_rows(database_path) == real_records
    assert all(r["is_synthetic"] is False for r in client.get("/symptoms").json())
    assert demo.delete_demo_data(database_path, report=messages.append) == (0, 2)
    demo.generate_demo_data(database_path, seed=42, end_date=END_DATE)
    regenerated = [r for r in client.get("/symptoms").json() if r["is_synthetic"]]
    assert [{k: v for k, v in r.items() if k != "id"} for r in regenerated] == [
        {k: v for k, v in r.items() if k != "id"} for r in generated
    ]
    assert database_rows(database_path, real_only=True) == real_records


def test_even_one_existing_synthetic_record_blocks_generation(client, database_path, valid_record):
    client.post("/symptoms", json=valid_record)
    before = database_rows(database_path)
    with pytest.raises(demo.DemoDataError, match="1 synthetic"):
        demo.generate_demo_data(database_path, end_date=END_DATE)
    assert database_rows(database_path) == before


def test_concurrent_generation_does_not_duplicate(client, database_path, real_records):
    def attempt():
        try:
            return demo.generate_demo_data(database_path, end_date=END_DATE).generated
        except demo.DemoDataError:
            return "stopped"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert results.count(140) == results.count("stopped") == 1
    assert len(database_rows(database_path)) == 142
    assert database_rows(database_path, real_only=True) == real_records


def test_failed_insert_rolls_back_entire_batch(client, database_path, real_records, monkeypatch):
    original = Session.flush
    def fail_after_insert(self, *args, **kwargs):
        inserting = bool(self.new)
        original(self, *args, **kwargs)
        if inserting:
            raise RuntimeError("Simulated failure after inserts")
    monkeypatch.setattr(Session, "flush", fail_after_insert)
    with pytest.raises(RuntimeError, match="after inserts"):
        demo.generate_demo_data(database_path, end_date=END_DATE)
    assert database_rows(database_path) == real_records


def test_failed_deletion_rolls_back(client, database_path, real_records, monkeypatch):
    demo.generate_demo_data(database_path, end_date=END_DATE)
    before = database_rows(database_path)
    original = Session.execute
    def fail_after_delete(self, statement, *args, **kwargs):
        result = original(self, statement, *args, **kwargs)
        if isinstance(statement, Delete):
            raise RuntimeError("Simulated failure after delete")
        return result
    monkeypatch.setattr(Session, "execute", fail_after_delete)
    with pytest.raises(RuntimeError, match="after delete"):
        demo.delete_demo_data(database_path, report=lambda _: None)
    assert database_rows(database_path) == before


@pytest.mark.parametrize("operation", ["generate", "delete"])
def test_wrong_database_path_does_not_create_a_file(tmp_path, operation):
    path = tmp_path / "not-created" / "typo.sqlite3"
    with pytest.raises(demo.DemoDataError, match="does not exist"):
        if operation == "generate":
            demo.generate_demo_data(path, end_date=END_DATE)
        else:
            demo.delete_demo_data(path)
    assert not path.parent.exists()


def test_incompatible_database_is_not_migrated_or_rebuilt(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
    before = path.read_bytes()
    for action in (demo.generate_demo_data, demo.delete_demo_data):
        with pytest.raises(demo.DemoDataError, match="schema is not current"):
            action(path)
    assert path.read_bytes() == before


def test_scripts_work_from_different_directory_and_report_counts(client, database_path, real_records, tmp_path):
    outside = tmp_path / "PowerShell working directory with spaces"
    outside.mkdir()
    def run(script, *extra):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script),
            "--database", str(database_path), *extra], cwd=outside, capture_output=True, text=True, timeout=20)
    created = run("generate_demo_data.py", "--seed", "42", "--end-date", END_DATE.isoformat())
    assert created.returncode == 0, created.stderr
    assert "Generated 140 synthetic symptom records" in created.stdout
    assert "Real records preserved: 2" in created.stdout
    assert "Records with missing environmental values: 8" in created.stdout
    duplicate = run("generate_demo_data.py", "--seed", "42", "--end-date", END_DATE.isoformat())
    assert duplicate.returncode == 1 and "already exist" in duplicate.stderr
    assert len(database_rows(database_path)) == 142
    removed = run("delete_demo_data.py")
    assert removed.returncode == 0, removed.stderr
    assert removed.stdout.index("Synthetic records to remove: 140") < removed.stdout.index("Deleted 140")
    assert "Real records preserved: 2" in removed.stdout
    assert database_rows(database_path) == real_records
    invalid = run("generate_demo_data.py", "--end-date", "invalid")
    assert invalid.returncode == 2 and database_rows(database_path) == real_records
