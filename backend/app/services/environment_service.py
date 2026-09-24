"""Fetch modelled current conditions; callers decide whether to display or store them."""

import asyncio
from datetime import UTC, datetime, timedelta
import math

import httpx
from pydantic import ValidationError

from ..config import (
    OPEN_METEO_CONNECT_TIMEOUT_SECONDS,
    OPEN_METEO_IO_TIMEOUT_SECONDS,
    OPEN_METEO_TOTAL_TIMEOUT_SECONDS,
    Settings,
    get_settings,
)
from ..environment_schemas import CurrentEnvironment
from ..time_policy import Clock, ClockDependency, ENVIRONMENT_MAX_AGE_HOURS, as_utc, utc_now

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
UNAVAILABLE_MESSAGE = "Environmental data are temporarily unavailable."

# Provider key, output key, expected unit, and valid numeric bounds.
WEATHER_FIELDS = (
    ("temperature_2m", "temperature_c", "°C", -273.15, None),
    ("relative_humidity_2m", "relative_humidity", "%", 0, 100),
)
AIR_QUALITY_FIELDS = (
    ("pm2_5", "pm2_5", "µg/m³", 0, None),
    ("pm10", "pm10", "µg/m³", 0, None),
    ("us_aqi", "us_aqi", "USAQI", 0, None),
)


class EnvironmentUnavailable(Exception):
    """No usable values, including an unavailable or invalid monitoring config."""


def _finite_number(value: object) -> float | None:
    # bool and numeric strings must not silently become environmental readings.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def _normalize(payload: object, fields: tuple, *, now: datetime) -> tuple[datetime | None, dict]:
    if not isinstance(payload, dict) or payload.get("error"):
        return None, {}
    current, units = payload.get("current"), payload.get("current_units")
    if not isinstance(current, dict) or not isinstance(units, dict):
        return None, {}
    # Unix seconds are absolute UTC instants. Never interpret a naive local string.
    seconds = _finite_number(current.get("time"))
    if seconds is None or units.get("time") != "unixtime":
        return None, {}
    try:
        valid_time = datetime.fromtimestamp(seconds, UTC)
    except (ValueError, OverflowError, OSError):
        return None, {}
    # A syntactically valid timestamp is not necessarily current. Both providers
    # use the same captured retrieval-completion clock and inclusive age window.
    current_time = as_utc(now)
    if not current_time - timedelta(hours=ENVIRONMENT_MAX_AGE_HOURS) <= valid_time <= current_time:
        return None, {}

    values = {}
    for provider_key, output_key, expected_unit, minimum, maximum in fields:
        value = _finite_number(current.get(provider_key))
        unit = units.get(provider_key)
        # Open-Meteo uses Greek mu; accept the equivalent micro sign as well.
        unit = unit.replace("μ", "µ") if isinstance(unit, str) else None
        if unit != expected_unit or (value is not None and (
            value < minimum or (maximum is not None and value > maximum)
        )):
            value = None
        values[output_key] = value
    return (valid_time if any(value is not None for value in values.values()) else None), values


async def _fetch_source(client: httpx.AsyncClient, url: str, params: dict) -> object:
    try:
        # In addition to HTTPX's per-operation timeouts, bound the whole source call.
        async with asyncio.timeout(OPEN_METEO_TOTAL_TIMEOUT_SECONDS):
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None


class EnvironmentService:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None,
                 *, clock: Clock = utc_now):
        self.settings = settings
        # A transport seam lets tests exercise real request/response handling offline.
        self.transport = transport
        self.clock = clock

    async def get_current(self) -> CurrentEnvironment:
        try:
            settings = self.settings or get_settings()
        except ValidationError as exc:
            raise EnvironmentUnavailable(UNAVAILABLE_MESSAGE) from exc
        common = {"latitude": settings.latitude, "longitude": settings.longitude, "timezone": "UTC", "timeformat": "unixtime"}
        timeout = httpx.Timeout(OPEN_METEO_IO_TIMEOUT_SECONDS, connect=OPEN_METEO_CONNECT_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            weather_payload, air_payload = await asyncio.gather(
                _fetch_source(client, WEATHER_URL, common | {"current": "temperature_2m,relative_humidity_2m", "temperature_unit": "celsius"}),
                _fetch_source(client, AIR_QUALITY_URL, common | {"current": "pm2_5,pm10,us_aqi"}),
            )
        completed = as_utc(self.clock())
        weather = _normalize(weather_payload, WEATHER_FIELDS, now=completed)
        air = _normalize(air_payload, AIR_QUALITY_FIELDS, now=completed)
        values = {key: None for _, key, *_ in (*WEATHER_FIELDS, *AIR_QUALITY_FIELDS)}
        values.update(weather[1])
        values.update(air[1])
        if all(value is None for value in values.values()):
            raise EnvironmentUnavailable(UNAVAILABLE_MESSAGE)
        return CurrentEnvironment(
            timestamp=completed, weather_timestamp=weather[0], air_quality_timestamp=air[0],
            status="available" if all(value is not None for value in values.values()) else "partial",
            latitude=settings.latitude, longitude=settings.longitude, **values,
        )


def get_environment_service(clock: ClockDependency) -> EnvironmentService:
    return EnvironmentService(clock=clock)
