from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..analysis.schemas import DatasetMode
from ..daily_health import DailyHealthCreate, DailyHealthList, DailyHealthRead, DailyHealthRecord, DailyHealthValues, study_date
from ..database import get_session
from ..config import is_public_demo
from ..time_policy import ClockDependency, as_utc, validate_daily_date

router = APIRouter(prefix="/daily-health", tags=["Daily health"])
SessionDependency = Annotated[Session, Depends(get_session)]
DatePath = Annotated[str, Path(pattern=r"^\d{4}-\d{2}-\d{2}$")]
DemoDependency = Annotated[bool, Depends(is_public_demo)]


def find_daily(session: Session, value: str, synthetic: bool) -> DailyHealthRecord:
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Use a valid calendar date in YYYY-MM-DD format") from None
    record = session.scalar(select(DailyHealthRecord).where(
        DailyHealthRecord.date == day, DailyHealthRecord.is_synthetic.is_(synthetic)))
    if record is None:
        raise HTTPException(404, "No daily health record for this date and observation type")
    return record


@router.post("", response_model=DailyHealthRead, status_code=201)
def create_daily(payload: DailyHealthCreate, session: SessionDependency, clock: ClockDependency, public_demo: DemoDependency) -> DailyHealthRecord:
    now = as_utc(clock())
    validate_daily_date(payload.date, payload.is_synthetic, now)
    values = payload.model_dump()
    if public_demo:
        values["is_synthetic"] = True
    record = DailyHealthRecord(**values, created_at=now, updated_at=now)
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "A daily health record already exists for this date and type. Load it before updating.") from None
    session.refresh(record)
    return record


@router.get("", response_model=DailyHealthList)
def list_daily(session: SessionDependency, clock: ClockDependency, dataset: Annotated[DatasetMode, Query()] = "real_only") -> DailyHealthList:
    statement = select(DailyHealthRecord).order_by(DailyHealthRecord.date.desc(), DailyHealthRecord.is_synthetic, DailyHealthRecord.id.desc())
    if dataset != "all":
        statement = statement.where(DailyHealthRecord.is_synthetic.is_(dataset == "synthetic_only"))
    return DailyHealthList(today=study_date(as_utc(clock())), records=list(session.scalars(statement)))


@router.get("/{date}", response_model=DailyHealthRead)
def read_daily(date: DatePath, session: SessionDependency, public_demo: DemoDependency, is_synthetic: bool = False) -> DailyHealthRecord:
    return find_daily(session, date, public_demo or is_synthetic)


@router.put("/{date}", response_model=DailyHealthRead)
def update_daily(date: DatePath, payload: DailyHealthValues, session: SessionDependency, clock: ClockDependency,
                 public_demo: DemoDependency, is_synthetic: bool = False) -> DailyHealthRecord:
    record = find_daily(session, date, public_demo or is_synthetic)
    now = as_utc(clock())
    validate_daily_date(record.date, record.is_synthetic, now, "path")
    for field, value in payload.model_dump().items():
        setattr(record, field, value)
    record.updated_at = now
    session.commit()
    session.refresh(record)
    return record
