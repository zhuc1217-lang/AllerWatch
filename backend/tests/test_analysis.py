from datetime import UTC, datetime, timedelta
from math import sqrt
from types import SimpleNamespace
import warnings

import pytest
from sqlalchemy import select

from app.analysis.associations import associate_variable
from app.analysis.dataset import prepare_dataset
from app.analysis.descriptive import describe_variable
from app.analysis.schemas import EXPOSURES, VARIABLES
from app.models import SymptomRecord


def observation(index=0, synthetic=False, **changes):
    timestamp = datetime(2026, 9, 1, tzinfo=UTC) + timedelta(hours=index)
    values = dict(timestamp=timestamp,
                  weather_timestamp=timestamp, air_quality_timestamp=timestamp,
                  environment_timestamp=timestamp + timedelta(seconds=3),
                  nasal_congestion=index % 4, sneezing=1, runny_nose=2, nasal_itching=0,
                  eye_symptoms=3, overall_severity=5, medication_taken=False,
                  is_synthetic=synthetic, pm2_5=float(index), pm10=20.0,
                  china_aqi_estimate=None, relative_humidity=60.0, temperature_c=20.0)
    values.update(changes)
    return SymptomRecord(**values)


def test_complete_descriptive_statistics():
    result = describe_variable([{"tnss": n} for n in [0, 2, 4, 6]], "tnss")
    assert result.model_dump() == dict(n=4, missing=0, mean=3, median=3,
                                      std=pytest.approx(sqrt(20 / 3)), min=0, q1=1.5, q3=4.5, max=6)


def test_missing_and_nonfinite_excluded_but_zero_retained():
    values = [None, 0, 10, 20, float("nan"), float("inf"), -float("inf")]
    result = describe_variable([{"pm2_5": n} for n in values], "pm2_5")
    assert (result.n, result.missing) == (3, 4)
    assert (result.mean, result.median, result.std, result.min) == (10, 10, 10, 0)


@pytest.mark.parametrize("rows", [[], [{"pm2_5": None}], [{}, {}]])
def test_empty_or_all_missing_statistics(rows):
    result = describe_variable(rows, "pm2_5").model_dump()
    assert result.pop("n") == 0
    assert result.pop("missing") == len(rows)
    assert all(value is None for value in result.values())


def test_single_observation_has_no_sample_standard_deviation():
    result = describe_variable([{"tnss": 4}], "tnss")
    assert result.std is None
    assert result.mean == result.median == result.q1 == result.q3 == 4


@pytest.mark.parametrize("direction", [1, -1])
def test_known_perfect_rank_association(direction):
    rows = [{"tnss": i, "pm2_5": i if direction == 1 else 12 - i} for i in range(12)]
    result = associate_variable(rows, "pm2_5")
    assert result.status == "ok"
    assert result.n == 12 and result.missing_pairs == 0
    assert result.spearman_rho == pytest.approx(direction)
    assert result.p_value == pytest.approx(0, abs=1e-12)


def test_known_nonperfect_association_and_tied_ranks():
    # Repeating each ranked pair leaves rho unchanged, with average ranks for ties.
    rows = [{"tnss": x, "pm2_5": y} for x, y in zip([1, 2, 3, 4, 5], [5, 6, 7, 8, 7]) for _ in range(2)]
    result = associate_variable(rows, "pm2_5")
    assert result.spearman_rho == pytest.approx(0.8207826816681233)
    assert result.n == 10 and 0 < result.p_value < 1


@pytest.mark.parametrize("n", [0, 1, 6, 9])
def test_insufficient_paired_data(n):
    result = associate_variable([{"tnss": i, "pm2_5": i} for i in range(n)], "pm2_5")
    assert result.status == "insufficient_data" and result.n == n
    assert result.spearman_rho is None and result.p_value is None


@pytest.mark.parametrize("constant", ["tnss", "pm2_5"])
def test_constant_variable_is_handled_without_scipy_warning(constant):
    rows = [{"tnss": i, "pm2_5": i, constant: 5} for i in range(12)]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = associate_variable(rows, "pm2_5")
    assert result.status == "insufficient_variation"
    assert result.spearman_rho is None and result.p_value is None


def test_pairwise_deletion_is_specific_to_each_exposure():
    rows = [{"tnss": i, "pm2_5": i, "pm10": i} for i in range(10)]
    rows += [{"tnss": None, "pm2_5": 100, "pm10": 100},
             {"tnss": 10, "pm2_5": None, "pm10": 10},
             {"tnss": 11, "pm2_5": float("inf"), "pm10": 11}]
    pm25, pm10 = associate_variable(rows, "pm2_5"), associate_variable(rows, "pm10")
    assert (pm25.n, pm25.missing_pairs) == (10, 3)
    assert (pm10.n, pm10.missing_pairs) == (12, 1)
    assert pm25.spearman_rho == pytest.approx(1)
    assert pm10.spearman_rho == pytest.approx(1)


def test_threshold_uses_complete_pairs_not_total_records():
    rows = [{"tnss": i, "pm2_5": i} for i in range(9)] + [{"tnss": 3, "pm2_5": None}] * 20
    result = associate_variable(rows, "pm2_5")
    assert result.status == "insufficient_data"
    assert (result.n, result.missing_pairs) == (9, 20)


def test_variation_checked_after_pairwise_exclusion():
    rows = [{"tnss": i, "pm2_5": 4} for i in range(10)] + [{"tnss": None, "pm2_5": 50}]
    assert associate_variable(rows, "pm2_5").status == "insufficient_variation"


def test_unexpected_nonfinite_scipy_result_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.analysis.associations.spearmanr",
                        lambda *args, **kwargs: SimpleNamespace(statistic=float("nan"), pvalue=float("nan")))
    result = associate_variable([{"tnss": i, "pm2_5": i} for i in range(12)], "pm2_5")
    assert result.status == "unavailable"
    assert result.spearman_rho is None and result.p_value is None


@pytest.mark.parametrize("mode,real,synthetic", [("real_only", 2, 0), ("synthetic_only", 0, 3), ("all", 2, 3)])
def test_dataset_modes_and_existing_tnss_property(mode, real, synthetic):
    records = [observation(i, i >= 2) for i in range(5)]
    selected = prepare_dataset(records, mode)
    metadata = selected.metadata
    assert metadata.dataset_mode == mode
    assert (metadata.record_count, metadata.real_count, metadata.synthetic_count) == (real + synthetic, real, synthetic)
    assert metadata.includes_synthetic == bool(synthetic)
    assert len(selected.rows) == real + synthetic
    if synthetic:
        assert "synthetic" in metadata.data_notice
    for record in records:
        record.eye_symptoms = 0
    assert prepare_dataset(records, mode).rows == selected.rows
    assert all(row["tnss"] in [3, 4, 5, 6] for row in selected.rows)
    assert len(records) == 5  # Selection never mutates the source list.


@pytest.mark.parametrize("endpoint", ["descriptive", "associations"])
@pytest.mark.parametrize("mode,real,synthetic", [("real_only", 1, 0), ("synthetic_only", 0, 12), ("all", 1, 12)])
def test_api_filtering_metadata_counts_and_no_writes(client, endpoint, mode, real, synthetic):
    with client.app.state.session_factory() as session:
        session.add(observation(0, False, pm2_5=None, relative_humidity=None))
        session.add_all(observation(i + 1, True) for i in range(12))
        session.commit()
        before = [(r.id, r.timestamp, r.tnss, r.is_synthetic, r.pm2_5) for r in session.scalars(select(SymptomRecord))]
    response = client.get(f"/analysis/{endpoint}?dataset={mode}")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_mode"] == mode
    assert (data["record_count"], data["real_count"], data["synthetic_count"]) == (real + synthetic, real, synthetic)
    assert data["includes_synthetic"] == bool(synthetic)
    assert data["date_start"].endswith("Z") and data["date_end"].endswith("Z")
    assert data["observation_unit"] == "individual_observation"
    if endpoint == "descriptive":
        assert set(data["variables"]) == set(VARIABLES)
        assert data["variables"]["pm2_5"]["n"] == synthetic
        assert data["variables"]["pm2_5"]["missing"] == real
        assert data["variables"]["china_aqi_estimate"]["mean"] is None
        assert data["standard_deviation"] == "sample_ddof_1"
    else:
        assert data["minimum_pairs"] == 10
        assert [item["variable"] for item in data["associations"]] == list(EXPOSURES)
        item = data["associations"][0]
        assert (item["n"], item["missing_pairs"]) == (synthetic, real)
        assert item["status"] == ("ok" if synthetic else "insufficient_data")
    assert not any(invalid in response.text for invalid in ["NaN", "Infinity"])
    with client.app.state.session_factory() as session:
        after = [(r.id, r.timestamp, r.tnss, r.is_synthetic, r.pm2_5) for r in session.scalars(select(SymptomRecord))]
    assert before == after


@pytest.mark.parametrize("endpoint", ["descriptive", "associations"])
def test_safe_default_remains_empty_real_with_synthetic_present(client, endpoint):
    with client.app.state.session_factory() as session:
        session.add(observation(synthetic=True))
        session.commit()
    response = client.get(f"/analysis/{endpoint}")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_mode"] == "real_only" and data["record_count"] == 0
    assert data["synthetic_count"] == 0 and data["real_count"] == 0
    assert data["date_start"] is None and data["date_end"] is None
    assert data["includes_synthetic"] is False
    assert client.get(f"/analysis/{endpoint}?dataset=invalid").status_code == 422


def test_one_real_record_has_insufficient_states(client):
    with client.app.state.session_factory() as session:
        session.add(observation())
        session.commit()
    data = client.get("/analysis/associations").json()
    assert data["record_count"] == 1
    assert all(item["status"] == "insufficient_data" and item["spearman_rho"] is None and
               item["p_value"] is None for item in data["associations"])
