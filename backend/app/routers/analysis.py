from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis.associations import associate_dataset
from ..analysis.dataset import AnalysisDataset, prepare_dataset
from ..analysis.descriptive import describe_dataset
from ..analysis.lagged_associations import LaggedAssociationsResponse, lagged_associations
from ..analysis.schemas import AssociationsResponse, DatasetMode, DescriptiveResponse
from ..database import get_session
from ..models import SymptomRecord
from ..daily_health import DailyHealthRecord
from ..analysis.daily_health_associations import DailyAssociationsResponse, daily_health_associations
from ..analysis.risk_model import ModelMode, ModelResponse, run_risk_model

router = APIRouter(prefix="/analysis", tags=["Exploratory analysis"])


def get_dataset(session: Annotated[Session, Depends(get_session)],
                dataset: Annotated[DatasetMode, Query()] = "real_only") -> AnalysisDataset:
    return prepare_dataset(list(session.scalars(select(SymptomRecord))), dataset)


DatasetDependency = Annotated[AnalysisDataset, Depends(get_dataset)]


@router.get("/descriptive", response_model=DescriptiveResponse)
def descriptive(dataset: DatasetDependency) -> DescriptiveResponse:
    return describe_dataset(dataset)


@router.get("/associations", response_model=AssociationsResponse)
def associations(dataset: DatasetDependency) -> AssociationsResponse:
    return associate_dataset(dataset)


@router.get("/lagged-associations", response_model=LaggedAssociationsResponse)
def lagged(dataset: DatasetDependency) -> LaggedAssociationsResponse:
    return lagged_associations(dataset)


@router.get("/daily-health-associations", response_model=DailyAssociationsResponse)
def daily_associations(dataset: DatasetDependency, session: Annotated[Session, Depends(get_session)]) -> DailyAssociationsResponse:
    return daily_health_associations(dataset, list(session.scalars(select(DailyHealthRecord))))


@router.get("/risk-model", response_model=ModelResponse)
def risk_model(session: Annotated[Session, Depends(get_session)],
               dataset: Annotated[ModelMode, Query()] = "real_only") -> ModelResponse:
    return run_risk_model(list(session.scalars(select(SymptomRecord))),
                          list(session.scalars(select(DailyHealthRecord))), dataset)
