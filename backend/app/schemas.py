from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    computed_field,
    field_validator,
)

from .analysis.environment_timing import SOURCE_TIME, contemporaneous_times_eligible
from .analysis.schemas import EXPOSURES, Exposure

SymptomScore = Annotated[int, Field(strict=True, ge=0, le=3)]
OverallSeverity = Annotated[int, Field(strict=True, ge=0, le=10)]


class SymptomRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    nasal_congestion: SymptomScore
    sneezing: SymptomScore
    runny_nose: SymptomScore
    nasal_itching: SymptomScore
    eye_symptoms: SymptomScore
    overall_severity: OverallSeverity
    medication_taken: StrictBool
    notes: str | None = None
    is_synthetic: StrictBool = False

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class SymptomRecordRead(SymptomRecordCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_at: AwareDatetime | None = None
    tnss: int = Field(ge=0, le=12, json_schema_extra={"readOnly": True})
    # Response-only snapshot fields; callers cannot supply or edit them in POST.
    temperature_c: float | None = None
    relative_humidity: float | None = None
    pm2_5: float | None = None
    pm10: float | None = None
    us_aqi: float | None = None
    environment_timestamp: AwareDatetime | None = None
    weather_timestamp: AwareDatetime | None = None
    air_quality_timestamp: AwareDatetime | None = None
    environment_latitude: float | None = None
    environment_longitude: float | None = None

    @computed_field
    @property
    def environment_time_eligible(self) -> dict[Exposure, bool]:
        """Response-only time checks; raw values remain untouched, even if false."""
        return {variable: contemporaneous_times_eligible(
            self.timestamp, getattr(self, SOURCE_TIME[variable]), self.environment_timestamp
        ) for variable in EXPOSURES}
