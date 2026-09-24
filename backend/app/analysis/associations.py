from collections.abc import Sequence

from scipy.stats import spearmanr

from .dataset import AnalysisDataset, NumericRow, finite_number
from .environment_timing import SOURCE_TIME, contemporaneous_times_eligible
from .schemas import (EXPOSURES, MINIMUM_PAIRS, AssociationResult, AssociationsResponse,
                      ContemporaneousAssociationResult, Exposure, PairStatistics)


def paired_spearman(rows: Sequence[NumericRow], variable: str) -> PairStatistics:
    pairs = [(outcome, exposure) for row in rows
             if (outcome := finite_number(row.get("tnss"))) is not None
             and (exposure := finite_number(row.get(variable))) is not None]
    result = PairStatistics(n=len(pairs), missing_pairs=len(rows) - len(pairs),
                               status="insufficient_data")
    if len(pairs) < MINIMUM_PAIRS:
        return result
    outcome, exposure = zip(*pairs)
    # Check both variables on the paired subset before SciPy can warn on constants.
    if len(set(outcome)) < 2 or len(set(exposure)) < 2:
        result.status = "insufficient_variation"
        return result
    statistic = spearmanr(outcome, exposure, alternative="two-sided", nan_policy="raise")
    rho, p_value = finite_number(statistic.statistic), finite_number(statistic.pvalue)
    if rho is None or p_value is None:
        result.status = "unavailable"
        return result
    result.status, result.spearman_rho, result.p_value = "ok", rho, p_value
    return result


def associate_variable(rows: Sequence[NumericRow], variable: Exposure) -> AssociationResult:
    return AssociationResult(variable=variable, **paired_spearman(rows, variable).model_dump())


def associate_dataset(dataset: AnalysisDataset) -> AssociationsResponse:
    # Numeric-only rows cannot establish alignment. Keep them for raw descriptive
    # summaries, but require the original timestamped records for relationships.
    if len(dataset.records) != dataset.metadata.record_count:
        raise ValueError("Environmental associations require timestamped source records")
    results = []
    for variable in EXPOSURES:
        eligible_rows, missing, excluded = [], 0, 0
        for record in dataset.records:
            outcome, exposure = finite_number(record.tnss), finite_number(getattr(record, variable))
            if outcome is None or exposure is None:
                missing += 1
            elif not contemporaneous_times_eligible(
                record.timestamp, getattr(record, SOURCE_TIME[variable]), record.environment_timestamp
            ):
                excluded += 1
            else:
                eligible_rows.append({"tnss": outcome, variable: exposure})
        statistics = paired_spearman(eligible_rows, variable)
        statistics.missing_pairs = missing
        results.append(ContemporaneousAssociationResult(
            variable=variable, temporally_excluded_pairs=excluded, **statistics.model_dump()))
    return AssociationsResponse(**dataset.metadata.model_dump(), associations=results)
