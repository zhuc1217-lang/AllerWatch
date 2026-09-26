"""C1: preserve raw snapshots, exclude incompatible contemporaneous pairs."""
from datetime import UTC, datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.analysis.associations import associate_dataset
from app.analysis.dataset import prepare_dataset
from app.analysis.descriptive import describe_dataset
from app.analysis.environment_timing import SOURCE_TIME, contemporaneous_times_eligible
from app.analysis.lagged_associations import LAG_EXPOSURES, lagged_associations, match_exposure
from app.analysis.schemas import EXPOSURES
from app.models import SymptomRecord
from app.schemas import SymptomRecordRead
from app.services.environment_service import get_environment_service

T = datetime(2026, 9, 1, 12, tzinfo=UTC)


def observation(index=0, **changes):
    time = T + timedelta(hours=index)
    values = dict(id=index + 1, timestamp=time, nasal_congestion=index % 4,
                  sneezing=(index // 4) % 4, runny_nose=1, nasal_itching=1,
                  eye_symptoms=3, overall_severity=5, medication_taken=False,
                  notes=None, is_synthetic=True, pm2_5=float(index), pm10=float(index * 2),
                  china_aqi_estimate=float(index * 3), relative_humidity=50.0 + index, temperature_c=10.0 + index,
                  weather_timestamp=time, air_quality_timestamp=time,
                  environment_timestamp=time + timedelta(seconds=3))
    values.update(changes)
    return SymptomRecord(**values)


@pytest.mark.parametrize("source,retrieved,expected", [
    (T, T, True),
    (T, T + timedelta(seconds=3), True),  # Retrieval after validation is allowed.
    (T - timedelta(hours=3), T, True),
    (T - timedelta(hours=3, microseconds=1), T, False),
    (T + timedelta(microseconds=1), T + timedelta(seconds=3), False),
    (T + timedelta(days=30), T + timedelta(days=30, seconds=3), False),
    (None, T, False),
    (T, None, False),
    (T, T - timedelta(microseconds=1), False),
])
def test_contemporaneous_boundaries_missing_metadata_and_retrieval_consistency(source, retrieved, expected):
    assert contemporaneous_times_eligible(T, source, retrieved) is expected


def test_offsets_are_compared_as_utc_instants():
    assert contemporaneous_times_eligible(
        T.astimezone(timezone(timedelta(hours=8))),
        (T - timedelta(hours=3)).astimezone(timezone(timedelta(hours=-4))), T)
    assert not contemporaneous_times_eligible(None, T, T)


@pytest.mark.parametrize("field", [0, 1, 2])
def test_naive_timestamps_are_not_silently_interpreted(field):
    times = [T, T, T]
    times[field] = T.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        contemporaneous_times_eligible(*times)


@pytest.mark.parametrize("variable", EXPOSURES)
@pytest.mark.parametrize("reason", ["future", "stale", "missing_source", "missing_retrieval", "inconsistent"])
def test_all_exposures_use_shared_time_gate_and_missing_count_precedence(variable, reason):
    changes = {
        "future": {SOURCE_TIME[variable]: T + timedelta(days=30), "environment_timestamp": T + timedelta(days=30, seconds=3)},
        "stale": {SOURCE_TIME[variable]: T - timedelta(hours=4)},
        "missing_source": {SOURCE_TIME[variable]: None},
        "missing_retrieval": {"environment_timestamp": None},
        "inconsistent": {"environment_timestamp": T - timedelta(seconds=1)},
    }[reason]
    rejected = observation(**changes)
    missing = observation(**{**changes, variable: None})
    zero = observation(**{variable: 0})
    result = associate_dataset(prepare_dataset([rejected, missing, zero], "synthetic_only"))
    item = next(item for item in result.associations if item.variable == variable)
    assert (item.n, item.temporally_excluded_pairs, item.missing_pairs) == (1, 1, 1)
    assert result.record_count == item.n + item.missing_pairs + item.temporally_excluded_pairs
    assert result.temporal_tolerance_hours == 3
    assert SymptomRecordRead.model_validate(rejected).environment_time_eligible[variable] is False
    assert SymptomRecordRead.model_validate(zero).environment_time_eligible[variable] is True
    if variable in LAG_EXPOSURES:
        assert match_exposure(rejected, [zero], variable, 0) is None  # No substitute.


def test_provider_eligibility_is_independent_and_raw_descriptive_data_remain_available():
    record = observation(air_quality_timestamp=T + timedelta(hours=1))
    dataset = prepare_dataset([record], "synthetic_only")
    results = {item.variable: item for item in associate_dataset(dataset).associations}
    flags = SymptomRecordRead.model_validate(record).environment_time_eligible
    for variable in EXPOSURES:
        expected = variable in ("temperature_c", "relative_humidity")
        assert flags[variable] is expected
        assert results[variable].n == int(expected)
        assert results[variable].temporally_excluded_pairs == int(not expected)
    assert describe_dataset(dataset).variables["pm2_5"].n == 1
    assert describe_dataset(dataset).variables["pm2_5"].mean == 0


@pytest.mark.parametrize("mode,expected", [("real_only", (1, 0)), ("synthetic_only", (0, 1)), ("all", (1, 1))])
def test_modes_partition_aligned_and_excluded_without_cross_matching(mode, expected):
    records = [observation(is_synthetic=False), observation(1, air_quality_timestamp=T + timedelta(days=30))]
    data = associate_dataset(prepare_dataset(records, mode))
    item = data.associations[0]
    assert (item.n, item.temporally_excluded_pairs) == expected
    assert item.missing_pairs == 0
    assert (data.real_count, data.synthetic_count) == expected


def test_aligned_spearman_matches_lag_zero_and_original_numerical_values():
    records = [observation(i) for i in range(12)]
    # Monotone TNSS 0..11, preserving the authoritative four-nasal-score property.
    for i, record in enumerate(records):
        record.nasal_congestion = min(i, 3)
        record.sneezing = min(max(i - 3, 0), 3)
        record.runny_nose = min(max(i - 6, 0), 3)
        record.nasal_itching = max(i - 9, 0)
    dataset = prepare_dataset(records, "synthetic_only")
    ordinary = associate_dataset(dataset)
    for item in ordinary.associations:
        assert (item.n, item.missing_pairs, item.temporally_excluded_pairs) == (12, 0, 0)
        assert item.spearman_rho == pytest.approx(1)
        assert item.p_value == pytest.approx(0, abs=1e-12)
    lag_zero = [item for item in lagged_associations(dataset).results if item.lag_hours == 0]
    for item in lag_zero:
        same = next(result for result in ordinary.associations if result.variable == item.variable)
        assert (item.n, item.spearman_rho, item.p_value) == (same.n, same.spearman_rho, same.p_value)


def test_audit_backdated_submission_regression_preserves_every_raw_column(client, valid_record):
    """Exercise real POST enrichment, GET, analysis and lag-0 on an isolated DB."""
    class CurrentService:
        index = 0

        async def get_current(self):
            index = self.index
            self.index += 1
            return SimpleNamespace(temperature_c=10 + index, relative_humidity=50 + index, pm2_5=index,
                pm10=index * 2, china_aqi_estimate=index * 3, timestamp=T + timedelta(days=30, seconds=3),
                weather_timestamp=T + timedelta(days=30), air_quality_timestamp=T + timedelta(days=30),
                latitude=51.5, longitude=-0.12, nitrogen_dioxide=20, sulfur_dioxide=10,
                carbon_monoxide=600, ozone=64, china_aqi_primary_pollutant=None)
    service = CurrentService()
    client.app.dependency_overrides[get_environment_service] = lambda: service
    saved = []
    for i in range(12):
        response = client.post("/symptoms", json={**valid_record, "timestamp": (T + timedelta(hours=i)).isoformat(),
            "nasal_congestion": min(i, 3), "sneezing": min(max(i - 3, 0), 3),
            "runny_nose": min(max(i - 6, 0), 3), "nasal_itching": max(i - 9, 0)})
        assert response.status_code == 201
        saved.append(response.json())

    def raw_rows():
        with client.app.state.session_factory() as session:
            return list(session.execute(select(*SymptomRecord.__table__.columns).order_by(SymptomRecord.id)))

    before = raw_rows()
    assert [record["pm2_5"] for record in saved] == list(range(12))
    assert [record["tnss"] for record in saved] == list(range(12))
    assert all(not any(record["environment_time_eligible"].values()) for record in saved)
    assert client.get(f"/symptoms/{saved[0]['id']}").json() == saved[0]
    assert client.get("/symptoms").json() == list(reversed(saved))
    data = client.get("/analysis/associations?dataset=synthetic_only").json()
    assert data["record_count"] == 12
    for item in data["associations"]:
        assert (item["n"], item["temporally_excluded_pairs"], item["missing_pairs"]) == (0, 12, 0)
        assert item["status"] == "insufficient_data"
        assert item["spearman_rho"] is None and item["p_value"] is None
    lagged = client.get("/analysis/lagged-associations?dataset=synthetic_only").json()
    for item in lagged["results"]:
        if item["lag_hours"] == 0:
            assert (item["n"], item["missing_pairs"]) == (0, 12)
    assert client.get("/analysis/descriptive?dataset=synthetic_only").json()["variables"]["pm2_5"]["n"] == 12
    assert before == raw_rows()
    assert client.get("/symptoms").json() == list(reversed(saved))


def test_dashboard_api_fixtures_agree_with_backend_ordinary_and_lag_zero_eligibility():
    fixtures = Path(__file__).resolve().parents[2] / "frontend/tests/fixtures/contemporaneous-records.json"
    records = []
    for fixture in json.loads(fixtures.read_text(encoding="utf-8")):
        # Recompute output-only flags from raw fields, never trust fixture flags as input.
        response = SymptomRecordRead.model_validate({
            key: value for key, value in fixture.items() if key != "environment_time_eligible"})
        assert response.environment_time_eligible == fixture["environment_time_eligible"]
        record = SymptomRecord(**response.model_dump(exclude={"tnss", "environment_time_eligible"}))
        records.append(record)
        for variable in LAG_EXPOSURES:
            match = match_exposure(record, records, variable, 0)
            assert (match is not None) == (response.environment_time_eligible[variable] and getattr(record, variable) is not None)
    results = associate_dataset(prepare_dataset(records, "synthetic_only"))
    for item in results.associations:
        n = 3 if item.variable in ("relative_humidity", "temperature_c") else 2
        assert (item.n, item.temporally_excluded_pairs, item.missing_pairs) == (n, 8 - n, 1)


def test_caller_cannot_supply_analytic_eligibility(client, valid_record):
    response = client.post("/symptoms", json={**valid_record,
        "environment_time_eligible": {variable: True for variable in EXPOSURES}})
    assert response.status_code == 422
    assert client.get("/symptoms").json() == []
