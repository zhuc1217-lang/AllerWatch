"""Independent HJ 633—2026 examples and full-pipeline safety regressions."""
import asyncio
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import sqlite3

from fastapi.testclient import TestClient
import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.models import SymptomRecord
from app.services.china_aqi import POLLUTANTS, calculate_china_aqi, pollutant_iaqi
from app.services.environment_service import EnvironmentService, get_environment_service
from scripts.demo_data import build_demo_records


# Independent standard table, not imported from the implementation under test.
TABLE = {
    "pm2_5": [0, 35, 60, 115, 150, 250, 350, 500],
    "pm10": [0, 50, 120, 250, 350, 420, 500, 600],
    "nitrogen_dioxide": [0, 100, 200, 700, 1200, 2340, 3090, 3840],
    "sulfur_dioxide": [0, 150, 500, 650, 800],
    "carbon_monoxide": [0, 5000, 10000, 35000, 60000, 90000, 120000, 150000],
    "ozone": [0, 160, 200, 300, 400, 800, 1000, 1200],
}
INDICES = [0, 50, 100, 150, 200, 300, 400, 500]
ZERO = dict.fromkeys(TABLE, 0)


@pytest.mark.parametrize("pollutant,concentration,expected", [
    (name, bp, INDICES[i]) for name, values in TABLE.items() for i, bp in enumerate(values)
])
def test_exact_breakpoints(pollutant, concentration, expected):
    assert pollutant_iaqi(pollutant, concentration) == expected


@pytest.mark.parametrize("pollutant,concentration,expected", [
    ("pm2_5", 17.5, 25), ("pm2_5", 35.01, 51), ("pm2_5", 0.7, 1),
    ("pm10", 85, 75), ("pm10", 0.01, 1),
    ("nitrogen_dioxide", 450, 125), ("nitrogen_dioxide", 201, 101),
    ("ozone", 180, 75), ("ozone", 160.01, 51),
    ("carbon_monoxide", 7500, 75), ("carbon_monoxide", 5001, 51),
    ("sulfur_dioxide", 325, 75), ("sulfur_dioxide", 800.01, 200),
    ("sulfur_dioxide", 1000000, 200),
])
def test_interpolation_upward_rounding_co_conversion_and_so2_special_case(pollutant, concentration, expected):
    assert pollutant_iaqi(pollutant, concentration) == expected


@pytest.mark.parametrize("pollutant", TABLE)
def test_upper_representation_is_bounded(pollutant):
    expected = 200 if pollutant == "sulfur_dioxide" else 500
    assert pollutant_iaqi(pollutant, TABLE[pollutant][-1] + 1000) == expected


@pytest.mark.parametrize("pollutant", TABLE)
@pytest.mark.parametrize("invalid", [None, -1, True, "12", float("nan"), float("inf")])
def test_missing_or_invalid_required_pollutant_never_becomes_zero(pollutant, invalid):
    values = ZERO | {pollutant: invalid}
    result = calculate_china_aqi(**values)
    assert result.aqi is result.primary_pollutant is None
    assert result.iaqi[pollutant] is None
    assert values[pollutant] is invalid  # No mutation of raw input.


def test_maximum_primary_ties_and_true_zero():
    assert calculate_china_aqi(**ZERO).aqi == 0
    assert calculate_china_aqi(**(ZERO | {"pm2_5": 35})).primary_pollutant is None
    result = calculate_china_aqi(**(ZERO | {"pm2_5": 60, "pm10": 120, "carbon_monoxide": 7500}))
    assert result.aqi == 100
    assert result.primary_pollutant == "PM2.5, PM10"
    result = calculate_china_aqi(**(ZERO | {"ozone": 300, "pm2_5": 60}))
    assert result.aqi == 150 and result.primary_pollutant == "O3"


NOW = datetime(2026, 9, 18, 10, 30, tzinfo=UTC)
PROVIDER_KEYS = ("pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone")


def air_payload():
    return {"hourly_units": {"time": "unixtime", **dict.fromkeys(PROVIDER_KEYS, "µg/m³")},
            "hourly": {"time": [(NOW - timedelta(minutes=90)).timestamp(), (NOW - timedelta(minutes=30)).timestamp(),
                                (NOW + timedelta(minutes=30)).timestamp()],
                       **{key: [10, 0, 99999] for key in PROVIDER_KEYS}}}


def hourly_service(payload):
    return EnvironmentService(Settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=payload
        if request.url.host == "air-quality-api.open-meteo.com" else {
            "current_units": {"time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%"},
            "current": {"time": NOW.timestamp(), "temperature_2m": 20, "relative_humidity_2m": 50}})), clock=lambda: NOW)


def test_hourly_slot_uses_all_same_hour_and_excludes_future_values():
    result = asyncio.run(hourly_service(air_payload()).get_current())
    assert result.china_aqi_estimate == 0
    assert all(getattr(result, field) == 0 for field in POLLUTANTS)
    assert result.air_quality_timestamp == NOW - timedelta(minutes=30)
    assert result.timestamp == NOW


@pytest.mark.parametrize("bad", ["missing", "short_array", "wrong_unit", "negative", "string"])
def test_partial_hour_never_borrows_gas_from_another_hour(bad):
    payload = air_payload()
    if bad == "missing": payload["hourly"].pop("nitrogen_dioxide")
    elif bad == "short_array": payload["hourly"]["nitrogen_dioxide"] = [10]
    elif bad == "wrong_unit": payload["hourly_units"]["nitrogen_dioxide"] = "mg/m³"
    else: payload["hourly"]["nitrogen_dioxide"][1] = -1 if bad == "negative" else "20"
    result = asyncio.run(hourly_service(payload).get_current())
    assert result.nitrogen_dioxide is result.china_aqi_estimate is result.china_aqi_primary_pollutant is None
    assert result.pm2_5 == 0 and result.carbon_monoxide == 0
    assert result.status == "partial"


@pytest.mark.parametrize("times", [[], [None], [True], [float("inf")], [1, 1], "invalid"])
def test_malformed_hourly_time_axis_is_not_used(times):
    payload = air_payload(); payload["hourly"]["time"] = times
    result = asyncio.run(hourly_service(payload).get_current())
    assert result.china_aqi_estimate is result.air_quality_timestamp is None
    assert result.temperature_c == 20


def test_new_snapshot_round_trip_keeps_raw_co_and_deprecates_us_index(client, valid_record):
    payload = air_payload(); payload["hourly"]["carbon_monoxide"][1] = 7500
    client.app.dependency_overrides[get_environment_service] = lambda: hourly_service(payload)
    saved = client.post("/symptoms", json=valid_record).json()
    assert saved["carbon_monoxide"] == 7500  # Raw API/DB concentration stays µg/m³.
    assert saved["china_aqi_estimate"] == 75
    assert saved["china_aqi_primary_pollutant"] == "CO"
    assert saved["us_aqi"] is None
    assert client.get(f"/symptoms/{saved['id']}").json() == saved
    # This deliberately backdated symptom keeps its snapshot but fails C1.
    assert saved["environment_time_eligible"]["china_aqi_estimate"] is False
    associations = client.get('/analysis/associations?dataset=synthetic_only').json()
    row = next(r for r in associations['associations'] if r['variable'] == 'china_aqi_estimate')
    assert (row['n'], row['temporally_excluded_pairs'], row['missing_pairs']) == (0, 1, 0)
    lag = client.get('/analysis/lagged-associations?dataset=synthetic_only').json()
    assert all(r['n'] == 0 for r in lag['results'] if r['variable'] == 'china_aqi_estimate')


def test_additive_migration_retains_legacy_real_snapshot_without_inventing_aqi(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with TestClient(create_app(path)) as client:
        with client.app.state.session_factory() as session:
            session.add(SymptomRecord(timestamp=NOW, is_synthetic=False, nasal_congestion=1,
                sneezing=1, runny_nose=1, nasal_itching=1, eye_symptoms=2, overall_severity=4,
                medication_taken=False, pm2_5=0, pm10=20, us_aqi=42, notes="Preserved fixture",
                air_quality_timestamp=NOW, environment_timestamp=NOW))
            session.commit()
    new_columns = [*POLLUTANTS[2:], "china_aqi_estimate", "china_aqi_primary_pollutant"]
    with closing(sqlite3.connect(path)) as db, db:
        for column in new_columns: db.execute(f'ALTER TABLE symptom_records DROP COLUMN {column}')
        original = db.execute('SELECT * FROM symptom_records').fetchall()
        columns = [row[1] for row in db.execute('PRAGMA table_info(symptom_records)')]
    with TestClient(create_app(path)) as client:
        result = client.get('/symptoms').json()[0]
        assert result['us_aqi'] == 42 and result['pm2_5'] == 0
        assert all(result[column] is None for column in new_columns)
        descriptive = client.get('/analysis/descriptive').json()['variables']
        assert 'us_aqi' not in descriptive
        assert descriptive['china_aqi_estimate']['missing'] == 1
        associations = client.get('/analysis/associations').json()['associations']
        assert next(r for r in associations if r['variable'] == 'china_aqi_estimate')['missing_pairs'] == 1
    with closing(sqlite3.connect(path)) as db:
        assert db.execute(f'SELECT {",".join(columns)} FROM symptom_records').fetchall() == original
    assert len(list((path.parent / 'backups').glob('*.sqlite3'))) == 1


def test_generated_aqi_uses_all_six_pollutants_and_preserves_original_symptom_stream():
    records = build_demo_records(seed=42, end_date=date(2026, 9, 18))
    assert len(records) == 140
    for record in records:
        estimate = calculate_china_aqi(**{field:getattr(record, field) for field in POLLUTANTS})
        assert record.china_aqi_estimate == estimate.aqi
        assert record.china_aqi_primary_pollutant == estimate.primary_pollutant
        assert record.is_synthetic and record.us_aqi is None
    # Frozen pre-change symptom stream; no outcome tuning when adding gases.
    fields = ['timestamp', 'nasal_congestion', 'sneezing', 'runny_nose', 'nasal_itching',
              'eye_symptoms', 'overall_severity', 'medication_taken']
    serialized = json.dumps([{f:str(getattr(r, f)) for f in fields} for r in records], sort_keys=True)
    assert hashlib.sha256(serialized.encode()).hexdigest() == '6f7dd51cf2fe3ff8a8cd4b8a80cf29106e9dd94822cf31d9c83c6473ed545c24'
