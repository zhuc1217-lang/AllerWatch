from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, Float, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class SymptomRecord(Base):
    __tablename__ = "symptom_records"
    __table_args__ = (
        *(
            CheckConstraint(
                f"typeof({field}) = 'integer' AND {field} BETWEEN 0 AND {maximum}",
                name=f"ck_symptom_records_{field}",
            )
            for field, maximum in (
                ("nasal_congestion", 3),
                ("sneezing", 3),
                ("runny_nose", 3),
                ("nasal_itching", 3),
                ("eye_symptoms", 3),
                ("overall_severity", 10),
            )
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), index=True
    )
    # Server acceptance time, independent of reported symptom time/enrichment.
    # No ORM/server default: migration and direct legacy/demo rows stay unknown.
    received_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    nasal_congestion: Mapped[int]
    sneezing: Mapped[int]
    runny_nose: Mapped[int]
    nasal_itching: Mapped[int]
    eye_symptoms: Mapped[int]
    overall_severity: Mapped[int]
    medication_taken: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_medication_taken")
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_is_synthetic"),
        default=False,
        server_default=false(),
    )

    # Estimated outdoor conditions at submission, not measured personal exposure.
    temperature_c: Mapped[float | None] = mapped_column(Float, default=None)
    relative_humidity: Mapped[float | None] = mapped_column(Float, default=None)
    pm2_5: Mapped[float | None] = mapped_column(Float, default=None)
    pm10: Mapped[float | None] = mapped_column(Float, default=None)
    # Legacy/deprecated: preserved only; never populated by new snapshots.
    us_aqi: Mapped[float | None] = mapped_column(Float, default=None)
    nitrogen_dioxide: Mapped[float | None] = mapped_column(Float, default=None)
    sulfur_dioxide: Mapped[float | None] = mapped_column(Float, default=None)
    carbon_monoxide: Mapped[float | None] = mapped_column(Float, default=None)
    ozone: Mapped[float | None] = mapped_column(Float, default=None)
    china_aqi_estimate: Mapped[int | None] = mapped_column(default=None)
    china_aqi_primary_pollutant: Mapped[str | None] = mapped_column(Text, default=None)
    environment_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    weather_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    air_quality_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    # Preserve the monitoring location even if configuration changes later.
    environment_latitude: Mapped[float | None] = mapped_column(Float, default=None)
    environment_longitude: Mapped[float | None] = mapped_column(Float, default=None)

    @property
    def tnss(self) -> int:
        """Return the four nasal scores, excluding eye symptoms and overall severity."""
        return (
            self.nasal_congestion
            + self.sneezing
            + self.runny_nose
            + self.nasal_itching
        )
