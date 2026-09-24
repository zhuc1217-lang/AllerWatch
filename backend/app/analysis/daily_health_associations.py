from collections.abc import Sequence
from typing import Literal

from ..config import STUDY_CALENDAR_LABEL
from ..daily_health import DailyHealthRecord, study_date
from .associations import paired_spearman
from .dataset import AnalysisDataset, NumericRow, finite_number
from .schemas import MINIMUM_PAIRS, DatasetMetadata, PairStatistics

DailyVariable = Literal["sleep_duration_hours", "sleep_quality", "stress_level", "exercise_minutes"]
DAILY_VARIABLES: tuple[DailyVariable, ...] = ("sleep_duration_hours", "sleep_quality", "stress_level", "exercise_minutes")


class DailyAssociation(PairStatistics):
    variable: DailyVariable
    real_pairs: int
    synthetic_pairs: int
    distinct_daily_records: int


class DailyAssociationsResponse(DatasetMetadata):
    outcome: Literal["tnss"] = "tnss"
    calendar_timezone: str = STUDY_CALENDAR_LABEL
    join_method: Literal["study_date_and_same_provenance"] = "study_date_and_same_provenance"
    minimum_pairs: int = MINIMUM_PAIRS
    p_value_method: Literal["two_sided_asymptotic_unadjusted"] = "two_sided_asymptotic_unadjusted"
    daily_record_count: int
    real_daily_count: int
    synthetic_daily_count: int
    matched_symptom_count: int
    missing_daily_symptom_count: int
    matched_daily_records: int
    daily_records_without_symptoms: int
    associations: list[DailyAssociation]


def join_daily_health(dataset: AnalysisDataset, daily_records: Sequence[DailyHealthRecord]):
    mode = dataset.metadata.dataset_mode
    selected = [item for item in daily_records if mode == "all" or item.is_synthetic == (mode == "synthetic_only")]
    lookup = {(item.date, item.is_synthetic): item for item in selected}
    rows: list[NumericRow] = []
    matches: list[DailyHealthRecord | None] = []
    for observation in dataset.records:
        daily = lookup.get((study_date(observation.timestamp), observation.is_synthetic))
        rows.append({"tnss": finite_number(observation.tnss), **{
            variable: finite_number(getattr(daily, variable)) if daily else None for variable in DAILY_VARIABLES}})
        matches.append(daily)
    return selected, rows, matches


def daily_health_associations(dataset: AnalysisDataset, daily_records: Sequence[DailyHealthRecord]) -> DailyAssociationsResponse:
    selected, rows, matches = join_daily_health(dataset, daily_records)
    matched_keys = {(item.date, item.is_synthetic) for item in matches if item is not None}
    results = []
    for variable in DAILY_VARIABLES:
        paired = [item for row, item in zip(rows, matches) if item is not None and
                  finite_number(row.get("tnss")) is not None and finite_number(row.get(variable)) is not None]
        synthetic_pairs = sum(item.is_synthetic for item in paired)
        results.append(DailyAssociation(variable=variable, **paired_spearman(rows, variable).model_dump(),
            real_pairs=len(paired) - synthetic_pairs, synthetic_pairs=synthetic_pairs,
            distinct_daily_records=len({(item.date, item.is_synthetic) for item in paired})))
    count = sum(item is not None for item in matches)
    synthetic = sum(item.is_synthetic for item in selected)
    return DailyAssociationsResponse(**dataset.metadata.model_dump(), associations=results,
        daily_record_count=len(selected), real_daily_count=len(selected) - synthetic, synthetic_daily_count=synthetic,
        matched_symptom_count=count, missing_daily_symptom_count=len(rows) - count,
        matched_daily_records=len(matched_keys), daily_records_without_symptoms=len(selected) - len(matched_keys))
