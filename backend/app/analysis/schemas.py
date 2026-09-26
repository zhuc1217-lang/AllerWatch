from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .environment_timing import TOLERANCE_HOURS

DatasetMode = Literal["real_only", "synthetic_only", "all"]
Exposure = Literal["pm2_5", "pm10", "china_aqi_estimate", "relative_humidity", "temperature_c"]
Variable = Literal["tnss", "overall_severity", "temperature_c", "relative_humidity", "pm2_5", "pm10", "china_aqi_estimate"]
EXPOSURES: tuple[Exposure, ...] = ("pm2_5", "pm10", "china_aqi_estimate", "relative_humidity", "temperature_c")
VARIABLES: tuple[Variable, ...] = ("tnss", "overall_severity", *EXPOSURES)
MINIMUM_PAIRS = 10


class AnalysisModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class DatasetMetadata(AnalysisModel):
    dataset_mode: DatasetMode
    record_count: int = Field(ge=0)
    real_count: int = Field(ge=0)
    synthetic_count: int = Field(ge=0)
    includes_synthetic: bool
    data_notice: str
    date_start: datetime | None
    date_end: datetime | None
    observation_unit: Literal["individual_observation"] = "individual_observation"


class DescriptiveSummary(AnalysisModel):
    n: int = Field(ge=0)
    missing: int = Field(ge=0)
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    q1: float | None = None
    q3: float | None = None
    max: float | None = None


class DescriptiveResponse(DatasetMetadata):
    variables: dict[Variable, DescriptiveSummary]
    standard_deviation: Literal["sample_ddof_1"] = "sample_ddof_1"
    percentile_method: Literal["linear"] = "linear"


class PairStatistics(AnalysisModel):
    n: int = Field(ge=0)
    missing_pairs: int = Field(ge=0)
    spearman_rho: float | None = Field(default=None, ge=-1, le=1)
    p_value: float | None = Field(default=None, ge=0, le=1)
    status: Literal["ok", "insufficient_data", "insufficient_variation", "unavailable"]


class AssociationResult(PairStatistics):
    variable: Exposure


class ContemporaneousAssociationResult(AssociationResult):
    # Disjoint from missing numerical pairs; n contains only time-eligible pairs.
    temporally_excluded_pairs: int = Field(ge=0)


class AssociationsResponse(DatasetMetadata):
    outcome: Literal["tnss"] = "tnss"
    minimum_pairs: int = MINIMUM_PAIRS
    p_value_method: Literal["two_sided_asymptotic_unadjusted"] = "two_sided_asymptotic_unadjusted"
    temporal_tolerance_hours: int = TOLERANCE_HOURS
    associations: list[ContemporaneousAssociationResult]
