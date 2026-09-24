"""Read-only, fixed-protocol next-observation experiment; never a clinical model."""
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import floor
from statistics import median
from typing import Literal
import warnings

import numpy as np
from pydantic import Field
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..daily_health import DailyHealthRecord, study_date
from ..models import SymptomRecord
from .dataset import finite_number, prepare_dataset
from .schemas import AnalysisModel, DatasetMetadata

ModelMode = Literal["real_only", "synthetic_only"]
ENVIRONMENT = ("pm2_5", "pm10", "us_aqi", "relative_humidity", "temperature_c")
DAILY_FEATURES = ("previous_day_sleep_duration", "previous_day_sleep_quality",
                  "previous_day_stress_level", "previous_day_exercise_minutes")
FEATURES = ("previous_tnss", "previous_overall_severity", *ENVIRONMENT, *DAILY_FEATURES)
MINIMUM_ROWS = 30
MINIMUM_TRAIN_CLASS = 3
MINIMUM_TOTAL_CLASS = 5
SEED = 42


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Model timestamps must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class ModelRow:
    feature_timestamp: datetime
    target_timestamp: datetime
    target_available_timestamp: datetime
    previous_report_timestamp: datetime
    features: dict[str, float | None]
    target: int
    dataset_mode: ModelMode
    feature_record_id: int | None
    target_record_id: int | None

    def __post_init__(self):
        for stamp in (self.feature_timestamp, self.target_timestamp,
                      self.target_available_timestamp, self.previous_report_timestamp):
            aware_utc(stamp)
        if not self.previous_report_timestamp <= self.feature_timestamp < self.target_timestamp <= self.target_available_timestamp:
            raise ValueError("All predictors must precede their target observation")
        if set(self.features) != set(FEATURES) or self.target not in (0, 1):
            raise ValueError("Invalid model feature/target definition")
        if self.dataset_mode not in ("real_only", "synthetic_only"):
            raise ValueError("Mixed model training is prohibited")


@dataclass(frozen=True)
class FeatureDataset:
    rows: tuple[ModelRow, ...]
    candidate_pairs: int
    excluded_pairs: dict[str, int]
    daily_candidates: dict[str, int]


def report_available(record: SymptomRecord) -> datetime | None:
    reported = aware_utc(record.timestamp)
    # Prospective receipt is an additional lower bound, never a backfilled time.
    # Keep the existing conservative retrieval requirement for model eligibility.
    if record.environment_timestamp is not None:
        return max(reported, aware_utc(record.environment_timestamp),
                   aware_utc(record.received_at) if record.received_at is not None else reported)
    # Only the simulation has a known generated reporting-time convention on outages.
    if record.is_synthetic:
        return max(reported, aware_utc(record.received_at)) if record.received_at is not None else reported
    return None


def daily_candidate_reason(previous: SymptomRecord, at: datetime,
                           diaries: dict[tuple, DailyHealthRecord]) -> str:
    """Audit previous-day candidates, but never treat an unversioned value as historical."""
    candidate = diaries.get((study_date(at) - timedelta(days=1), previous.is_synthetic))
    if candidate is None:
        return "no_previous_day_record"
    if candidate.created_at is None:
        return "unknown_creation_time"
    if aware_utc(candidate.created_at) > at:
        return "created_after_prediction"
    # Even with a prospective last-edit time, this milestone does not enable
    # daily predictors or reconstruct older diary versions. Keep the frozen rule.
    return "unversioned_daily_record"


def build_model_rows(records: Sequence[SymptomRecord], daily_records: Sequence[DailyHealthRecord],
                     mode: ModelMode) -> FeatureDataset:
    if mode not in ("real_only", "synthetic_only"):
        raise ValueError("Choose real_only or synthetic_only; mixed training is prohibited")
    synthetic = mode == "synthetic_only"
    selected = sorted((r for r in records if r.is_synthetic == synthetic),
                      key=lambda r: (aware_utc(r.timestamp), r.id or 0))
    times = Counter(aware_utc(r.timestamp) for r in selected)
    diaries = {(r.date, r.is_synthetic): r for r in daily_records if r.is_synthetic == synthetic}
    rows, exclusions, daily_counts = [], Counter(), Counter()
    # Form adjacent pairs first; rejecting one must not reassign its next target.
    for previous, target in zip(selected, selected[1:]):
        before, after = aware_utc(previous.timestamp), aware_utc(target.timestamp)
        if times[before] > 1 or times[after] > 1:
            exclusions["ambiguous_equal_timestamps"] += 1
            continue
        at, label_available = report_available(previous), report_available(target)
        if at is None or label_available is None:
            exclusions["unknown_real_report_availability"] += 1
            continue
        if not before <= at < after:
            exclusions["predictors_not_before_target"] += 1
            continue
        prior_tnss, prior_overall, next_tnss = map(finite_number, (previous.tnss, previous.overall_severity, target.tnss))
        if prior_tnss is None or prior_overall is None or next_tnss is None:
            exclusions["missing_symptom_scores"] += 1
            continue
        features = {name: None for name in FEATURES}
        features.update(previous_tnss=prior_tnss, previous_overall_severity=prior_overall)
        retrieved = aware_utc(previous.environment_timestamp) if previous.environment_timestamp is not None else None
        for variable in ENVIRONMENT:
            stamp = previous.air_quality_timestamp if variable in ENVIRONMENT[:3] else previous.weather_timestamp
            valid_time = aware_utc(stamp) if stamp is not None else None
            if (retrieved is not None and before <= retrieved <= at and valid_time is not None
                    and before - timedelta(hours=3) <= valid_time <= before):
                features[variable] = finite_number(getattr(previous, variable))
        daily_counts[daily_candidate_reason(previous, at, diaries)] += 1
        rows.append(ModelRow(feature_timestamp=at, target_timestamp=after,
            target_available_timestamp=label_available, previous_report_timestamp=before,
            features=features, target=int(next_tnss >= 6), dataset_mode=mode,
            feature_record_id=previous.id, target_record_id=target.id))
    return FeatureDataset(tuple(rows), max(0, len(selected) - 1), dict(exclusions), dict(daily_counts))


class ClassBalance(AnalysisModel):
    n: int
    positive: int
    negative: int
    positive_percent: float | None
    negative_percent: float | None


class Period(ClassBalance):
    target_start: datetime | None
    target_end: datetime | None
    feature_start: datetime | None
    feature_end: datetime | None


class ConfusionMatrix(AnalysisModel):
    true_negatives: int
    false_positives: int
    false_negatives: int
    true_positives: int


class Metrics(AnalysisModel):
    accuracy: float
    precision: float | None
    recall: float | None
    f1: float | None
    roc_auc: float | None
    unavailable_reasons: dict[str, str]
    confusion_matrix: ConfusionMatrix


class Coefficient(AnalysisModel):
    feature: str
    coefficient: float
    train_missing: int
    test_missing: int
    imputation_median: float
    scaler_mean: float
    scaler_scale: float


class ModelResponse(DatasetMetadata):
    dataset_mode: ModelMode
    status: Literal["ok", "insufficient_data", "unavailable"] = "insufficient_data"
    reasons: list[str] = Field(default_factory=list)
    target: Literal["next_observation_tnss_gte_6"] = "next_observation_tnss_gte_6"
    probability_threshold: float = 0.5
    minimum_rows: int = MINIMUM_ROWS
    split_method: Literal["chronological_80_20_no_shuffle"] = "chronological_80_20_no_shuffle"
    feature_timing: str = "Previous report, snapshot completion and any known server receipt strictly before next observation; UTC."
    daily_health_policy: str = "Previous prediction-day candidates excluded: no immutable daily edit history."
    model_row_count: int
    candidate_pair_count: int
    excluded_pair_counts: dict[str, int]
    daily_candidate_counts: dict[str, int]
    class_balance: ClassBalance
    training: Period
    testing: Period
    first_test_prediction_time: datetime | None
    horizon_hours: dict[str, float | None]
    feature_count: int = 0
    candidate_features: tuple[str, ...] = FEATURES
    used_features: list[str] = Field(default_factory=list)
    omitted_features: list[str] = Field(default_factory=list)
    feature_missing_counts: dict[str, int]
    metrics: Metrics | None = None
    baseline_class: int | None = None
    baseline_accuracy: float | None = None
    coefficients: list[Coefficient] = Field(default_factory=list)
    intercept: float | None = None


def balance(rows: Sequence[ModelRow]) -> ClassBalance:
    positives = sum(row.target for row in rows)
    n = len(rows)
    return ClassBalance(n=n, positive=positives, negative=n - positives,
        positive_percent=100 * positives / n if n else None,
        negative_percent=100 * (n - positives) / n if n else None)


def period(rows: Sequence[ModelRow]) -> Period:
    return Period(**balance(rows).model_dump(),
        target_start=rows[0].target_timestamp if rows else None,
        target_end=rows[-1].target_timestamp if rows else None,
        feature_start=rows[0].feature_timestamp if rows else None,
        feature_end=rows[-1].feature_timestamp if rows else None)


def temporal_split(rows: Sequence[ModelRow]) -> tuple[tuple[ModelRow, ...], tuple[ModelRow, ...]]:
    ordered = tuple(rows)
    if any(a.target_timestamp >= b.target_timestamp for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Model rows must be in strict chronological target order")
    if len({row.dataset_mode for row in ordered}) > 1:
        raise ValueError("Real and synthetic model rows must not be mixed")
    split = floor(len(ordered) * .8)
    return ordered[:split], ordered[split:]


def make_pipeline() -> Pipeline:
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()),
        ("model", LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=SEED))])


def fit_training_pipeline(training: Sequence[ModelRow]) -> tuple[Pipeline, list[str], np.ndarray]:
    # Only training availability chooses columns. An entirely missing column has no median.
    used = [name for name in FEATURES if any(finite_number(row.features[name]) is not None for row in training)]
    matrix = feature_matrix(training, used)
    pipeline = make_pipeline()
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        pipeline.fit(matrix, [row.target for row in training])
    return pipeline, used, matrix


def feature_matrix(rows: Sequence[ModelRow], names: Sequence[str]) -> np.ndarray:
    return np.array([[finite_number(row.features[name]) if finite_number(row.features[name]) is not None else np.nan
                      for name in names] for row in rows], dtype=float)


def evaluate_metrics(actual: Sequence[int], probabilities: Sequence[float]) -> Metrics:
    values, probability = np.asarray(actual), np.asarray(probabilities, dtype=float)
    if len(values) == 0 or len(values) != len(probability) or not np.isfinite(probability).all():
        raise ValueError("Invalid evaluation inputs")
    predicted = (probability >= .5).astype(int)
    tn, fp, fn, tp = (int(x) for x in confusion_matrix(values, predicted, labels=[0, 1]).ravel())
    reasons = {}
    def ratio(name, numerator, denominator, message):
        if denominator:
            return numerator / denominator
        reasons[name] = message
        return None
    precision = ratio("precision", tp, tp + fp, "No predicted high-symptom targets in the test set.")
    recall = ratio("recall", tp, tp + fn, "No actual high-symptom targets in the test set.")
    f1 = ratio("f1", 2 * tp, 2 * tp + fp + fn, "No actual or predicted high-symptom targets in the test set.")
    auc = float(roc_auc_score(values, probability)) if len(set(values)) == 2 else None
    if auc is None:
        reasons["roc_auc"] = "ROC-AUC requires both target classes in the temporal test set."
    return Metrics(accuracy=(tn + tp) / len(values), precision=precision, recall=recall, f1=f1,
        roc_auc=auc, unavailable_reasons=reasons,
        confusion_matrix=ConfusionMatrix(true_negatives=tn, false_positives=fp, false_negatives=fn, true_positives=tp))


def run_risk_model(records: Sequence[SymptomRecord], daily_records: Sequence[DailyHealthRecord],
                   mode: ModelMode = "real_only") -> ModelResponse:
    built = build_model_rows(records, daily_records, mode)
    rows = built.rows
    training, testing = temporal_split(rows)
    spans = [(r.target_timestamp - r.feature_timestamp).total_seconds() / 3600 for r in rows]
    result = ModelResponse(**prepare_dataset(records, mode).metadata.model_dump(),
        model_row_count=len(rows), candidate_pair_count=built.candidate_pairs,
        excluded_pair_counts=built.excluded_pairs, daily_candidate_counts=built.daily_candidates,
        class_balance=balance(rows), training=period(training), testing=period(testing),
        first_test_prediction_time=testing[0].feature_timestamp if testing else None,
        horizon_hours={"min": min(spans) if spans else None, "median": median(spans) if spans else None, "max": max(spans) if spans else None},
        feature_missing_counts={name: sum(finite_number(r.features[name]) is None for r in rows) for name in FEATURES})
    if len(rows) < MINIMUM_ROWS:
        result.reasons.append(f"At least {MINIMUM_ROWS} usable consecutive-observation pairs are required; found {len(rows)}.")
    if len(training) < 24 or len(testing) < 6:
        result.reasons.append("The fixed temporal split requires at least 24 training and 6 test pairs.")
    if min(result.class_balance.positive, result.class_balance.negative) < MINIMUM_TOTAL_CLASS:
        result.reasons.append("At least 5 high and 5 low targets are required overall.")
    if min(result.training.positive, result.training.negative) < MINIMUM_TRAIN_CLASS:
        result.reasons.append("Training needs both target classes, with at least 3 examples of each.")
    if testing and any(r.target_available_timestamp > testing[0].feature_timestamp for r in training):
        result.reasons.append("A training label was not available at the first test prediction time; temporal evaluation is not valid.")
    if result.reasons:
        return result
    try:
        pipeline, used, train_x = fit_training_pipeline(training)
        test_x = feature_matrix(testing, used)
        probabilities = pipeline.predict_proba(test_x)[:, 1]
        metrics = evaluate_metrics([r.target for r in testing], probabilities)
        coefficients = pipeline.named_steps["model"].coef_[0]
        if not np.isfinite(coefficients).all():
            raise ValueError("Non-finite coefficients")
    except (ConvergenceWarning, ValueError, FloatingPointError):
        result.status = "unavailable"
        result.reasons = ["The fixed model could not be fitted or evaluated reliably; no model results are displayed."]
        return result
    result.status = "ok"
    result.metrics = metrics
    result.feature_count = len(used)
    result.used_features = used
    result.omitted_features = [name for name in FEATURES if name not in used]
    result.baseline_class = int(result.training.positive > result.training.negative)
    result.baseline_accuracy = sum(r.target == result.baseline_class for r in testing) / len(testing)
    result.intercept = float(pipeline.named_steps["model"].intercept_[0])
    result.coefficients = [Coefficient(feature=name, coefficient=float(coefficients[i]),
        train_missing=int(np.isnan(train_x[:, i]).sum()), test_missing=int(np.isnan(test_x[:, i]).sum()),
        imputation_median=float(pipeline.named_steps["imputer"].statistics_[i]),
        scaler_mean=float(pipeline.named_steps["scaler"].mean_[i]), scaler_scale=float(pipeline.named_steps["scaler"].scale_[i]))
        for i, name in enumerate(used)]
    return result
