from collections.abc import Sequence

import numpy as np

from .dataset import AnalysisDataset, NumericRow, finite_number
from .schemas import VARIABLES, DescriptiveResponse, DescriptiveSummary, Variable


def describe_variable(rows: Sequence[NumericRow], variable: Variable) -> DescriptiveSummary:
    values = np.array([value for row in rows if (value := finite_number(row.get(variable))) is not None])
    n = len(values)
    if n == 0:
        return DescriptiveSummary(n=0, missing=len(rows))
    # Defensive overflow handling never emits NaN/Infinity into JSON.
    with np.errstate(over="ignore", invalid="ignore"):
        q1, median, q3 = np.percentile(values, [25, 50, 75], method="linear")
        return DescriptiveSummary(
            n=n, missing=len(rows) - n,
            mean=finite_number(np.mean(values)), median=finite_number(median),
            std=finite_number(np.std(values, ddof=1)) if n > 1 else None,
            min=finite_number(np.min(values)), q1=finite_number(q1),
            q3=finite_number(q3), max=finite_number(np.max(values)),
        )


def describe_dataset(dataset: AnalysisDataset) -> DescriptiveResponse:
    return DescriptiveResponse(**dataset.metadata.model_dump(), variables={
        variable: describe_variable(dataset.rows, variable) for variable in VARIABLES
    })
