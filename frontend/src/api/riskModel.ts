import { apiUrl } from './base.ts'
import { modelFeatureLabels } from '../types/riskModel.ts'
import type { ModelMode, RiskModelResponse } from '../types/riskModel'

const featureNames = Object.keys(modelFeatureLabels)
function object(x: unknown): x is Record<string, unknown> { return x !== null && typeof x === 'object' && !Array.isArray(x) }
function count(x: unknown): x is number { return typeof x === 'number' && Number.isSafeInteger(x) && x >= 0 }
function finite(x: unknown): x is number { return typeof x === 'number' && Number.isFinite(x) }
function rate(x: unknown): x is number { return finite(x) && x >= 0 && x <= 1 }
function aware(x: unknown): x is string { return typeof x === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(x) && Number.isFinite(Date.parse(x)) }
function counts(x: unknown): x is Record<string, number> { return object(x) && Object.values(x).every(count) }
function balance(x: unknown): boolean {
  return object(x) && count(x.n) && count(x.positive) && count(x.negative) && x.positive + x.negative === x.n &&
    (x.n === 0 ? x.positive_percent === null && x.negative_percent === null :
      finite(x.positive_percent) && finite(x.negative_percent) && Math.abs(x.positive_percent - 100 * x.positive / x.n) < 1e-6 &&
      Math.abs(x.negative_percent - 100 * x.negative / x.n) < 1e-6)
}
function period(x: unknown): x is Record<string, unknown> & { n: number; positive: number; negative: number } {
  if (!object(x) || !balance(x)) return false
  if (x.n === 0) return ['feature_start', 'feature_end', 'target_start', 'target_end'].every(k => x[k] === null)
  return aware(x.feature_start) && aware(x.feature_end) && aware(x.target_start) && aware(x.target_end) &&
    Date.parse(x.feature_start) <= Date.parse(x.feature_end) && Date.parse(x.target_start) <= Date.parse(x.target_end) &&
    Date.parse(x.feature_start) < Date.parse(x.target_start) && Date.parse(x.feature_end) < Date.parse(x.target_end)
}

export function isRiskModelResponse(x: unknown, mode: ModelMode): x is RiskModelResponse {
  if (!object(x) || x.dataset_mode !== mode || !['real_only', 'synthetic_only'].includes(mode) ||
    !['ok', 'insufficient_data', 'unavailable'].includes(String(x.status)) || !count(x.record_count) ||
    !count(x.real_count) || !count(x.synthetic_count) || x.real_count + x.synthetic_count !== x.record_count ||
    (mode === 'real_only' ? x.synthetic_count !== 0 : x.real_count !== 0) ||
    x.includes_synthetic !== (x.synthetic_count > 0) || typeof x.data_notice !== 'string' || x.observation_unit !== 'individual_observation' ||
    (x.record_count === 0 ? x.date_start !== null || x.date_end !== null : !aware(x.date_start) || !aware(x.date_end)) ||
    x.target !== 'next_observation_tnss_gte_6' || x.probability_threshold !== .5 || x.minimum_rows !== 30 ||
    x.split_method !== 'chronological_80_20_no_shuffle' || typeof x.feature_timing !== 'string' || typeof x.daily_health_policy !== 'string' ||
    !Array.isArray(x.reasons) || !x.reasons.every(r => typeof r === 'string') || !count(x.model_row_count) ||
    x.candidate_pair_count !== Math.max(0, x.record_count - 1) || !counts(x.excluded_pair_counts) || !counts(x.daily_candidate_counts) ||
    Object.values(x.excluded_pair_counts).reduce((a, b) => a + b, 0) + x.model_row_count !== x.candidate_pair_count ||
    Object.values(x.daily_candidate_counts).reduce((a, b) => a + b, 0) !== x.model_row_count ||
    !object(x.class_balance) || !balance(x.class_balance) || x.class_balance.n !== x.model_row_count ||
    !period(x.training) || !period(x.testing) || x.training.n !== Math.floor(x.model_row_count * .8) ||
    x.training.n + x.testing.n !== x.model_row_count || x.training.positive + x.testing.positive !== x.class_balance.positive ||
    x.first_test_prediction_time !== x.testing.feature_start || !counts(x.feature_missing_counts) ||
    !featureNames.every(k => count(x.feature_missing_counts && (x.feature_missing_counts as Record<string, unknown>)[k]))) return false
  const n = x.model_row_count, train = x.training, test = x.testing
  if (Object.values(x.feature_missing_counts).some(v => v > n) || !object(x.horizon_hours)) return false
  const { min, median, max } = x.horizon_hours
  if (n === 0 ? min !== null || median !== null || max !== null : !finite(min) || !finite(median) || !finite(max) || min <= 0 || min > median || median > max) return false
  if (train.n && test.n && Date.parse(String(train.target_end)) >= Date.parse(String(test.target_start))) return false
  if (!Array.isArray(x.candidate_features) || x.candidate_features.join(',') !== featureNames.join(',') ||
    !Array.isArray(x.used_features) || !Array.isArray(x.omitted_features) || !Array.isArray(x.coefficients) || !count(x.feature_count)) return false
  if (x.status !== 'ok') return x.reasons.length > 0 && x.metrics === null && x.baseline_accuracy === null &&
    x.baseline_class === null && x.intercept === null && x.coefficients.length === 0 && x.feature_count === 0
  if (x.reasons.length || n < 30 || train.n < 24 || test.n < 6 || train.positive < 3 || train.negative < 3 ||
    Number(x.class_balance.positive) < 5 || Number(x.class_balance.negative) < 5 ||
    Date.parse(String(train.target_end)) > Date.parse(String(test.feature_start)) ||
    !finite(x.intercept) || !rate(x.baseline_accuracy) || x.baseline_class !== Number(train.positive > train.negative) ||
    !object(x.metrics) || !rate(x.metrics.accuracy) || !object(x.metrics.unavailable_reasons) ||
    !Object.values(x.metrics.unavailable_reasons).every(v => typeof v === 'string')) return false
  const metrics = x.metrics, matrix = metrics.confusion_matrix
  if (!counts(matrix) || !['true_negatives', 'false_positives', 'false_negatives', 'true_positives'].every(k => count(matrix[k])) ||
    matrix.true_negatives + matrix.false_positives !== test.negative || matrix.true_positives + matrix.false_negatives !== test.positive ||
    Math.abs(Number(metrics.accuracy) - (matrix.true_negatives + matrix.true_positives) / test.n) > 1e-9) return false
  for (const metric of ['precision', 'recall', 'f1', 'roc_auc']) {
    if (metrics[metric] === null ? typeof (metrics.unavailable_reasons as Record<string, unknown>)[metric] !== 'string' : !rate(metrics[metric])) return false
  }
  if ((test.positive === 0 || test.negative === 0) && metrics.roc_auc !== null) return false
  const used = x.used_features
  if (x.feature_count !== used.length || used.length === 0 || new Set(used).size !== used.length ||
    !used.every(k => typeof k === 'string' && featureNames.includes(k)) ||
    x.omitted_features.join(',') !== featureNames.filter(k => !used.includes(k)).join(',') || x.coefficients.length !== used.length) return false
  return used.every(name => x.coefficients instanceof Array && x.coefficients.filter(c => object(c) && c.feature === name).length === 1) &&
    x.coefficients.every(c => object(c) && finite(c.coefficient) && finite(c.imputation_median) && finite(c.scaler_mean) &&
      finite(c.scaler_scale) && c.scaler_scale > 0 && count(c.train_missing) && c.train_missing < train.n &&
      count(c.test_missing) && c.test_missing <= test.n)
}

export async function getRiskModel(mode: ModelMode, signal: AbortSignal): Promise<RiskModelResponse> {
  if (!['real_only', 'synthetic_only'].includes(mode)) throw new Error('Choose Real data or Synthetic data. Mixed model training is disabled.')
  const response = await fetch(apiUrl(`/analysis/risk-model?dataset=${mode}`), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error('Could not load the experimental model. Check the backend and retry.')
  const body: unknown = await response.json().catch(() => null)
  if (!isRiskModelResponse(body, mode)) throw new Error('The backend returned an unexpected model response. Please retry.')
  return body
}
