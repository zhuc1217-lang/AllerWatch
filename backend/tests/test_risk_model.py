from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
import json
import warnings

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning

from app.analysis import risk_model as risk
from app.daily_health import DailyHealthRecord
from app.models import SymptomRecord


def records(n=51, synthetic=True):
    result = []
    for i in range(n):
        stamp = datetime(2026, 1, 1, 8, tzinfo=UTC) + timedelta(hours=12 * i)
        score = i % 13
        result.append(SymptomRecord(id=i + 1, timestamp=stamp,
            nasal_congestion=min(score, 3), sneezing=min(max(score - 3, 0), 3),
            runny_nose=min(max(score - 6, 0), 3), nasal_itching=max(score - 9, 0),
            eye_symptoms=3, overall_severity=i % 11, medication_taken=True, is_synthetic=synthetic,
            temperature_c=18 + i % 6, relative_humidity=40 + i % 30,
            pm2_5=10 + i, pm10=20 + 2 * i, china_aqi_estimate=40 + i,
            environment_timestamp=stamp + timedelta(seconds=3),
            weather_timestamp=stamp - timedelta(minutes=15), air_quality_timestamp=stamp - timedelta(hours=1)))
    return result


def diary(day=date(2025, 12, 31), created=datetime(2025, 12, 31, 16, tzinfo=UTC), synthetic=True):
    return DailyHealthRecord(date=day, created_at=created, is_synthetic=synthetic,
        sleep_duration_hours=7.5, sleep_quality=4, stress_level=3, exercise_minutes=35)


def rows(n=51):
    return risk.build_model_rows(records(n), [], 'synthetic_only').rows


def test_target_boundary_and_no_target_or_eye_scores_in_features():
    data = records(14)
    built = risk.build_model_rows(data, [], 'synthetic_only')
    assert [r.target for r in built.rows] == [0] * 5 + [1] * 7 + [0]
    assert built.rows[5].features['previous_tnss'] == 5
    assert built.rows[5].target == 1
    assert set(built.rows[0].features) == set(risk.FEATURES)
    assert 'tnss' not in built.rows[0].features and 'medication_taken' not in built.rows[0].features


def test_ordering_is_chronological_not_input_order_and_all_predictors_precede_target():
    data = records()
    built = risk.build_model_rows(list(reversed(data)), [], 'synthetic_only')
    assert built == risk.build_model_rows(data, [], 'synthetic_only')
    assert [r.target_record_id for r in built.rows] == list(range(2, 52))
    for previous, target, row in zip(data, data[1:], built.rows):
        assert row.previous_report_timestamp == previous.timestamp
        assert row.feature_timestamp == previous.environment_timestamp < target.timestamp == row.target_timestamp
        assert row.features['pm2_5'] == previous.pm2_5
        assert row.target_available_timestamp == target.environment_timestamp


@pytest.mark.parametrize('offset', [0, 1])
def test_future_or_equal_retrieval_excludes_pair_without_skipping_to_a_later_target(offset):
    data = records(4)
    data[0].environment_timestamp = data[1].timestamp + timedelta(seconds=offset)
    built = risk.build_model_rows(data, [], 'synthetic_only')
    assert built.excluded_pairs == {'predictors_not_before_target': 1}
    assert [(r.feature_record_id, r.target_record_id) for r in built.rows] == [(2, 3), (3, 4)]


def test_equal_report_times_are_ambiguous_and_never_repaired_with_arbitrary_id_order():
    data = records(5)
    data[2].timestamp = data[1].timestamp
    built = risk.build_model_rows(data, [], 'synthetic_only')
    assert built.excluded_pairs == {'ambiguous_equal_timestamps': 3}
    assert [(r.feature_record_id, r.target_record_id) for r in built.rows] == [(4, 5)]


def test_explicit_model_row_validation_rejects_time_leakage_and_target_feature():
    row = rows(2)[0]
    with pytest.raises(ValueError, match='precede'): replace(row, feature_timestamp=row.target_timestamp)
    with pytest.raises(ValueError, match='feature/target'): replace(row, features=row.features | {'tnss': 6})
    with pytest.raises(ValueError, match='timezone-aware'): replace(row, target_timestamp=row.target_timestamp.replace(tzinfo=None))
    with pytest.raises(ValueError, match='Mixed'): replace(row, dataset_mode='all')


@pytest.mark.parametrize('field', ['weather_timestamp', 'air_quality_timestamp'])
def test_future_source_valid_times_are_missing_even_if_downloaded_before_target(field):
    data = records(2)
    setattr(data[0], field, data[0].timestamp + timedelta(seconds=1))
    features = risk.build_model_rows(data, [], 'synthetic_only').rows[0].features
    fields = ('pm2_5', 'pm10', 'china_aqi_estimate') if field == 'air_quality_timestamp' else ('temperature_c', 'relative_humidity')
    assert all(features[name] is None for name in fields)


def test_stale_unknown_or_nonfinite_environment_is_missing_and_zero_is_retained():
    data = records(3)
    data[0].pm2_5 = 0
    data[0].pm10 = float('inf')
    data[0].weather_timestamp = None
    data[1].air_quality_timestamp = data[1].timestamp - timedelta(hours=3, seconds=1)
    built = risk.build_model_rows(data, [], 'synthetic_only')
    assert built.rows[0].features['pm2_5'] == 0
    assert built.rows[0].features['pm10'] is None
    assert built.rows[0].features['relative_humidity'] is None
    assert built.rows[1].features['pm2_5'] is None


def test_target_environment_never_changes_its_own_predictors():
    data = records(2)
    original = risk.build_model_rows(data, [], 'synthetic_only').rows[0].features
    for field in risk.ENVIRONMENT: setattr(data[1], field, 999999)
    assert risk.build_model_rows(data, [], 'synthetic_only').rows[0].features == original


def test_daily_health_rejects_late_creation_and_unversioned_past_creation():
    data = records(2)
    late = diary(created=data[1].timestamp + timedelta(days=1))
    built = risk.build_model_rows(data, [late], 'synthetic_only')
    assert built.daily_candidates == {'created_after_prediction': 1}
    assert all(built.rows[0].features[name] is None for name in risk.DAILY_FEATURES)
    past = diary()
    built = risk.build_model_rows(data, [past], 'synthetic_only')
    assert built.daily_candidates == {'unversioned_daily_record': 1}
    assert all(built.rows[0].features[name] is None for name in risk.DAILY_FEATURES)


def test_daily_health_uses_previous_prediction_day_not_future_target_day_or_other_type():
    data = records(2)
    data[1].timestamp += timedelta(days=3)
    data[1].environment_timestamp = data[1].timestamp + timedelta(seconds=3)
    for wrong in [diary(day=date(2026, 1, 3)), diary(synthetic=False)]:
        built = risk.build_model_rows(data, [wrong], 'synthetic_only')
        assert built.daily_candidates == {'no_previous_day_record': 1}
        assert all(built.rows[0].features[name] is None for name in risk.DAILY_FEATURES)


def test_synthetic_outage_fallback_is_not_assumed_for_unknown_real_availability():
    for flag, mode in [(False, 'real_only'), (True, 'synthetic_only')]:
        data = records(2, flag)
        data[0].environment_timestamp = None
        built = risk.build_model_rows(data, [], mode)
        if flag:
            assert len(built.rows) == 1 and all(built.rows[0].features[name] is None for name in risk.ENVIRONMENT)
        else:
            assert not built.rows and built.excluded_pairs == {'unknown_real_report_availability': 1}


def test_timezone_offsets_represent_same_instant():
    data = records(3)
    expected = risk.build_model_rows(data, [], 'synthetic_only')
    for item in data:
        for field in ['timestamp', 'environment_timestamp', 'weather_timestamp', 'air_quality_timestamp']:
            setattr(item, field, getattr(item, field).astimezone(timezone(timedelta(hours=-7))))
    assert risk.build_model_rows(data, [], 'synthetic_only') == expected


def test_split_is_first_eighty_percent_without_shuffle_and_rejects_unsorted_or_mixed_rows():
    original = rows()
    train, test = risk.temporal_split(original)
    assert train == original[:40] and test == original[40:]
    assert train[-1].target_timestamp < test[0].target_timestamp
    assert max(row.target_available_timestamp for row in train) <= test[0].feature_timestamp
    with pytest.raises(ValueError, match='chronological'): risk.temporal_split(list(reversed(original)))
    with pytest.raises(ValueError, match='mixed'): risk.temporal_split([replace(original[0], dataset_mode='real_only'), *original[1:]])


def test_training_only_imputation_scaling_and_all_missing_column_removal():
    original = list(rows())
    train, test = risk.temporal_split(original)
    training = [replace(r, features=r.features | {'pm2_5': None if i % 3 == 0 else float(i), 'pm10': None}) for i, r in enumerate(train)]
    pipeline, names, x = risk.fit_training_pipeline(training)
    assert 'pm10' not in names
    assert all(name not in names for name in risk.DAILY_FEATURES)
    expected = np.nanmedian(x, axis=0)
    np.testing.assert_allclose(pipeline.named_steps['imputer'].statistics_, expected)
    completed = np.where(np.isnan(x), expected, x)
    np.testing.assert_allclose(pipeline.named_steps['scaler'].mean_, completed.mean(axis=0))
    means = pipeline.named_steps['scaler'].mean_.copy()
    extremes = [replace(r, features=r.features | {'pm2_5': 1e9, 'pm10': 1e9}) for r in test]
    pipeline.predict_proba(risk.feature_matrix(extremes, names))
    np.testing.assert_array_equal(pipeline.named_steps['scaler'].mean_, means)
    np.testing.assert_array_equal(pipeline.named_steps['imputer'].statistics_, expected)


@pytest.mark.parametrize('mode', ['real_only', 'synthetic_only'])
def test_modes_filter_before_building_pairs_and_never_mix(mode):
    real, fake = records(synthetic=False), records(synthetic=True)
    for r in real: r.id += 1000
    built = risk.build_model_rows([*real, *fake], [], mode)
    assert len(built.rows) == 50
    assert all(r.dataset_mode == mode for r in built.rows)
    assert all((r.feature_record_id > 1000) == (mode == 'real_only') for r in built.rows)
    result = risk.run_risk_model([*real, *fake], [], mode)
    assert result.status == 'ok'
    assert (result.real_count, result.synthetic_count) == ((51, 0) if mode == 'real_only' else (0, 51))


@pytest.mark.parametrize('n', [0, 1, 15, 30])
def test_insufficient_rows_do_not_fit(n, monkeypatch):
    def forbidden(*args): raise AssertionError('Must not train')
    monkeypatch.setattr(risk, 'fit_training_pipeline', forbidden)
    result = risk.run_risk_model(records(n), [], 'synthetic_only')
    assert result.status == 'insufficient_data' and result.metrics is None and not result.coefficients
    assert result.reasons


def test_single_class_training_does_not_train():
    data = records()
    for item in data[:41]:
        item.nasal_congestion = item.sneezing = item.runny_nose = item.nasal_itching = 0
    result = risk.run_risk_model(data, [], 'synthetic_only')
    assert result.status == 'insufficient_data' and result.training.positive == 0
    assert any('both target classes' in reason for reason in result.reasons)


def test_single_class_testing_has_no_auc_but_other_valid_metrics():
    data = records()
    for item in data[41:]:
        item.nasal_congestion = item.sneezing = item.runny_nose = item.nasal_itching = 0
    result = risk.run_risk_model(data, [], 'synthetic_only')
    assert result.status == 'ok' and result.testing.positive == 0
    assert result.metrics.roc_auc is None and result.metrics.recall is None
    assert 'both target classes' in result.metrics.unavailable_reasons['roc_auc']
    assert result.metrics.accuracy is not None


def test_confusion_matrix_metrics_probability_threshold_and_undefined_denominators():
    m = risk.evaluate_metrics([0, 0, 1, 1], [.1, .8, .7, .2])
    assert m.confusion_matrix.model_dump() == dict(true_negatives=1, false_positives=1, false_negatives=1, true_positives=1)
    assert m.accuracy == m.precision == m.recall == m.f1 == .5
    assert m.roc_auc == .5
    undefined = risk.evaluate_metrics([0, 0], [.1, .2])
    assert undefined.precision is None and undefined.recall is None and undefined.f1 is None
    assert undefined.accuracy == 1 and undefined.roc_auc is None
    assert risk.evaluate_metrics([0, 1], [.2, .5]).confusion_matrix.true_positives == 1


def test_coefficients_reproducibility_and_majority_baseline():
    data = records()
    first = risk.run_risk_model(data, [], 'synthetic_only')
    second = risk.run_risk_model(list(reversed(data)), [], 'synthetic_only')
    assert first.model_dump() == second.model_dump() and first.status == 'ok'
    assert first.feature_count == 7 and len(first.coefficients) == 7
    assert first.omitted_features == list(risk.DAILY_FEATURES)
    assert all(np.isfinite(c.coefficient) and c.scaler_scale > 0 for c in first.coefficients)
    assert first.baseline_class == int(first.training.positive > first.training.negative)
    expected = first.testing.positive if first.baseline_class else first.testing.negative
    assert first.baseline_accuracy == expected / first.testing.n


def test_changing_test_values_and_labels_does_not_change_fitted_coefficients():
    data = records()
    original = risk.run_risk_model(data, [], 'synthetic_only')
    for i, r in enumerate(data[41:]):
        r.nasal_congestion = r.sneezing = r.runny_nose = r.nasal_itching = i % 4
        r.pm2_5 = 10000 + i
    changed = risk.run_risk_model(data, [], 'synthetic_only')
    assert changed.status == 'ok'
    assert [(x.feature, x.coefficient, x.imputation_median, x.scaler_mean) for x in original.coefficients] == [
        (x.feature, x.coefficient, x.imputation_median, x.scaler_mean) for x in changed.coefficients]


def test_missing_predictors_do_not_become_zero_and_training_missing_column_is_reported():
    data = records()
    for r in data[:40]: r.pm2_5 = None
    result = risk.run_risk_model(data, [], 'synthetic_only')
    assert result.status == 'ok' and 'pm2_5' in result.omitted_features
    assert not any(c.feature == 'pm2_5' for c in result.coefficients)
    assert result.feature_missing_counts['pm2_5'] == 40


def test_convergence_failure_returns_controlled_unavailable(monkeypatch):
    def fail(*args): warnings.warn('did not converge', ConvergenceWarning)
    monkeypatch.setattr(risk.LogisticRegression, 'fit', fail)
    result = risk.run_risk_model(records(), [], 'synthetic_only')
    assert result.status == 'unavailable' and result.metrics is None and result.coefficients == []


def test_endpoint_defaults_real_rejects_all_and_is_read_only(client):
    with client.app.state.session_factory() as session:
        session.add_all(records()); session.commit()
    assert client.get('/analysis/risk-model').json()['status'] == 'insufficient_data'
    for mode in ['all', 'invalid']:
        assert client.get(f'/analysis/risk-model?dataset={mode}').status_code == 422
    before = client.get('/symptoms').json()
    result = client.get('/analysis/risk-model?dataset=synthetic_only')
    assert result.status_code == 200 and result.json()['status'] == 'ok'
    assert result.json()['training']['n'] == 40 and result.json()['testing']['n'] == 10
    assert client.get('/symptoms').json() == before
    json.dumps(result.json(), allow_nan=False)
    assert result.json()['training']['target_end'] < result.json()['testing']['target_start']


def test_training_labels_must_be_known_at_first_test_prediction(monkeypatch):
    built = risk.build_model_rows(records(), [], 'synthetic_only')
    altered = list(built.rows)
    altered[0] = replace(altered[0], target_available_timestamp=altered[-1].target_available_timestamp)
    monkeypatch.setattr(risk, 'build_model_rows', lambda *args: replace(built, rows=tuple(altered)))
    result = risk.run_risk_model(records(), [], 'synthetic_only')
    assert result.status == 'insufficient_data'
    assert any('training label' in reason for reason in result.reasons)


def test_majority_baseline_uses_training_counts_even_when_test_majority_differs():
    data = records()
    # Exactly 20 high / 20 low training targets: tie resolves to low.
    for i, item in enumerate(data[1:]):
        score = 2 if i >= 40 or i % 2 else 0
        item.nasal_congestion = item.sneezing = item.runny_nose = item.nasal_itching = score
    result = risk.run_risk_model(data, [], 'synthetic_only')
    assert result.status == 'ok' and result.training.positive == result.training.negative == 20
    assert result.testing.positive == 10 and result.baseline_class == 0 and result.baseline_accuracy == 0
