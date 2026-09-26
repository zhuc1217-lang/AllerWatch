import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..database import get_session
from ..config import is_public_demo
from ..models import SymptomRecord
from ..schemas import SymptomRecordCreate, SymptomRecordRead
from ..time_policy import ClockDependency, as_utc, validate_symptom_time
from ..services.environment_service import EnvironmentService, get_environment_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/symptoms", tags=["Symptoms"])
SessionDependency = Annotated[Session, Depends(get_session)]
EnvironmentDependency = Annotated[EnvironmentService, Depends(get_environment_service)]
RecordId = Annotated[int, Path(ge=1, le=2**63 - 1)]


def find_record(session: Session, record_id: int) -> SymptomRecord:
    record = session.get(SymptomRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symptom record not found")
    return record


@router.post("", response_model=SymptomRecordRead, status_code=status.HTTP_201_CREATED)
async def create_symptom(
    payload: SymptomRecordCreate, session: SessionDependency, environment: EnvironmentDependency, clock: ClockDependency,
    public_demo: Annotated[bool, Depends(is_public_demo)],
) -> SymptomRecord:
    received = as_utc(clock())
    values = payload.model_dump()
    # The current-observation form omits time; assign it from this same server clock.
    if "timestamp" not in payload.model_fields_set:
        values["timestamp"] = received
    validate_symptom_time(values["timestamp"], payload.is_synthetic, received)
    if public_demo:
        values["is_synthetic"] = True
    record = SymptomRecord(**values, received_at=received)
    try:
        current = await environment.get_current()
        snapshot = {
            "temperature_c": current.temperature_c,
            "relative_humidity": current.relative_humidity,
            "pm2_5": current.pm2_5,
            "pm10": current.pm10,
            "nitrogen_dioxide": current.nitrogen_dioxide,
            "sulfur_dioxide": current.sulfur_dioxide,
            "carbon_monoxide": current.carbon_monoxide,
            "ozone": current.ozone,
            "china_aqi_estimate": current.china_aqi_estimate,
            "china_aqi_primary_pollutant": current.china_aqi_primary_pollutant,
            "environment_timestamp": current.timestamp,
            "weather_timestamp": current.weather_timestamp,
            "air_quality_timestamp": current.air_quality_timestamp,
            "environment_latitude": current.latitude,
            "environment_longitude": current.longitude,
        }
    except Exception as exc:
        # Enrichment is optional, including unexpected provider/decoding failures.
        # Deliberately exclude database writes from this fallback. Do not log health data.
        logger.warning("Environmental snapshot unavailable (%s); saving symptoms", type(exc).__name__)
        snapshot = {}
    for field, value in snapshot.items():
        setattr(record, field, value)
    # No SQLite write transaction is held while awaiting Open-Meteo.
    return await run_in_threadpool(_save_record, session, record)


def _save_record(session: Session, record: SymptomRecord) -> SymptomRecord:
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("", response_model=list[SymptomRecordRead])
def list_symptoms(session: SessionDependency) -> list[SymptomRecord]:
    statement = select(SymptomRecord).order_by(
        SymptomRecord.timestamp.desc(), SymptomRecord.id.desc()
    )
    return list(session.scalars(statement))


@router.get("/{id}", response_model=SymptomRecordRead)
def get_symptom(id: RecordId, session: SessionDependency) -> SymptomRecord:
    return find_record(session, id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_symptom(id: RecordId, session: SessionDependency) -> Response:
    record = find_record(session, id)
    session.delete(record)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
