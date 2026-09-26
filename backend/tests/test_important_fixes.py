"""I1/I3/I4 deterministic time, provenance, migration and model safeguards."""
import asyncio
from contextlib import closing
from datetime import UTC, date, datetime, timedelta, timezone
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analysis.risk_model import DAILY_FEATURES, build_model_rows, report_available
from app.config import Settings
from app.daily_health import DailyHealthRecord
from app.main import create_app
from app.models import SymptomRecord
from app.services.environment_service import EnvironmentService, EnvironmentUnavailable, get_environment_service
from app.time_policy import get_clock

NOW = datetime(2026, 9, 22, 16, tzinfo=UTC)  # September 23 midnight in UTC+08.
DAILY = dict(sleep_duration_hours=7.5, sleep_quality=4, stress_level=3, exercise_minutes=30)


def clock_at(client, instant):
    client.app.dependency_overrides[get_clock] = lambda: lambda: instant


def symptom(timestamp, **changes):
    values = dict(timestamp=timestamp, nasal_congestion=2, sneezing=2, runny_nose=1,
                  nasal_itching=1, eye_symptoms=3, overall_severity=6,
                  medication_taken=False, is_synthetic=False, environment_timestamp=timestamp + timedelta(seconds=3))
    values.update(changes)
    return SymptomRecord(**values)


@pytest.mark.parametrize("seconds,accepted", [(-1, True), (0, True), (59, True), (60, True), (60.000001, False), (86400, False)])
@pytest.mark.parametrize("offset", [-7, 0, 8])
def test_real_symptom_clock_skew_boundaries_and_offsets(client, valid_record, seconds, accepted, offset):
    clock_at(client, NOW)
    timestamp = (NOW + timedelta(seconds=seconds)).astimezone(timezone(timedelta(hours=offset)))
    response = client.post("/symptoms", json={**valid_record, "timestamp": timestamp.isoformat(), "is_synthetic": False})
    assert response.status_code == (201 if accepted else 422)
    assert len(client.get("/symptoms").json()) == int(accepted)
    if accepted:
        assert datetime.fromisoformat(response.json()["received_at"]) == NOW
        assert datetime.fromisoformat(response.json()["timestamp"]) == timestamp
    else:
        assert response.json()["detail"][0]["loc"] == ["body", "timestamp"]


@pytest.mark.parametrize("now,day,accepted", [
    (NOW - timedelta(microseconds=1), "2026-09-22", True),
    (NOW - timedelta(microseconds=1), "2026-09-23", False),
    (NOW, "2026-09-23", True),
    (NOW, "2026-09-24", False),
    (datetime(2026, 9, 22, 23, 59, 59, tzinfo=UTC), "2026-09-23", True),
    (datetime(2026, 9, 23, tzinfo=UTC), "2026-09-24", False),
    (datetime(2026, 9, 23, 8, tzinfo=timezone(timedelta(hours=8))), "2026-09-23", True),
])
def test_daily_dates_follow_study_midnight_not_utc_or_device_day(client, now, day, accepted):
    clock_at(client, now)
    response = client.post("/daily-health", json={**DAILY, "date": day})
    assert response.status_code == (201 if accepted else 422)
    assert client.get("/daily-health").json()["today"] == now.astimezone(timezone(timedelta(hours=8))).date().isoformat()


def test_controlled_future_synthetic_records_are_explicit_and_separate(client, valid_record):
    clock_at(client, NOW)
    assert client.post("/symptoms", json={**valid_record, "timestamp": "2027-01-01T00:00:00Z"}).status_code == 201
    assert client.post("/daily-health", json={**DAILY, "date": "2027-01-01", "is_synthetic": True}).status_code == 201
    assert client.put("/daily-health/2027-01-01?is_synthetic=true", json=DAILY).status_code == 200
    assert client.get("/daily-health").json()["records"] == []
    assert client.get("/analysis/associations?dataset=real_only").json()["record_count"] == 0


def test_default_symptom_time_and_receipt_use_server_clock_even_on_environment_failure(client, valid_record):
    clock_at(client, NOW)
    payload = {key: value for key, value in valid_record.items() if key != "timestamp"}
    response = client.post("/symptoms", json={**payload, "is_synthetic": False})
    assert response.status_code == 201
    data = response.json()
    assert datetime.fromisoformat(data["timestamp"]) == datetime.fromisoformat(data["received_at"]) == NOW
    assert data["environment_timestamp"] is None


def test_future_legacy_real_records_remain_readable_but_daily_update_is_rejected(client):
    clock_at(client, NOW)
    with client.app.state.session_factory() as session:
        session.add(symptom(NOW + timedelta(days=30)))
        session.add(DailyHealthRecord(date=date(2027, 1, 1), is_synthetic=False, **DAILY))
        session.commit()
    assert len(client.get("/symptoms").json()) == 1
    before = client.get("/daily-health/2027-01-01").json()
    assert before["updated_at"] is None
    assert client.put("/daily-health/2027-01-01", json={**DAILY, "stress_level": 5}).status_code == 422
    assert client.get("/daily-health/2027-01-01").json() == before


def test_server_daily_creation_and_edit_times_change_only_on_accepted_save(client):
    clock_at(client, NOW)
    first = client.post("/daily-health", json={**DAILY, "date": "2026-09-22"}).json()
    assert datetime.fromisoformat(first["created_at"]) == datetime.fromisoformat(first["updated_at"]) == NOW
    clock_at(client, NOW + timedelta(hours=1))
    saved = client.put("/daily-health/2026-09-22", json={**DAILY, "stress_level": 4}).json()
    assert saved["created_at"] == first["created_at"]
    assert datetime.fromisoformat(saved["updated_at"]) == NOW + timedelta(hours=1)
    assert client.put("/daily-health/2026-09-22", json={**DAILY, "stress_level": 9}).status_code == 422
    assert client.get("/daily-health/2026-09-22").json() == saved


@pytest.mark.parametrize("endpoint,field", [("symptoms", "received_at"), ("daily-health", "updated_at"), ("daily-health", "created_at")])
def test_provenance_cannot_be_supplied_by_caller(client, valid_record, endpoint, field):
    payload = valid_record if endpoint == "symptoms" else {**DAILY, "date": "2026-09-22"}
    assert client.post('/' + endpoint, json={**payload, field: NOW.isoformat()}).status_code == 422


def test_new_metadata_never_enables_unproven_lifestyle_or_earlier_prediction():
    earlier, later = symptom(NOW), symptom(NOW + timedelta(hours=6))
    earlier.received_at = NOW + timedelta(hours=7)
    assert report_available(earlier) == NOW + timedelta(hours=7)
    assert build_model_rows([earlier, later], [], "real_only").excluded_pairs == {"predictors_not_before_target": 1}
    earlier.received_at = NOW
    diary = DailyHealthRecord(date=date(2026, 9, 22), created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(hours=1), is_synthetic=False, **DAILY)
    rows = build_model_rows([earlier, later], [diary], "real_only").rows
    assert len(rows) == 1
    assert all(rows[0].features[name] is None for name in DAILY_FEATURES)
    assert rows[0].feature_timestamp < rows[0].target_timestamp
    earlier.environment_timestamp = None
    assert report_available(earlier) is None  # Preserve the conservative first-model protocol.


def providers(weather_time=NOW, air_time=NOW):
    return {
        "api.open-meteo.com": {"current_units": {"time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%"},
            "current": {"time": weather_time.timestamp(), "temperature_2m": 0, "relative_humidity_2m": 60}},
        "air-quality-api.open-meteo.com": {"hourly_units": {"time": "unixtime", **{key: "µg/m³" for key in ("pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone")}},
            "hourly": {"time": [air_time.timestamp()], "pm2_5": [0], "pm10": [20], "nitrogen_dioxide": [20], "sulphur_dioxide": [10], "carbon_monoxide": [600], "ozone": [64]}},
    }


def service_for(payloads, clock=lambda: NOW):
    return EnvironmentService(Settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=payloads[request.url.host])), clock=clock)


@pytest.mark.parametrize("age,accepted", [(0, True), (3600, True), (10800, True), (10800.001, False), (-0.001, False), (-3600, False), (1e9, False)])
@pytest.mark.parametrize("provider", ["weather", "air"])
def test_freshness_closed_window_and_independent_sources(age, accepted, provider):
    source = NOW - timedelta(seconds=age)
    values = providers(weather_time=source) if provider == "weather" else providers(air_time=source)
    result = asyncio.run(service_for(values).get_current())
    assert result.timestamp == NOW
    assert result.status == ("available" if accepted else "partial")
    if provider == "weather":
        assert result.temperature_c == (0 if accepted else None)
        assert result.weather_timestamp == (source if accepted else None)
        assert result.pm2_5 == 0 and result.air_quality_timestamp == NOW
    else:
        assert result.pm2_5 == (0 if accepted else None)
        assert result.air_quality_timestamp == (source if accepted else None)
        assert result.temperature_c == 0 and result.weather_timestamp == NOW


def test_clock_is_captured_once_for_both_providers_and_retrieval_metadata():
    calls = []
    def clock():
        calls.append(1)
        return NOW.astimezone(timezone(timedelta(hours=-7)))
    result = asyncio.run(service_for(providers(NOW - timedelta(hours=3), NOW), clock).get_current())
    assert len(calls) == 1
    assert result.status == "available" and result.timestamp == NOW


def test_both_stale_is_controlled_unavailable_and_still_saves_symptoms(client, valid_record):
    clock_at(client, NOW)
    service = service_for(providers(NOW - timedelta(days=1), NOW + timedelta(hours=1)))
    with pytest.raises(EnvironmentUnavailable):
        asyncio.run(service.get_current())
    client.app.dependency_overrides[get_environment_service] = lambda: service
    assert client.get("/environment/current").status_code == 503
    saved = client.post("/symptoms", json={**valid_record, "timestamp": NOW.isoformat(), "is_synthetic": False})
    assert saved.status_code == 201
    assert all(saved.json()[field] is None for field in ["pm2_5", "pm10", "china_aqi_estimate", "temperature_c", "relative_humidity", "environment_timestamp"])


def test_legacy_metadata_migration_is_nullable_preserving_and_idempotent(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with TestClient(create_app(path)) as client:
        with client.app.state.session_factory() as session:
            session.add(symptom(NOW))
            session.add(DailyHealthRecord(date=date(2026, 9, 22), is_synthetic=False, **DAILY))
            session.commit()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('ALTER TABLE symptom_records DROP COLUMN received_at')
        db.execute('ALTER TABLE daily_health_records DROP COLUMN updated_at')
        symptom_before = db.execute('SELECT * FROM symptom_records').fetchall()
        daily_before = db.execute('SELECT * FROM daily_health_records').fetchall()
    for _ in range(2):
        with TestClient(create_app(path)) as client:
            assert client.get('/symptoms').json()[0]['received_at'] is None
            assert client.get('/daily-health').json()['records'][0]['updated_at'] is None
        with closing(sqlite3.connect(path)) as db:
            assert [row[:-1] for row in db.execute('SELECT * FROM symptom_records')] == symptom_before
            assert [row[:-1] for row in db.execute('SELECT * FROM daily_health_records')] == daily_before
    backups = list((tmp_path / 'backups').glob('*.sqlite3'))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as db:
        assert db.execute('SELECT * FROM symptom_records').fetchall() == symptom_before
        assert db.execute('SELECT * FROM daily_health_records').fetchall() == daily_before
