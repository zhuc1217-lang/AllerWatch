from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.analysis.daily_health_associations import daily_health_associations, join_daily_health
from app.analysis.dataset import prepare_dataset
from app.daily_health import DailyHealthRecord, study_date
from app.models import SymptomRecord
from app.database import create_database_engine, initialize_database
from scripts.daily_demo_data import build_daily_demo, delete_daily_demo, generate_daily_demo, DemoDataError

PAYLOAD = dict(date="2026-09-17", sleep_duration_hours=7.5, sleep_quality=4, stress_level=3, exercise_minutes=30)


def daily(day=date(2026, 9, 17), synthetic=False, **values):
    return DailyHealthRecord(date=day, is_synthetic=synthetic, **{
        "sleep_duration_hours": 7.5, "sleep_quality": 4, "stress_level": 3, "exercise_minutes": 30, **values})


def symptom(day=17, synthetic=False, score=1, **values):
    return SymptomRecord(**{"timestamp": datetime(2026, 9, day, 8, tzinfo=UTC),
        "nasal_congestion": min(score, 3), "sneezing": max(score - 3, 0), "runny_nose": 0, "nasal_itching": 0,
        "eye_symptoms": 3, "overall_severity": 5, "medication_taken": False, "is_synthetic": synthetic, **values})


def test_create_read_update_and_duplicate_prevention(client):
    result = client.post("/daily-health", json=PAYLOAD)
    assert result.status_code == 201
    first = result.json()
    assert first["date"] == PAYLOAD["date"] and first["is_synthetic"] is False
    assert first["notes"] is None and first["created_at"].endswith("Z")
    assert client.post("/daily-health", json=PAYLOAD).status_code == 409
    values = {k: v for k, v in PAYLOAD.items() if k != "date"} | {"sleep_duration_hours": 6.5, "exercise_minutes": 0, "notes": "Updated"}
    updated = client.put("/daily-health/2026-09-17", json=values)
    assert updated.status_code == 200
    assert updated.json()["id"] == first["id"] and updated.json()["created_at"] == first["created_at"]
    assert updated.json()["sleep_duration_hours"] == 6.5 and updated.json()["exercise_minutes"] == 0
    assert client.get("/daily-health/2026-09-17").json() == updated.json()
    assert len(client.get("/daily-health").json()["records"]) == 1
    assert client.put("/daily-health/2026-09-18", json=values).status_code == 404
    assert client.get("/daily-health/2026-02-30").status_code == 422
    assert client.get("/daily-health/2026-09-18").status_code == 404


@pytest.mark.parametrize("field,value", [
    ("sleep_duration_hours", -0.1), ("sleep_duration_hours", 24.1), ("sleep_duration_hours", True), ("sleep_duration_hours", "NaN"),
    ("sleep_quality", 0), ("sleep_quality", 6), ("sleep_quality", 2.5), ("sleep_quality", True),
    ("stress_level", 0), ("stress_level", 6), ("stress_level", 2.5), ("stress_level", "3"),
    ("exercise_minutes", -1), ("exercise_minutes", 1441), ("exercise_minutes", 5.5), ("exercise_minutes", False),
    ("date", "2026-09-17T00:00:00Z"), ("date", 0), ("date", "2026-02-30"), ("date", "09/17/2026"),
    ("is_synthetic", "true"), ("created_at", "2020-01-01T00:00:00Z"),
])
def test_invalid_values_return_422_without_writes(client, field, value):
    assert client.post("/daily-health", json=PAYLOAD | {field: value}).status_code == 422
    assert client.get("/daily-health?dataset=all").json()["records"] == []


@pytest.mark.parametrize("sleep,quality,stress,exercise", [(0, 1, 1, 0), (24, 5, 5, 1440)])
def test_bounds_are_valid(client, sleep, quality, stress, exercise):
    assert client.post("/daily-health", json=PAYLOAD | dict(sleep_duration_hours=sleep, sleep_quality=quality,
        stress_level=stress, exercise_minutes=exercise)).status_code == 201


def test_update_cannot_relabel_date_or_provenance(client):
    client.post("/daily-health", json=PAYLOAD)
    values = {k: v for k, v in PAYLOAD.items() if k != "date"}
    for field, value in [("date", "2026-09-18"), ("is_synthetic", True), ("sleep_quality", 0)]:
        assert client.put("/daily-health/2026-09-17", json=values | {field: value}).status_code == 422
    assert client.get("/daily-health/2026-09-17").json()["sleep_quality"] == 4


def test_real_and_synthetic_can_coexist_but_not_overwrite_each_other(client):
    client.post("/daily-health", json=PAYLOAD | {"is_synthetic": True, "sleep_duration_hours": 4})
    assert client.get("/daily-health/2026-09-17").status_code == 404
    assert client.post("/daily-health", json=PAYLOAD).status_code == 201
    assert client.post("/daily-health", json=PAYLOAD | {"is_synthetic": True}).status_code == 409
    for mode, count in [("real_only", 1), ("synthetic_only", 1), ("all", 2)]:
        body = client.get(f"/daily-health?dataset={mode}").json()
        assert len(body["records"]) == count and body["calendar_timezone"] == "UTC+08:00"
    values = {k: v for k, v in PAYLOAD.items() if k != "date"} | {"sleep_duration_hours": 8}
    client.put("/daily-health/2026-09-17", json=values)
    assert client.get("/daily-health/2026-09-17?is_synthetic=true").json()["sleep_duration_hours"] == 4


def test_database_constraint_prevents_duplicate_dates(client):
    with client.app.state.session_factory() as s:
        s.add_all([daily(), daily()])
        with pytest.raises(IntegrityError): s.commit()


def test_list_newest_first(client):
    for day in ["2026-09-17", "2026-09-19", "2026-09-18"]:
        client.post("/daily-health", json=PAYLOAD | {"date": day})
    assert [r["date"] for r in client.get("/daily-health").json()["records"]] == ["2026-09-19", "2026-09-18", "2026-09-17"]


def test_calendar_midnight_and_offset_equivalence():
    assert study_date(datetime(2026, 9, 17, 15, 59, tzinfo=UTC)) == date(2026, 9, 17)
    instant = datetime(2026, 9, 17, 16, tzinfo=UTC)
    assert study_date(instant) == date(2026, 9, 18)
    assert study_date(instant.astimezone(timezone(timedelta(hours=-5)))) == date(2026, 9, 18)
    with pytest.raises(ValueError, match="timezone-aware"): study_date(instant.replace(tzinfo=None))


def test_left_join_preserves_unmatched_and_multiple_symptoms_and_zeros():
    symptoms = [symptom(), symptom(timestamp=datetime(2026, 9, 17, 15, tzinfo=UTC)),
                symptom(timestamp=datetime(2026, 9, 17, 16, tzinfo=UTC))]
    diaries = [daily(exercise_minutes=0), daily(date(2026, 9, 19))]
    dataset = prepare_dataset(symptoms, "real_only")
    _, rows, matches = join_daily_health(dataset, diaries)
    assert len(rows) == 3 and [r["exercise_minutes"] for r in rows] == [0, 0, None]
    assert matches[2] is None
    response = daily_health_associations(dataset, diaries)
    assert response.matched_symptom_count == 2 and response.missing_daily_symptom_count == 1
    assert response.matched_daily_records == 1 and response.daily_records_without_symptoms == 1
    assert all(r.n == 2 and r.missing_pairs == 1 and r.distinct_daily_records == 1 for r in response.associations)


@pytest.mark.parametrize("mode,real,synthetic", [("real_only", 12, 0), ("synthetic_only", 0, 12), ("all", 12, 12)])
def test_spearman_and_dataset_modes(mode, real, synthetic):
    symptoms, diaries = [], []
    for flag in (False, True):
        for i in range(12):
            symptoms.append(symptom(day=i + 1, score=i % 5, synthetic=flag))
            diaries.append(daily(date(2026, 9, i + 1), synthetic=flag, sleep_duration_hours=9 - i % 5, stress_level=1 + i % 5))
    response = daily_health_associations(prepare_dataset(symptoms, mode), diaries)
    assert (response.real_count, response.synthetic_count) == (real, synthetic)
    sleep, _, stress, _ = response.associations
    assert sleep.spearman_rho == pytest.approx(-1)
    assert stress.spearman_rho == pytest.approx(1)
    assert (sleep.n, sleep.real_pairs, sleep.synthetic_pairs) == (real + synthetic, real, synthetic)
    assert response.associations[-1].status == "insufficient_variation"


@pytest.mark.parametrize("mode", ["real_only", "synthetic_only", "all"])
def test_cross_type_never_joins(mode):
    symptoms = [symptom(synthetic=False), symptom(day=18, synthetic=True)]
    diaries = [daily(synthetic=True), daily(date(2026, 9, 18), synthetic=False)]
    response = daily_health_associations(prepare_dataset(symptoms, mode), diaries)
    assert response.matched_symptom_count == 0
    assert all(r.n == 0 and r.spearman_rho is None and r.status == "insufficient_data" for r in response.associations)


def test_empty_analysis_and_default_endpoint(client):
    body = client.get("/analysis/daily-health-associations").json()
    assert body["dataset_mode"] == "real_only" and body["record_count"] == 0
    assert len(body["associations"]) == 4
    assert all(r["n"] == 0 and r["p_value"] is None for r in body["associations"])
    assert client.get("/analysis/daily-health-associations?dataset=invalid").status_code == 422


def test_daily_generation_reproducible_plausible_and_does_not_use_real_data():
    symptoms = [symptom(day=i, synthetic=True, score=i % 5) for i in range(1, 30)]
    generated = build_daily_demo(symptoms)
    again = build_daily_demo([symptom(day=30, synthetic=False), *reversed(symptoms)])
    columns = ["date", "sleep_duration_hours", "sleep_quality", "stress_level", "exercise_minutes", "notes", "is_synthetic"]
    assert [[getattr(r, key) for key in columns] for r in generated] == [[getattr(r, key) for key in columns] for r in again]
    assert len(generated) == 29
    assert all(r.is_synthetic and 0 <= r.sleep_duration_hours <= 24 and 1 <= r.sleep_quality <= 5 and
               1 <= r.stress_level <= 5 and 0 <= r.exercise_minutes <= 120 and r.notes is None for r in generated)
    assert len({r.sleep_duration_hours for r in generated}) > 10
    with pytest.raises(DemoDataError): build_daily_demo([symptom()])


def test_daily_generate_delete_preserves_all_symptoms_and_real_diaries(client, database_path):
    with client.app.state.session_factory() as s:
        s.add_all([symptom(synthetic=True), symptom(day=20, synthetic=True), symptom(synthetic=False), daily()])
        s.commit()
    with sqlite3.connect(database_path) as c:
        before_symptoms = c.execute('SELECT * FROM symptom_records ORDER BY id').fetchall()
        real_before = c.execute('SELECT * FROM daily_health_records WHERE is_synthetic=0').fetchall()
    generated = generate_daily_demo(database_path)
    assert generated.generated == 4 and generated.real_preserved == 1
    with pytest.raises(DemoDataError, match="already exist"): generate_daily_demo(database_path)
    messages = []
    assert delete_daily_demo(database_path, report=messages.append) == (4, 1)
    assert "4" in messages[0]
    with sqlite3.connect(database_path) as c:
        assert c.execute('SELECT * FROM symptom_records ORDER BY id').fetchall() == before_symptoms
        assert c.execute('SELECT * FROM daily_health_records').fetchall() == real_before
    assert generate_daily_demo(database_path).generated == 4
    root = Path(__file__).resolve().parents[2]
    run = subprocess.run([sys.executable, str(root / 'scripts/delete_demo_data.py'), '--database', str(database_path), '--daily-health'], capture_output=True, text=True)
    assert run.returncode == 0 and 'Deleted 4 synthetic daily-health records' in run.stdout
    with sqlite3.connect(database_path) as c:
        assert c.execute('SELECT * FROM symptom_records ORDER BY id').fetchall() == before_symptoms
        assert c.execute('SELECT * FROM daily_health_records').fetchall() == real_before


def test_additive_table_creation_preserves_existing_symptoms(client, database_path):
    with client.app.state.session_factory() as s:
        s.add(symptom()); s.commit()
    with sqlite3.connect(database_path) as c:
        before = c.execute('SELECT * FROM symptom_records').fetchall()
        c.execute('DROP TABLE daily_health_records')  # Isolated test fixture only.
    engine = create_database_engine(database_path)
    try:
        initialize_database(engine); initialize_database(engine)
    finally: engine.dispose()
    with sqlite3.connect(database_path) as c:
        assert c.execute('SELECT * FROM symptom_records').fetchall() == before
        assert c.execute('SELECT COUNT(*) FROM daily_health_records').fetchone()[0] == 0


def test_existing_symptom_delete_default_leaves_all_daily_records_untouched(client, database_path):
    from scripts.demo_data import delete_demo_data
    with client.app.state.session_factory() as s:
        s.add_all([symptom(), symptom(synthetic=True), daily(), daily(synthetic=True)])
        s.commit()
    with sqlite3.connect(database_path) as c:
        before = c.execute('SELECT * FROM daily_health_records ORDER BY id').fetchall()
    assert delete_demo_data(database_path, report=lambda message: None) == (1, 1)
    with sqlite3.connect(database_path) as c:
        assert c.execute('SELECT * FROM daily_health_records ORDER BY id').fetchall() == before
        assert c.execute('SELECT is_synthetic FROM symptom_records').fetchall() == [(0,)]
