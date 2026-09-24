"""Backward-only approximate matching of existing, irregular symptom-time snapshots."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Literal

from pydantic import Field

from ..models import SymptomRecord
from .associations import associate_variable
from .dataset import AnalysisDataset, finite_number
from .environment_timing import (SOURCE_TIME as ENVIRONMENT_SOURCE_TIME,
                                 TOLERANCE_HOURS, contemporaneous_times_eligible, utc)
from .schemas import MINIMUM_PAIRS, AnalysisModel, AssociationResult, DatasetMetadata

LagExposure = Literal["pm2_5", "us_aqi", "relative_humidity"]
LagHours = Literal[0, 6, 12, 24]
LAGS: tuple[LagHours, ...] = (0, 6, 12, 24)
LAG_EXPOSURES: tuple[LagExposure, ...] = ("pm2_5", "us_aqi", "relative_humidity")
SOURCE_TIME = {variable: ENVIRONMENT_SOURCE_TIME[variable] for variable in LAG_EXPOSURES}


class LagResult(AssociationResult):
    variable: LagExposure
    lag_hours: LagHours
    real_pairs: int = Field(ge=0)
    synthetic_pairs: int = Field(ge=0)
    distinct_source_records: int = Field(ge=0)
    actual_lag_hours_min: float | None = None
    actual_lag_hours_median: float | None = None
    actual_lag_hours_max: float | None = None


class MatchingMethod(AnalysisModel):
    approximate: Literal[True] = True
    tolerance_hours: int = TOLERANCE_HOURS
    timezone: Literal["UTC"] = "UTC"
    method: Literal["same_record_0h_backward_source_time_other_lags"] = "same_record_0h_backward_source_time_other_lags"
    exposure_time_fields: dict[str, str] = Field(default_factory=lambda: dict(SOURCE_TIME))
    nonzero_source_record_and_retrieval_before_target: Literal[True] = True
    cross_provenance_matching: Literal[False] = False
    zero_lag_note: str = "Same-report snapshot: source valid time must not exceed reporting time; retrieval completion may follow validation."


class LaggedAssociationsResponse(DatasetMetadata):
    outcome: Literal["tnss"] = "tnss"
    minimum_pairs: int = MINIMUM_PAIRS
    p_value_method: Literal["two_sided_asymptotic_unadjusted"] = "two_sided_asymptotic_unadjusted"
    lags_hours: tuple[LagHours, ...] = LAGS
    matching: MatchingMethod = Field(default_factory=MatchingMethod)
    results: list[LagResult]


@dataclass(frozen=True)
class ExposureMatch:
    source: SymptomRecord
    value: float
    valid_time: datetime
    actual_lag_hours: float


def same_location(left: SymptomRecord, right: SymptomRecord) -> bool:
    left_location = (finite_number(left.environment_latitude), finite_number(left.environment_longitude))
    right_location = (finite_number(right.environment_latitude), finite_number(right.environment_longitude))
    if None in left_location or None in right_location:
        return bool(left.is_synthetic and right.is_synthetic and
                    left_location == right_location == (None, None))
    return left_location == right_location


def match_exposure(outcome: SymptomRecord, candidates: Sequence[SymptomRecord],
                   variable: LagExposure, lag_hours: LagHours) -> ExposureMatch | None:
    """No inferred timestamps, forward matches, cross-provenance or distant carry-forward."""
    if lag_hours not in LAGS or variable not in LAG_EXPOSURES:
        raise ValueError("Unsupported exposure or lag")
    time = utc(outcome.timestamp)
    if time is None:
        return None
    if lag_hours == 0:
        value = finite_number(getattr(outcome, variable))
        valid_time = utc(getattr(outcome, SOURCE_TIME[variable]))
        if value is None or not contemporaneous_times_eligible(time, valid_time, outcome.environment_timestamp):
            return None
        return ExposureMatch(outcome, value, valid_time, (time - valid_time).total_seconds() / 3600)
    target = time - timedelta(hours=lag_hours)
    earliest = target - timedelta(hours=TOLERANCE_HOURS)
    eligible = []
    for source in candidates:
        if source.is_synthetic != outcome.is_synthetic:
            continue
        value = finite_number(getattr(source, variable))
        valid_time = utc(getattr(source, SOURCE_TIME[variable]))
        if value is None or valid_time is None or not earliest <= valid_time <= target:
            continue
        retrieved = utc(source.environment_timestamp)
        if retrieved is None or valid_time > retrieved:
            continue
        if lag_hours:
            reported = utc(source.timestamp)
            if reported is None or reported > target or retrieved > target or not same_location(outcome, source):
                continue
        eligible.append((valid_time, retrieved, source.id or 0, source, value))
    if not eligible:
        return None
    valid_time, _, _, source, value = max(eligible, key=lambda item: item[:3])
    return ExposureMatch(source, value, valid_time, (time - valid_time).total_seconds() / 3600)


def lagged_associations(dataset: AnalysisDataset) -> LaggedAssociationsResponse:
    results = []
    for variable in LAG_EXPOSURES:
        for lag in LAGS:
            rows, matches, real_pairs, synthetic_pairs = [], [], 0, 0
            for outcome in dataset.records:
                tnss = finite_number(outcome.tnss)
                match = match_exposure(outcome, dataset.records, variable, lag)
                rows.append({"tnss": tnss, variable: match.value if match else None})
                if match is not None and tnss is not None:
                    matches.append(match)
                    if outcome.is_synthetic:
                        synthetic_pairs += 1
                    else:
                        real_pairs += 1
            association = associate_variable(rows, variable)
            offsets = [match.actual_lag_hours for match in matches]
            results.append(LagResult(**association.model_dump(), lag_hours=lag,
                real_pairs=real_pairs, synthetic_pairs=synthetic_pairs,
                distinct_source_records=len({id(match.source) for match in matches}),
                actual_lag_hours_min=min(offsets, default=None),
                actual_lag_hours_median=median(offsets) if offsets else None,
                actual_lag_hours_max=max(offsets, default=None)))
    return LaggedAssociationsResponse(**dataset.metadata.model_dump(), results=results)
