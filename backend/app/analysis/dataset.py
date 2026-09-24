from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real

from ..models import SymptomRecord
from .schemas import VARIABLES, DatasetMetadata, DatasetMode

NumericRow = Mapping[str, float | int | None]


def finite_number(value: object) -> float | None:
    """Treat invalid/non-finite values as missing, while preserving measured zero."""
    if isinstance(value, Real) and not isinstance(value, bool) and isfinite(value):
        return float(value)
    return None


@dataclass(frozen=True)
class AnalysisDataset:
    metadata: DatasetMetadata
    rows: Sequence[NumericRow]
    records: Sequence[SymptomRecord] = ()


def prepare_dataset(records: Sequence[SymptomRecord], mode: DatasetMode) -> AnalysisDataset:
    if mode not in ("real_only", "synthetic_only", "all"):
        raise ValueError("Unknown dataset mode")
    selected = [record for record in records if mode == "all" or
                record.is_synthetic == (mode == "synthetic_only")]
    synthetic = sum(record.is_synthetic for record in selected)
    timestamps = [record.timestamp for record in selected]
    notice = "Real observations only."
    if mode == "synthetic_only":
        notice = "Development dataset: synthetic observations. These are not real patient observations."
    elif synthetic:
        notice = "Includes synthetic development data. Synthetic observations are not real patient observations."
    metadata = DatasetMetadata(
        dataset_mode=mode, record_count=len(selected), real_count=len(selected) - synthetic,
        synthetic_count=synthetic, includes_synthetic=synthetic > 0, data_notice=notice,
        date_start=min(timestamps, default=None), date_end=max(timestamps, default=None),
    )
    # The model property is the sole TNSS definition; never re-sum symptom scores here.
    rows = [{variable: finite_number(getattr(record, variable)) for variable in VARIABLES}
            for record in selected]
    return AnalysisDataset(metadata, rows, tuple(selected))
