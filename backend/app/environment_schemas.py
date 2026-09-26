from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class CurrentEnvironment(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    # Retrieval completion time. Provider valid times are separate below.
    timestamp: AwareDatetime
    weather_timestamp: AwareDatetime | None
    air_quality_timestamp: AwareDatetime | None
    status: Literal["available", "partial"]
    temperature_c: float | None
    relative_humidity: float | None = Field(ge=0, le=100)
    pm2_5: float | None = Field(ge=0)
    pm10: float | None = Field(ge=0)
    nitrogen_dioxide: float | None = Field(default=None, ge=0)
    sulfur_dioxide: float | None = Field(default=None, ge=0)
    carbon_monoxide: float | None = Field(default=None, ge=0)
    ozone: float | None = Field(default=None, ge=0)
    china_aqi_estimate: int | None = Field(default=None, ge=0, le=500)
    china_aqi_primary_pollutant: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
