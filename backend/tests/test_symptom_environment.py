from contextlib import closing
from datetime import UTC, datetime
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.environment_service import EnvironmentService, get_environment_service

SNAPSHOT_FIELDS = (
    "temperature_c", "relative_humidity", "pm2_5", "pm10", "china_aqi_estimate",
    "environment_timestamp", "weather_timestamp", "air_quality_timestamp",
    "environment_latitude", "environment_longitude",
    "nitrogen_dioxide", "sulfur_dioxide", "carbon_monoxide", "ozone", "china_aqi_primary_pollutant",
)
FIXED_NOW = datetime.fromtimestamp(1789785000, UTC)


@pytest.fixture
def provider_payloads():
    return {
        "api.open-meteo.com": {
            "current_units": {"time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%"},
            "current": {"time": 1789784100, "temperature_2m": 23.8, "relative_humidity_2m": 61},
        },
        "air-quality-api.open-meteo.com": {
            "hourly_units": {"time": "unixtime", **{key: "µg/m³" for key in ("pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone")}},
            "hourly": {"time": [1789783200], "pm2_5": [21.5], "pm10": [34.2], "nitrogen_dioxide": [20], "sulphur_dioxide": [10], "carbon_monoxide": [600], "ozone": [64]},
        },
    }


def use_provider(client, payloads, handler=None):
    calls = []
    def transport(request):
        calls.append(request)
        return handler(request) if handler else httpx.Response(200, json=payloads[request.url.host])
    service = EnvironmentService(Settings(latitude=40.7, longitude=-74.0), httpx.MockTransport(transport), clock=lambda: FIXED_NOW)
    client.app.dependency_overrides[get_environment_service] = lambda: service
    return calls


def test_snapshot_is_persisted_and_returned_by_all_read_endpoints(client, valid_record, database_path, provider_payloads):
    calls = use_provider(client, provider_payloads)
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 201
    record = response.json()
    assert {field: record[field] for field in SNAPSHOT_FIELDS[:5]} == {
        "temperature_c": 23.8, "relative_humidity": 61, "pm2_5": 21.5, "pm10": 34.2, "china_aqi_estimate": 35,
    }
    assert datetime.fromisoformat(record["environment_timestamp"]) == FIXED_NOW
    assert record["timestamp"] == "2026-09-17T00:30:00Z"  # Never replace observation time.
    assert record["weather_timestamp"] == datetime.fromtimestamp(1789784100, UTC).isoformat().replace("+00:00", "Z")
    assert record["air_quality_timestamp"] == datetime.fromtimestamp(1789783200, UTC).isoformat().replace("+00:00", "Z")
    assert record["environment_latitude"] == 40.7 and record["environment_longitude"] == -74.0
    assert len(calls) == 2
    # Read actual SQLite values, then use a new app/connection to verify durability.
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT temperature_c, relative_humidity, pm2_5, pm10, china_aqi_estimate, environment_timestamp FROM symptom_records WHERE id = ?",
            (record["id"],),
        ).fetchone()
        assert row[:5] == (23.8, 61, 21.5, 34.2, 35)
        assert row[5] is not None
    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get(f"/symptoms/{record['id']}").json() == record
        assert restarted.get("/symptoms").json() == [record]
    assert len(calls) == 2  # History reads neither refresh nor overwrite snapshots.


@pytest.mark.parametrize("failure", ["timeout", "connect", "http", "malformed", "missing"])
def test_provider_failure_never_loses_symptoms(client, valid_record, provider_payloads, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("test timeout", request=request)
        if failure == "connect":
            raise httpx.ConnectError("test offline", request=request)
        if failure == "http":
            return httpx.Response(503)
        if failure == "malformed":
            return httpx.Response(200, text="{")
        return httpx.Response(200, json={})
    use_provider(client, provider_payloads, handler)
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 201
    saved = response.json()
    assert saved["tnss"] == 6 and saved["notes"] == valid_record["notes"]
    assert all(saved[field] is None for field in SNAPSHOT_FIELDS)
    assert client.get(f"/symptoms/{saved['id']}").json() == saved


def test_unexpected_enrichment_error_also_preserves_observation(client, valid_record):
    class BrokenService:
        async def get_current(self):
            raise ValueError("Unexpected provider shape")
    client.app.dependency_overrides[get_environment_service] = BrokenService
    saved = client.post("/symptoms", json=valid_record)
    assert saved.status_code == 201
    assert saved.json()["pm2_5"] is None
    assert len(client.get("/symptoms").json()) == 1


def test_partial_snapshot_preserves_missing_values_and_actual_zeros(client, valid_record, provider_payloads):
    provider_payloads["api.open-meteo.com"]["current"].update(temperature_2m=0)
    provider_payloads["api.open-meteo.com"]["current"].pop("relative_humidity_2m")
    provider_payloads["air-quality-api.open-meteo.com"]["hourly"].update(pm2_5=[None], pm10=[0])
    use_provider(client, provider_payloads)
    record = client.post("/symptoms", json=valid_record).json()
    assert record["temperature_c"] == record["pm10"] == 0
    assert record["china_aqi_estimate"] is None
    assert record["pm2_5"] is None and record["relative_humidity"] is None
    assert client.get("/symptoms").json() == [record]


def test_one_failed_provider_still_stores_the_other(client, valid_record, provider_payloads):
    def handler(request):
        if request.url.host == "api.open-meteo.com":
            raise httpx.ConnectTimeout("test", request=request)
        return httpx.Response(200, json=provider_payloads[request.url.host])
    use_provider(client, provider_payloads, handler)
    record = client.post("/symptoms", json=valid_record).json()
    assert record["temperature_c"] is record["relative_humidity"] is record["weather_timestamp"] is None
    assert record["pm2_5"] == 21.5 and record["air_quality_timestamp"] is not None
    assert record["environment_timestamp"] is not None


@pytest.mark.parametrize("eye_score", [0, 3])
def test_enrichment_keeps_tnss_definition_and_excludes_eyes(client, valid_record, provider_payloads, eye_score):
    use_provider(client, provider_payloads)
    valid_record.update(nasal_congestion=2, sneezing=2, runny_nose=1, nasal_itching=1, eye_symptoms=eye_score)
    saved = client.post("/symptoms", json=valid_record).json()
    assert saved["tnss"] == 6 and saved["pm2_5"] == 21.5


@pytest.mark.parametrize("field", SNAPSHOT_FIELDS)
def test_snapshot_is_server_managed_and_validation_precedes_retrieval(client, valid_record, provider_payloads, field):
    calls = use_provider(client, provider_payloads)
    response = client.post("/symptoms", json=valid_record | {field: None})
    assert response.status_code == 422
    assert calls == []
    assert client.get("/symptoms").json() == []


def test_invalid_symptom_does_not_request_environment(client, valid_record, provider_payloads):
    calls = use_provider(client, provider_payloads)
    assert client.post("/symptoms", json=valid_record | {"sneezing": 4}).status_code == 422
    assert calls == []
