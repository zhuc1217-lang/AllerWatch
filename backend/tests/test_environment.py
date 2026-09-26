import asyncio
from copy import deepcopy
from datetime import UTC, datetime
import json

import httpx
import pytest
from pydantic import ValidationError

from app.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, Settings, get_settings
from app.services import environment_service as environment

FIXED_NOW = datetime.fromtimestamp(1789785000, UTC)


@pytest.fixture
def provider_payloads():
    return {
        "api.open-meteo.com": {
            "current_units": {"time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%"},
            "current": {"time": 1789784100, "temperature_2m": 23.4, "relative_humidity_2m": 58},
        },
        "air-quality-api.open-meteo.com": {
            "hourly_units": {"time": "unixtime", **{key: "µg/m³" for key in ("pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "carbon_monoxide", "ozone")}},
            "hourly": {"time": [1789783200], "pm2_5": [17.2], "pm10": [25.8], "nitrogen_dioxide": [20], "sulphur_dioxide": [10], "carbon_monoxide": [600], "ozone": [64]},
        },
    }


def mock_service(payloads, handler=None, settings=None):
    def default_handler(request):
        return httpx.Response(200, text=json.dumps(payloads[request.url.host]), headers={"Content-Type": "application/json"})
    return environment.EnvironmentService(settings or Settings(), httpx.MockTransport(handler or default_handler), clock=lambda: FIXED_NOW)


def test_service_success_and_request_contract(provider_payloads):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=provider_payloads[request.url.host])

    result = asyncio.run(mock_service(provider_payloads, handler, Settings(latitude=40.7, longitude=-74.0)).get_current())
    assert result.timestamp == FIXED_NOW
    assert result.status == "available"
    assert (result.temperature_c, result.relative_humidity, result.pm2_5, result.pm10, result.china_aqi_estimate) == (23.4, 58, 17.2, 25.8, 26)
    assert result.latitude == 40.7 and result.longitude == -74.0
    assert result.weather_timestamp == datetime.fromtimestamp(1789784100, UTC)
    assert result.air_quality_timestamp == datetime.fromtimestamp(1789783200, UTC)
    assert len(requests) == 2
    for request in requests:
        assert request.url.params["latitude"] == "40.7"
        assert request.url.params["longitude"] == "-74.0"
        assert request.url.params["timezone"] == "UTC"
        assert request.url.params["timeformat"] == "unixtime"
        assert request.extensions["timeout"]["connect"] == 4.0
        assert request.extensions["timeout"]["read"] == 8.0
    weather = next(request for request in requests if request.url.host == "api.open-meteo.com")
    air = next(request for request in requests if request.url.host != "api.open-meteo.com")
    assert weather.url.path == "/v1/forecast"
    assert weather.url.params["current"] == "temperature_2m,relative_humidity_2m"
    assert weather.url.params["temperature_unit"] == "celsius"
    assert air.url.path == "/v1/air-quality"
    assert air.url.params["hourly"] == "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone"
    assert "current" not in air.url.params
    assert "us_aqi" not in str(air.url)


def test_missing_values_stay_null_and_real_zero_survives(provider_payloads):
    weather = provider_payloads["api.open-meteo.com"]["current"]
    weather["temperature_2m"] = 0
    weather.pop("relative_humidity_2m")
    air = provider_payloads["air-quality-api.open-meteo.com"]["hourly"]
    air["pm2_5"] = [None]
    air["pm10"] = [0]
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.status == "partial"
    assert result.temperature_c == 0 and result.pm10 == 0 and result.china_aqi_estimate is None
    assert result.relative_humidity is None and result.pm2_5 is None


@pytest.mark.parametrize("value", ["17.2", True, [], {}, float("nan"), float("inf"), -1])
def test_invalid_particle_values_are_unavailable(provider_payloads, value):
    provider_payloads["air-quality-api.open-meteo.com"]["hourly"]["pm2_5"] = [value]
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.pm2_5 is None
    assert result.pm10 == 25.8 and result.status == "partial"


@pytest.mark.parametrize("field,value", [("temperature_2m", -274), ("relative_humidity_2m", -1), ("relative_humidity_2m", 101)])
def test_invalid_weather_ranges_are_unavailable(provider_payloads, field, value):
    provider_payloads["api.open-meteo.com"]["current"][field] = value
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert getattr(result, "temperature_c" if field == "temperature_2m" else "relative_humidity") is None
    assert result.status == "partial"


@pytest.mark.parametrize("unit", [None, "°F", "unknown"])
def test_missing_or_wrong_units_never_get_mislabelled(provider_payloads, unit):
    provider_payloads["api.open-meteo.com"]["current_units"]["temperature_2m"] = unit
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.temperature_c is None and result.relative_humidity == 58


@pytest.mark.parametrize("body", [None, [], {}, {"error": True}, {"current": []}, {"current": {}, "current_units": {}}])
def test_malformed_source_preserves_other_provider(provider_payloads, body):
    provider_payloads["api.open-meteo.com"] = body
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.temperature_c is None and result.relative_humidity is None
    assert result.weather_timestamp is None
    assert result.pm2_5 == 17.2 and result.status == "partial"


@pytest.mark.parametrize("timestamp", [None, True, "2026-09-19T02:00:00", float("nan"), 10**100])
def test_invalid_timestamp_discards_only_its_source(provider_payloads, timestamp):
    provider_payloads["api.open-meteo.com"]["current"]["time"] = timestamp
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.weather_timestamp is None and result.temperature_c is None
    assert result.air_quality_timestamp is not None and result.china_aqi_estimate == 26


def test_timestamp_requires_explicit_epoch_metadata(provider_payloads):
    provider_payloads["api.open-meteo.com"]["current_units"]["time"] = "iso8601"
    result = asyncio.run(mock_service(provider_payloads).get_current())
    assert result.temperature_c is None and result.status == "partial"


@pytest.mark.parametrize("failure", ["connect", "read_timeout", "connect_timeout", "bad_json", 400, 429, 500, 503])
@pytest.mark.parametrize("failed_host", ["api.open-meteo.com", "air-quality-api.open-meteo.com"])
def test_provider_failure_preserves_partial_data(provider_payloads, failure, failed_host):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        if request.url.host != failed_host:
            return httpx.Response(200, json=provider_payloads[request.url.host])
        if failure == "connect":
            raise httpx.ConnectError("offline", request=request)
        if failure == "read_timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure == "connect_timeout":
            raise httpx.ConnectTimeout("timeout", request=request)
        if failure == "bad_json":
            return httpx.Response(200, text="not JSON")
        return httpx.Response(failure, json={"reason": "test upstream failure"})
    result = asyncio.run(mock_service(provider_payloads, handler).get_current())
    assert result.status == "partial" and len(calls) == 2  # No retry storm.
    if failed_host == "api.open-meteo.com":
        assert result.temperature_c is None and result.pm10 == 25.8
    else:
        assert result.pm10 is None and result.temperature_c == 23.4


def test_total_timeout_is_bounded_and_preserves_other_source(provider_payloads, monkeypatch):
    monkeypatch.setattr(environment, "OPEN_METEO_TOTAL_TIMEOUT_SECONDS", 0.01)
    async def handler(request):
        if request.url.host == "api.open-meteo.com":
            await asyncio.sleep(0.1)
        return httpx.Response(200, json=provider_payloads[request.url.host])
    result = asyncio.run(mock_service(provider_payloads, handler).get_current())
    assert result.temperature_c is None and result.pm2_5 == 17.2


@pytest.mark.parametrize("failure", ["missing", "timeout", "http", "malformed"])
def test_no_usable_data_becomes_controlled_endpoint_error(client, provider_payloads, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("offline timeout", request=request)
        if failure == "http":
            return httpx.Response(502)
        if failure == "malformed":
            return httpx.Response(200, text="{")
        payload = deepcopy(provider_payloads[request.url.host])
        key = "current" if request.url.host == "api.open-meteo.com" else "hourly"
        payload[key] = {"time": payload[key]["time"]}
        return httpx.Response(200, json=payload)
    client.app.dependency_overrides[environment.get_environment_service] = lambda: mock_service(provider_payloads, handler)
    response = client.get("/environment/current")
    assert response.status_code == 503
    assert response.json() == {"detail": environment.UNAVAILABLE_MESSAGE}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/symptoms").json() == []


@pytest.mark.parametrize("partial", [False, True])
def test_current_endpoint_never_rewrites_saved_snapshots(client, valid_record, provider_payloads, partial):
    saved = client.post("/symptoms", json=valid_record).json()
    if partial:
        provider_payloads["air-quality-api.open-meteo.com"]["hourly"]["pm10"] = [None]
    client.app.dependency_overrides[environment.get_environment_service] = lambda: mock_service(provider_payloads)
    response = client.get("/environment/current")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"timestamp", "weather_timestamp", "air_quality_timestamp", "status", "latitude", "longitude", "temperature_c", "relative_humidity", "pm2_5", "pm10", "nitrogen_dioxide", "sulfur_dioxide", "carbon_monoxide", "ozone", "china_aqi_estimate", "china_aqi_primary_pollutant"}
    assert body["status"] == ("partial" if partial else "available")
    assert body["pm10"] == (None if partial else 25.8)
    assert all(body[field].endswith("Z") for field in ("timestamp", "weather_timestamp", "air_quality_timestamp"))
    assert body["latitude"] == DEFAULT_LATITUDE and body["longitude"] == DEFAULT_LONGITUDE
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/symptoms").json() == [saved]


def test_config_defaults_and_environment_overrides(monkeypatch):
    monkeypatch.delenv("ALLERWATCH_LATITUDE", raising=False)
    monkeypatch.delenv("ALLERWATCH_LONGITUDE", raising=False)
    assert get_settings() == Settings(latitude=DEFAULT_LATITUDE, longitude=DEFAULT_LONGITUDE)
    monkeypatch.setenv("ALLERWATCH_LATITUDE", "-33.87")
    monkeypatch.setenv("ALLERWATCH_LONGITUDE", "151.21")
    assert get_settings() == Settings(latitude=-33.87, longitude=151.21)


@pytest.mark.parametrize("name,value", [("ALLERWATCH_LATITUDE", "91"), ("ALLERWATCH_LONGITUDE", "-181"), ("ALLERWATCH_LATITUDE", "nan"), ("ALLERWATCH_LONGITUDE", "abc")])
def test_invalid_location_does_not_send_network_requests(client, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        get_settings()
    def unexpected_client(*args, **kwargs):
        pytest.fail("Invalid configuration must not request external data")
    monkeypatch.setattr(environment.httpx, "AsyncClient", unexpected_client)
    assert client.get("/environment/current").status_code == 503
    assert client.get("/health").status_code == 200


def test_health_and_history_do_not_fetch_environment(client, monkeypatch):
    def unexpected_client(*args, **kwargs):
        pytest.fail("Reading health or history must not fetch environmental data")
    monkeypatch.setattr(environment.httpx, "AsyncClient", unexpected_client)
    assert client.get("/health").status_code == 200
    assert client.get("/symptoms").json() == []
