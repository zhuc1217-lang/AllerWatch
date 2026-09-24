"""Daily diary model, validation, and the shared calendar-date convention."""
from datetime import UTC, date as CalendarDate, datetime
import re
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import Boolean, CheckConstraint, Date, Float, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from .config import STUDY_CALENDAR, STUDY_CALENDAR_LABEL
from .database import Base, UTCDateTime


def study_date(timestamp: datetime) -> CalendarDate:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("A timezone-aware symptom timestamp is required")
    return timestamp.astimezone(STUDY_CALENDAR).date()


class DailyHealthRecord(Base):
    __tablename__ = "daily_health_records"
    __table_args__ = (
        UniqueConstraint("date", "is_synthetic", name="uq_daily_health_date_type"),
        CheckConstraint("typeof(sleep_duration_hours) IN ('integer', 'real') AND sleep_duration_hours BETWEEN 0 AND 24", name="ck_daily_sleep_duration"),
        CheckConstraint("typeof(sleep_quality) = 'integer' AND sleep_quality BETWEEN 1 AND 5", name="ck_daily_sleep_quality"),
        CheckConstraint("typeof(stress_level) = 'integer' AND stress_level BETWEEN 1 AND 5", name="ck_daily_stress"),
        CheckConstraint("typeof(exercise_minutes) = 'integer' AND exercise_minutes BETWEEN 0 AND 1440", name="ck_daily_exercise"),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[CalendarDate] = mapped_column(Date, index=True)
    sleep_duration_hours: Mapped[float] = mapped_column(Float)
    sleep_quality: Mapped[int]
    stress_level: Mapped[int]
    exercise_minutes: Mapped[int]
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_synthetic: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="ck_daily_synthetic"), default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=lambda: datetime.now(UTC))
    # Last server save; not a reconstruction of earlier diary versions.
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class DailyHealthValues(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sleep_duration_hours: Annotated[float, Field(strict=True, ge=0, le=24)]
    sleep_quality: Annotated[int, Field(strict=True, ge=1, le=5)]
    stress_level: Annotated[int, Field(strict=True, ge=1, le=5)]
    exercise_minutes: Annotated[int, Field(strict=True, ge=0, le=1440)]
    notes: str | None = None


class DailyHealthCreate(DailyHealthValues):
    date: CalendarDate
    is_synthetic: StrictBool = False

    @field_validator("date", mode="before")
    @classmethod
    def date_only(cls, value):
        if type(value) is CalendarDate:
            return value
        if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("Use a calendar date in YYYY-MM-DD format, without a time or timezone")
        return CalendarDate.fromisoformat(value)


class DailyHealthRead(DailyHealthCreate):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)
    id: int
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None


class DailyHealthList(BaseModel):
    calendar_timezone: str = STUDY_CALENDAR_LABEL
    today: CalendarDate
    records: list[DailyHealthRead]
