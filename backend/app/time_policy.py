"""Server clock and write-time policies; read paths never censor legacy data."""
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException

from .config import STUDY_CALENDAR

Clock = Callable[[], datetime]
SYMPTOM_CLOCK_SKEW_SECONDS = 60
ENVIRONMENT_MAX_AGE_HOURS = 3


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("The server clock must return a timezone-aware instant")
    return value.astimezone(UTC)


def get_clock() -> Clock:
    """Overridable FastAPI dependency; services also accept a clock explicitly."""
    return utc_now


ClockDependency = Annotated[Clock, Depends(get_clock)]


def field_error(field: str, message: str, location: str = "body") -> None:
    raise HTTPException(422, detail=[{"loc": [location, field], "msg": message, "type": "value_error"}])


def validate_symptom_time(timestamp: datetime, synthetic: bool, received: datetime) -> None:
    if not synthetic and as_utc(timestamp) > as_utc(received) + timedelta(seconds=SYMPTOM_CLOCK_SKEW_SECONDS):
        field_error("timestamp", "Real symptom time cannot be more than 60 seconds ahead of the server UTC clock.")


def validate_daily_date(day: date, synthetic: bool, received: datetime, location: str = "body") -> None:
    if not synthetic and day > as_utc(received).astimezone(STUDY_CALENDAR).date():
        field_error("date", "Real daily health dates cannot be after today in the UTC+08:00 study calendar.", location)
