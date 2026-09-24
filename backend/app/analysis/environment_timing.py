"""Shared temporal eligibility for same-record environmental relationships.

This is source-time alignment, not an as-of prediction availability rule.
No values are changed and no historical exposure is reconstructed.
"""
from datetime import UTC, datetime, timedelta

TOLERANCE_HOURS = 3
SOURCE_TIME = {
    "pm2_5": "air_quality_timestamp",
    "pm10": "air_quality_timestamp",
    "us_aqi": "air_quality_timestamp",
    "relative_humidity": "weather_timestamp",
    "temperature_c": "weather_timestamp",
}


def utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Environmental matching requires timezone-aware timestamps")
    return value.astimezone(UTC)


def contemporaneous_times_eligible(
    symptom_time: datetime | None,
    source_time: datetime | None,
    retrieval_time: datetime | None,
) -> bool:
    """Inclusive [T - 3h, T], with known retrieval at/after source valid time.

    Retrieval may follow symptom validation, as in the original lag-0 rule.
    Missing timestamp metadata fails closed; naive datetimes are rejected.
    """
    symptom, source, retrieved = map(utc, (symptom_time, source_time, retrieval_time))
    return (symptom is not None and source is not None and retrieved is not None
            and symptom - timedelta(hours=TOLERANCE_HOURS) <= source <= symptom
            and source <= retrieved)
