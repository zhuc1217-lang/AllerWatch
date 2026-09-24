"""Central environment settings for local use and an isolated public portfolio demo."""

import os
from datetime import timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = REPOSITORY_ROOT / "data" / "private" / "allerwatch.sqlite3"
DEFAULT_DEMO_DATABASE_PATH = REPOSITORY_ROOT / "data" / "public_demo" / "allerwatch.sqlite3"
LOCAL_FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173",
                          "http://localhost:4173", "http://127.0.0.1:4173"]

# Public London development example: these coordinates are the environmental
# monitoring location, not browser geolocation or an inferred user location.
DEFAULT_LATITUDE = 51.5074
DEFAULT_LONGITUDE = -0.1278
OPEN_METEO_IO_TIMEOUT_SECONDS = 8.0
OPEN_METEO_CONNECT_TIMEOUT_SECONDS = 4.0
OPEN_METEO_TOTAL_TIMEOUT_SECONDS = 10.0

# Fixed study calendar, independent of the environmental monitoring location.
# Changing this after daily collection begins requires a documented date migration.
STUDY_CALENDAR_LABEL = "UTC+08:00"
STUDY_CALENDAR = timezone(timedelta(hours=8), name=STUDY_CALENDAR_LABEL)


class Settings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    latitude: float = Field(default=DEFAULT_LATITUDE, ge=-90, le=90)
    longitude: float = Field(default=DEFAULT_LONGITUDE, ge=-180, le=180)
    database_path: Path | None = None
    public_demo_mode: bool = False
    frontend_origin: str | None = None

    @field_validator("frontend_origin")
    @classmethod
    def validate_origin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path
                or parsed.query or parsed.fragment or parsed.username or parsed.password or "*" in value):
            raise ValueError("FRONTEND_ORIGIN must be one HTTP(S) origin without a path or wildcard")
        return value

    def resolved_database_path(self, override: Path | None = None) -> Path:
        path = override if override is not None else self.database_path
        if path is None:
            path = DEFAULT_DEMO_DATABASE_PATH if self.public_demo_mode else DEFAULT_DATABASE_PATH
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        return path.resolve()


def get_settings() -> Settings:
    """Read optional PowerShell environment overrides; no .env loader is needed."""
    return Settings(
        latitude=os.environ.get("ALLERWATCH_LATITUDE", DEFAULT_LATITUDE),
        longitude=os.environ.get("ALLERWATCH_LONGITUDE", DEFAULT_LONGITUDE),
        database_path=os.environ.get("DATABASE_PATH") or None,
        public_demo_mode=os.environ.get("PUBLIC_DEMO_MODE", "false"),
        frontend_origin=os.environ.get("FRONTEND_ORIGIN") or None,
    )


def is_public_demo(request: Request) -> bool:
    """Mode is fixed for the running app; never trust a client-supplied flag."""
    return request.app.state.settings.public_demo_mode
