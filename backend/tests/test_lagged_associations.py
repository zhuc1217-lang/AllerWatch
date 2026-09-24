from datetime import UTC, datetime, timedelta, timezone
import warnings

import pytest
from sqlalchemy import select

from app.analysis.dataset import prepare_dataset
from app.analysis.lagged_associations import LAGS, LAG_EXPOSURES, lagged_associations, match_exposure
from app.models import SymptomRecord

BASE = datetime(2026, 8, 1, 12, tzinfo=UTC)


def record(time=BASE, tnss=4, pm=10.0, synthetic=True, **changes):
    values = dict(timestamp=time, nasal_congestion=min(tnss, 3), sneezing=min(max(tnss - 3, 0), 3),
        runny_nose=min(max(tnss - 6, 0), 3), nasal_itching=min(max(tnss - 9, 0), 3),
        eye_symptoms=3, overall_severity=5, medication_taken=False, is_synthetic=synthetic,
        pm2_5=pm, us_aqi=pm, relative_humidity=pm,
        environment_timestamp=time, air_quality_timestamp=time, weather_timestamp=time,
        environment_latitude=51.5, environment_longitude=0.0)
    values.update(changes)
    return SymptomRecord(**values)


def result(records, variable="pm2_5", lag=6, mode="synthetic_only"):
    response = lagged_associations(prepare_dataset(records, mode))
    return next(item for item in response.results if item.variable == variable and item.lag_hours == lag)


def test_zero_lag_uses_own_time_checked_snapshot_only():
    own = record(pm=0, air_quality_timestamp=BASE - timedelta(minutes=15),
                 environment_timestamp=BASE + timedelta(seconds=3))
    other = record(pm=80)
    match = match_exposure(own, [other], "pm2_5", 0)
    assert match.source is own and match.value == 0 and match.actual_lag_hours == .25
    # Retrieval is distinct from valid time; later *valid* times are never accepted.
    own.air_quality_timestamp = BASE + timedelta(seconds=1)
    assert match_exposure(own, [other], "pm2_5", 0) is None
    own.air_quality_timestamp = BASE - timedelta(hours=4)
    assert match_exposure(own, [other], "pm2_5", 0) is None


@pytest.mark.parametrize("lag", [6, 12, 24])
def test_exact_target_and_nearest_eligible_prior(lag):
    own = record()
    target = BASE - timedelta(hours=lag)
    exact = record(target, pm=25)
    older = record(target - timedelta(hours=1), pm=5)
    future = record(target + timedelta(seconds=1), pm=90)
    assert match_exposure(own, [future, older, exact], "pm2_5", lag).source is exact
    match = match_exposure(own, [future, older], "pm2_5", lag)
    assert match.source is older and match.actual_lag_hours == lag + 1


@pytest.mark.parametrize("lag", [6, 12, 24])
def test_tolerance_boundary_and_distant_data(lag):
    own = record()
    edge = BASE - timedelta(hours=lag + 3)
    source = record(edge)
    assert match_exposure(own, [source], "pm2_5", lag) is not None
    too_old = record(edge - timedelta(microseconds=1))
    assert match_exposure(own, [too_old], "pm2_5", lag) is None
    assert match_exposure(own, [], "pm2_5", lag) is None


@pytest.mark.parametrize("field", ["timestamp", "environment_timestamp", "air_quality_timestamp"])
@pytest.mark.parametrize("after_target_hours", [0.01, 7])
def test_future_source_report_retrieval_or_valid_time_never_matches(field, after_target_hours):
    own = record()
    target = BASE - timedelta(hours=6)
    source = record(target - timedelta(minutes=5), **{field: target + timedelta(hours=after_target_hours)})
    assert match_exposure(own, [source], "pm2_5", 6) is None


def test_backward_only_even_when_future_match_would_be_closer():
    own = record()
    future = record(BASE - timedelta(hours=5, minutes=59), pm=100)
    prior = record(BASE - timedelta(hours=8), pm=20)
    assert match_exposure(own, [future, prior], "pm2_5", 6).value == 20


@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_missing_values_are_not_imputed(value):
    own = record()
    source = record(BASE - timedelta(hours=6), pm=value)
    assert match_exposure(own, [source], "pm2_5", 6) is None
    assert result([own, source]).n == 0


def test_missing_nearest_variable_may_use_older_finite_same_variable_within_window():
    own = record()
    nearest = record(BASE - timedelta(hours=6), pm=None, relative_humidity=60)
    older = record(BASE - timedelta(hours=7), pm=0, relative_humidity=40)
    assert match_exposure(own, [nearest, older], "pm2_5", 6).value == 0
    assert match_exposure(own, [nearest, older], "relative_humidity", 6).value == 60


@pytest.mark.parametrize("field", ["air_quality_timestamp", "environment_timestamp"])
def test_missing_timestamp_has_no_symptom_time_fallback(field):
    source = record(BASE - timedelta(hours=6), **{field: None})
    assert match_exposure(record(), [source], "pm2_5", 6) is None


def test_humidity_uses_weather_time_not_air_quality_time():
    source = record(BASE - timedelta(hours=7), weather_timestamp=BASE - timedelta(hours=10))
    assert match_exposure(record(), [source], "pm2_5", 6) is not None
    assert match_exposure(record(), [source], "relative_humidity", 6) is None


def test_inconsistent_source_time_after_retrieval_is_rejected():
    source = record(BASE - timedelta(hours=7), air_quality_timestamp=BASE - timedelta(hours=6))
    assert match_exposure(record(), [source], "pm2_5", 6) is None


def test_offsets_normalized_to_utc():
    shanghai = timezone(timedelta(hours=8))
    source = record((BASE - timedelta(hours=6)).astimezone(shanghai))
    match = match_exposure(record(), [source], "pm2_5", 6)
    assert match.actual_lag_hours == 6 and match.valid_time.tzinfo is UTC


@pytest.mark.parametrize("field", ["timestamp", "environment_timestamp", "air_quality_timestamp"])
def test_naive_timestamps_rejected_explicitly(field):
    source = record(BASE - timedelta(hours=6), **{field: (BASE - timedelta(hours=6)).replace(tzinfo=None)})
    with pytest.raises(ValueError, match="timezone-aware"):
        match_exposure(record(), [source], "pm2_5", 6)


def test_ties_use_latest_retrieval_then_id_and_ignore_input_order():
    time = BASE - timedelta(hours=7)
    first = record(time, pm=10, id=1)
    second = record(time, pm=20, id=2, environment_timestamp=time + timedelta(minutes=1))
    third = record(time, pm=30, id=3, environment_timestamp=time + timedelta(minutes=1))
    for records in ([first, second, third], [third, first, second]):
        assert match_exposure(record(), records, "pm2_5", 6).source is third


def controlled_records(direction=1, constant=False, count=12):
    records = []
    for i in range(count):
        time = BASE + timedelta(days=3 * i)
        exposure = 20 if constant else (i if direction == 1 else 12 - i)
        records += [record(time - timedelta(hours=6), tnss=0, pm=exposure), record(time, tnss=i, pm=None)]
    return records


@pytest.mark.parametrize("direction", [1, -1])
def test_known_positive_and_negative_lagged_association(direction):
    item = result(controlled_records(direction))
    assert item.n == 12 and item.missing_pairs == 12 and item.synthetic_pairs == 12 and item.real_pairs == 0
    assert item.status == "ok" and item.spearman_rho == pytest.approx(direction)
    assert item.actual_lag_hours_min == item.actual_lag_hours_median == item.actual_lag_hours_max == 6
    assert item.distinct_source_records == 12


def test_minimum_and_constant_states():
    assert result(controlled_records(count=9)).status == "insufficient_data"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        item = result(controlled_records(constant=True))
    assert item.status == "insufficient_variation" and item.p_value is None and item.spearman_rho is None


def test_empty_returns_all_12_unavailable_results():
    data = lagged_associations(prepare_dataset([], "real_only"))
    assert len(data.results) == 12
    assert all(item.n == item.missing_pairs == 0 and item.status == "insufficient_data" for item in data.results)


def test_one_source_can_be_reused_but_is_not_counted_as_independent_sources():
    source = record(BASE - timedelta(hours=6), pm=10)
    outcomes = [record(BASE + timedelta(hours=i), pm=None) for i in range(3)]
    item = result([source, *outcomes])
    assert item.n == 3 and item.distinct_source_records == 1
    assert (item.actual_lag_hours_min, item.actual_lag_hours_max) == (6, 8)


def test_cross_provenance_and_changed_or_unknown_real_location_never_match():
    own = record(synthetic=False)
    source = record(BASE - timedelta(hours=6), synthetic=True)
    assert match_exposure(own, [source], "pm2_5", 6) is None
    source.is_synthetic = False
    source.environment_latitude = 52.0
    assert match_exposure(own, [source], "pm2_5", 6) is None
    source.environment_latitude = own.environment_latitude = None
    source.environment_longitude = own.environment_longitude = None
    assert match_exposure(own, [source], "pm2_5", 6) is None
    source.is_synthetic = own.is_synthetic = True
    assert match_exposure(own, [source], "pm2_5", 6) is not None


@pytest.mark.parametrize("mode,real,synthetic,n", [("real_only", 2, 0, 1), ("synthetic_only", 0, 2, 1), ("all", 2, 2, 2)])
def test_dataset_filtering_and_pair_provenance(mode, real, synthetic, n):
    records = [record(BASE, synthetic=False), record(BASE + timedelta(hours=6), synthetic=False, pm=None),
               record(BASE, synthetic=True), record(BASE + timedelta(hours=6), synthetic=True, pm=None)]
    data = lagged_associations(prepare_dataset(records, mode))
    item = next(item for item in data.results if item.variable == "pm2_5" and item.lag_hours == 6)
    assert (data.real_count, data.synthetic_count, data.record_count) == (real, synthetic, real + synthetic)
    assert (item.n, item.real_pairs, item.synthetic_pairs) == (n, real // 2, synthetic // 2)
    assert item.missing_pairs == n


def test_all_mode_does_not_borrow_synthetic_history_for_real_outcome():
    records = [record(BASE, synthetic=True), record(BASE + timedelta(hours=6), synthetic=False, pm=None)]
    assert result(records, mode="all").n == 0


@pytest.mark.parametrize("mode,expected", [("real_only", 1), ("synthetic_only", 24), ("all", 25)])
def test_endpoint_metadata_counts_finite_json_and_read_only(client, mode, expected):
    with client.app.state.session_factory() as session:
        session.add_all([record(synthetic=False, pm=None), *controlled_records()])
        session.commit()
        before = [(r.id, r.timestamp, r.tnss, r.pm2_5, r.is_synthetic) for r in session.scalars(select(SymptomRecord))]
    response = client.get(f"/analysis/lagged-associations?dataset={mode}")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_mode"] == mode and data["record_count"] == expected
    assert data["lags_hours"] == [0, 6, 12, 24] and data["minimum_pairs"] == 10
    assert data["matching"]["approximate"] and data["matching"]["timezone"] == "UTC"
    assert len(data["results"]) == 12
    assert {(x["variable"], x["lag_hours"]) for x in data["results"]} == {(v, h) for v in LAG_EXPOSURES for h in LAGS}
    assert all(x["n"] + x["missing_pairs"] == expected and x["real_pairs"] + x["synthetic_pairs"] == x["n"] for x in data["results"])
    assert "NaN" not in response.text and "Infinity" not in response.text
    with client.app.state.session_factory() as session:
        after = [(r.id, r.timestamp, r.tnss, r.pm2_5, r.is_synthetic) for r in session.scalars(select(SymptomRecord))]
    assert before == after


def test_endpoint_default_and_invalid_mode(client):
    data = client.get("/analysis/lagged-associations").json()
    assert data["dataset_mode"] == "real_only" and data["record_count"] == 0
    assert client.get("/analysis/lagged-associations?dataset=invalid").status_code == 422
