import test from 'node:test'
import assert from 'node:assert/strict'
import { getRiskModel, isRiskModelResponse } from '../src/api/riskModel.ts'
import { modelFeatureLabels } from '../src/types/riskModel.ts'

const names = Object.keys(modelFeatureLabels)
function fixture(mode = 'synthetic_only') {
  const real = mode === 'real_only', used = names.slice(0, 7)
  return { dataset_mode: mode, record_count: 51, real_count: real ? 51 : 0, synthetic_count: real ? 0 : 51,
    includes_synthetic: !real, data_notice: 'Deterministic fixture', observation_unit: 'individual_observation',
    date_start: '2026-01-01T08:00:00Z', date_end: '2026-02-20T08:00:00Z', status: 'ok', reasons: [],
    target: 'next_observation_tnss_gte_6', probability_threshold: .5, minimum_rows: 30,
    split_method: 'chronological_80_20_no_shuffle', feature_timing: 'Previous observation', daily_health_policy: 'Unversioned records excluded',
    model_row_count: 50, candidate_pair_count: 50, excluded_pair_counts: {}, daily_candidate_counts: { no_previous_day_record: 50 },
    class_balance: { n: 50, positive: 25, negative: 25, positive_percent: 50, negative_percent: 50 },
    training: { n: 40, positive: 20, negative: 20, positive_percent: 50, negative_percent: 50,
      target_start: '2026-01-02T08:00:00Z', target_end: '2026-02-10T08:00:00Z', feature_start: '2026-01-01T08:00:03Z', feature_end: '2026-02-09T08:00:03Z' },
    testing: { n: 10, positive: 5, negative: 5, positive_percent: 50, negative_percent: 50,
      target_start: '2026-02-11T08:00:00Z', target_end: '2026-02-20T08:00:00Z', feature_start: '2026-02-10T08:00:03Z', feature_end: '2026-02-19T08:00:03Z' },
    first_test_prediction_time: '2026-02-10T08:00:03Z', horizon_hours: { min: 23.999, median: 23.999, max: 23.999 },
    feature_count: 7, candidate_features: names, used_features: used, omitted_features: names.slice(7),
    feature_missing_counts: Object.fromEntries(names.map((key, i) => [key, i < 7 ? 0 : 50])),
    metrics: { accuracy: .7, precision: 4 / 6, recall: .8, f1: 8 / 11, roc_auc: .75, unavailable_reasons: {},
      confusion_matrix: { true_negatives: 3, false_positives: 2, false_negatives: 1, true_positives: 4 } },
    baseline_class: 0, baseline_accuracy: .5, intercept: -.2,
    coefficients: used.map((feature, i) => ({ feature, coefficient: -.1 * i, train_missing: 0, test_missing: 0,
      imputation_median: i, scaler_mean: i + .5, scaler_scale: 1 })) }
}

for (const mode of ['real_only', 'synthetic_only']) test(`accepts labelled ${mode} model and rejects mixed provenance`, () => {
  const body = fixture(mode)
  assert.equal(isRiskModelResponse(body, mode), true)
  body.real_count = 25; body.synthetic_count = 26
  assert.equal(isRiskModelResponse(body, mode), false)
})

test('rejects incorrect timing/split/target, invalid feature names and inconsistent counts', () => {
  for (const modify of [b => { b.training.target_end = b.testing.target_start },
    b => { b.testing.feature_start = b.testing.target_start; b.first_test_prediction_time = b.testing.target_start },
    b => { b.split_method = 'random' }, b => { b.target = 'current_tnss' },
    b => { b.coefficients[0].feature = 'tnss' }, b => { b.feature_missing_counts.pm2_5 = 1000 },
    b => { b.metrics.confusion_matrix.true_positives = 5 }, b => { b.baseline_class = 1 },
    b => { b.model_row_count = 51 }, b => { b.training.positive_percent = 100 }]) {
    const body = fixture(); modify(body)
    assert.equal(isRiskModelResponse(body, 'synthetic_only'), false)
  }
})

test('non-finite coefficients and metrics cannot reach the model UI; zero remains valid', () => {
  assert.equal(isRiskModelResponse(fixture(), 'synthetic_only'), true)
  for (const value of [NaN, Infinity, -Infinity, undefined]) {
    const coefficient = fixture(), metric = fixture()
    coefficient.coefficients[0].coefficient = value; metric.metrics.precision = value
    assert.equal(isRiskModelResponse(coefficient, 'synthetic_only'), false)
    assert.equal(isRiskModelResponse(metric, 'synthetic_only'), false)
  }
})

test('insufficient-data responses have explicit reasons and no invented model output', () => {
  const body = fixture('real_only')
  Object.assign(body, { status: 'insufficient_data', reasons: ['Controlled insufficient fixture'], metrics: null,
    baseline_accuracy: null, baseline_class: null, intercept: null, coefficients: [], feature_count: 0, used_features: [], omitted_features: [] })
  assert.equal(isRiskModelResponse(body, 'real_only'), true)
  body.metrics = fixture().metrics
  assert.equal(isRiskModelResponse(body, 'real_only'), false)
})

test('single-class test permits null AUC with explanation but rejects an invented AUC', () => {
  const body = fixture()
  Object.assign(body.testing, { positive: 0, negative: 10, positive_percent: 0, negative_percent: 100 })
  Object.assign(body.class_balance, { positive: 20, negative: 30, positive_percent: 40, negative_percent: 60 })
  Object.assign(body.metrics, { accuracy: 1, precision: null, recall: null, f1: null, roc_auc: null,
    unavailable_reasons: { precision: 'No predicted positives', recall: 'No actual positives', f1: 'No actual or predicted positives', roc_auc: 'One test class' },
    confusion_matrix: { true_negatives: 10, false_positives: 0, false_negatives: 0, true_positives: 0 } })
  assert.equal(isRiskModelResponse(body, 'synthetic_only'), true)
  body.metrics.roc_auc = .5
  assert.equal(isRiskModelResponse(body, 'synthetic_only'), false)
})

test('client passes selected mode and abort signal, uses no cache, and never requests all', async context => {
  const calls = [], signal = new AbortController().signal
  context.mock.method(globalThis, 'fetch', async (url, options) => { calls.push({ url, options }); return Response.json(fixture()) })
  assert.equal((await getRiskModel('synthetic_only', signal)).status, 'ok')
  assert.equal(calls[0].url, '/api/analysis/risk-model?dataset=synthetic_only')
  assert.equal(calls[0].options.signal, signal); assert.equal(calls[0].options.cache, 'no-store')
  await assert.rejects(getRiskModel('all', signal), /Mixed model training is disabled/)
  assert.equal(calls.length, 1)
})

test('HTTP failure and malformed success responses are readable errors', async context => {
  context.mock.method(globalThis, 'fetch', async () => Response.json({}, { status: 503 }))
  await assert.rejects(getRiskModel('real_only', new AbortController().signal), /Check the backend/)
  context.mock.method(globalThis, 'fetch', async () => Response.json({ metrics: { accuracy: 1 } }))
  await assert.rejects(getRiskModel('real_only', new AbortController().signal), /unexpected model response/)
})
