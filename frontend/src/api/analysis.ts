import { apiUrl } from './base.ts'
import { exposureKeys, variableKeys } from '../analysis.ts'
import { lagExposures, lagHours } from '../laggedAnalysis.ts'
import { dailyLabels } from '../types/dailyHealth.ts'
import type { DailyAssociationsResponse } from '../types/dailyHealth'
import type { AnalysisResponse, AssociationsResponse, DatasetMetadata, DatasetMode, DescriptiveResponse, LaggedResponse } from '../types/analysis'

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}
function finiteOrNull(value: unknown): boolean {
  return value === null || (typeof value === 'number' && Number.isFinite(value))
}
function awareDate(value: unknown): boolean {
  return typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value))
}
function metadata(value: unknown, mode: DatasetMode): value is DatasetMetadata & Record<string, unknown> {
  return object(value) && value.dataset_mode === mode && count(value.record_count) &&
    count(value.real_count) && count(value.synthetic_count) && value.real_count + value.synthetic_count === value.record_count &&
    (mode !== 'real_only' || value.synthetic_count === 0) && (mode !== 'synthetic_only' || value.real_count === 0) &&
    value.includes_synthetic === (value.synthetic_count > 0) && typeof value.data_notice === 'string' &&
    value.observation_unit === 'individual_observation' &&
    (value.record_count === 0 ? value.date_start === null && value.date_end === null :
      awareDate(value.date_start) && awareDate(value.date_end) && Date.parse(String(value.date_start)) <= Date.parse(String(value.date_end)))
}

export function isDescriptiveResponse(value: unknown, mode: DatasetMode): value is DescriptiveResponse {
  if (!metadata(value, mode) || !object(value.variables) || value.standard_deviation !== 'sample_ddof_1' || value.percentile_method !== 'linear') return false
  const variables = value.variables
  return variableKeys.every(key => {
    const item = variables[key]
    return object(item) && count(item.n) && count(item.missing) && item.n + item.missing === value.record_count &&
      ['mean', 'median', 'std', 'min', 'q1', 'q3', 'max'].every(field => finiteOrNull(item[field])) &&
      (item.n > 0 || ['mean', 'median', 'std', 'min', 'q1', 'q3', 'max'].every(field => item[field] === null)) &&
      (item.n >= 2 || item.std === null)
  })
}

export function isAssociationsResponse(value: unknown, mode: DatasetMode): value is AssociationsResponse {
  if (!metadata(value, mode) || value.outcome !== 'tnss' || !count(value.minimum_pairs) || value.minimum_pairs < 2 ||
    value.temporal_tolerance_hours !== 3 ||
    value.p_value_method !== 'two_sided_asymptotic_unadjusted' || !Array.isArray(value.associations)) return false
  const items = value.associations
  const minimum = value.minimum_pairs
  return items.length === exposureKeys.length && exposureKeys.every(key => items.filter(item => object(item) && item.variable === key).length === 1) &&
    items.every(item => {
      if (!object(item) || !count(item.n) || !count(item.missing_pairs) || !count(item.temporally_excluded_pairs) ||
        item.n + item.missing_pairs + item.temporally_excluded_pairs !== value.record_count) return false
      if (item.status !== 'ok') return ['insufficient_data', 'insufficient_variation', 'unavailable'].includes(String(item.status)) &&
        item.spearman_rho === null && item.p_value === null
      return item.n >= minimum && typeof item.spearman_rho === 'number' && Number.isFinite(item.spearman_rho) &&
        Math.abs(item.spearman_rho) <= 1 && typeof item.p_value === 'number' && Number.isFinite(item.p_value) && item.p_value >= 0 && item.p_value <= 1
    })
}

export async function getAnalysis(mode: DatasetMode, signal: AbortSignal): Promise<AnalysisResponse> {
  async function load(endpoint: string): Promise<unknown> {
    const response = await fetch(apiUrl(`/analysis/${endpoint}?dataset=${mode}`), { signal, cache: 'no-store' })
    if (!response.ok) throw new Error('Could not load analysis. Check that the backend is running, then try again.')
    return response.json().catch(() => null)
  }
  const [descriptive, associations] = await Promise.all([load('descriptive'), load('associations')])
  if (!isDescriptiveResponse(descriptive, mode) || !isAssociationsResponse(associations, mode)) {
    throw new Error('The backend returned an unexpected analysis response. Please try again.')
  }
  if (['record_count', 'real_count', 'synthetic_count', 'date_start', 'date_end'].some(key =>
    descriptive[key as keyof DatasetMetadata] !== associations[key as keyof DatasetMetadata])) {
    throw new Error('The dataset changed while analysis was loading. Please retry to refresh both summaries.')
  }
  return { descriptive, associations }
}

export function isLaggedResponse(value: unknown, mode: DatasetMode): value is LaggedResponse {
  if (!metadata(value, mode) || value.outcome !== 'tnss' || !count(value.minimum_pairs) || value.minimum_pairs < 2 ||
    value.p_value_method !== 'two_sided_asymptotic_unadjusted' || !Array.isArray(value.lags_hours) ||
    value.lags_hours.join(',') !== lagHours.join(',') || !object(value.matching) || !Array.isArray(value.results)) return false
  const matching = value.matching
  if (matching.approximate !== true || matching.timezone !== 'UTC' || matching.tolerance_hours !== 3 ||
    matching.method !== 'same_record_0h_backward_source_time_other_lags' ||
    matching.nonzero_source_record_and_retrieval_before_target !== true || matching.cross_provenance_matching !== false ||
    typeof matching.zero_lag_note !== 'string' || !object(matching.exposure_time_fields) ||
    matching.exposure_time_fields.pm2_5 !== 'air_quality_timestamp' || matching.exposure_time_fields.china_aqi_estimate !== 'air_quality_timestamp' ||
    matching.exposure_time_fields.relative_humidity !== 'weather_timestamp') return false
  const items = value.results, minimum = value.minimum_pairs
  return items.length === 12 && lagExposures.every(variable => lagHours.every(lag =>
    items.filter(item => object(item) && item.variable === variable && item.lag_hours === lag).length === 1)) && items.every(item => {
      if (!object(item) || !count(item.n) || !count(item.missing_pairs) || item.n + item.missing_pairs !== value.record_count ||
        !count(item.real_pairs) || !count(item.synthetic_pairs) || item.real_pairs + item.synthetic_pairs !== item.n ||
        item.real_pairs > value.real_count || item.synthetic_pairs > value.synthetic_count ||
        !count(item.distinct_source_records) || item.distinct_source_records > item.n) return false
      const { actual_lag_hours_min: min, actual_lag_hours_median: median, actual_lag_hours_max: max } = item
      if (item.n === 0) {
        if (min !== null || median !== null || max !== null || item.distinct_source_records !== 0) return false
      } else if (typeof min !== 'number' || typeof median !== 'number' || typeof max !== 'number' ||
        ![min, median, max].every(Number.isFinite) || min < Number(item.lag_hours) ||
        min > median || median > max || max > Number(item.lag_hours) + 3 || item.distinct_source_records === 0) return false
      if (item.status !== 'ok') return ['insufficient_data', 'insufficient_variation', 'unavailable'].includes(String(item.status)) &&
        item.spearman_rho === null && item.p_value === null
      return item.n >= minimum && typeof item.spearman_rho === 'number' && Number.isFinite(item.spearman_rho) &&
        Math.abs(item.spearman_rho) <= 1 && typeof item.p_value === 'number' && Number.isFinite(item.p_value) && item.p_value >= 0 && item.p_value <= 1
    })
}

export async function getLaggedAnalysis(mode: DatasetMode, signal: AbortSignal): Promise<LaggedResponse> {
  const response = await fetch(apiUrl(`/analysis/lagged-associations?dataset=${mode}`), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error('Could not load lagged associations. Check that the backend is running, then try again.')
  const body: unknown = await response.json().catch(() => null)
  if (!isLaggedResponse(body, mode)) throw new Error('The backend returned an unexpected lagged-analysis response. Please try again.')
  return body
}

export function isDailyAssociationsResponse(value: unknown, mode: DatasetMode): value is DailyAssociationsResponse {
  if (!metadata(value, mode) || value.outcome !== 'tnss' || typeof value.calendar_timezone !== 'string' ||
    value.join_method !== 'study_date_and_same_provenance' || value.p_value_method !== 'two_sided_asymptotic_unadjusted' ||
    !count(value.minimum_pairs) || value.minimum_pairs < 2 || !Array.isArray(value.associations)) return false
  if (!count(value.daily_record_count) || !count(value.real_daily_count) || !count(value.synthetic_daily_count) ||
    value.real_daily_count + value.synthetic_daily_count !== value.daily_record_count ||
    (mode === 'real_only' && value.synthetic_daily_count !== 0) || (mode === 'synthetic_only' && value.real_daily_count !== 0) ||
    !count(value.matched_symptom_count) || !count(value.missing_daily_symptom_count) ||
    value.matched_symptom_count + value.missing_daily_symptom_count !== value.record_count ||
    !count(value.matched_daily_records) || !count(value.daily_records_without_symptoms) ||
    value.matched_daily_records + value.daily_records_without_symptoms !== value.daily_record_count) return false
  const items = value.associations, minPairs = value.minimum_pairs, matchedDays = value.matched_daily_records
  return items.length === 4 && Object.keys(dailyLabels).every(variable => items.filter(item => object(item) && item.variable === variable).length === 1) && items.every(item => {
    if (!object(item) || !count(item.n) || !count(item.missing_pairs) || item.n + item.missing_pairs !== value.record_count ||
      !count(item.real_pairs) || !count(item.synthetic_pairs) || item.real_pairs + item.synthetic_pairs !== item.n ||
      item.real_pairs > value.real_count || item.synthetic_pairs > value.synthetic_count ||
      !count(item.distinct_daily_records) || item.distinct_daily_records > item.n || item.distinct_daily_records > matchedDays) return false
    if (item.status !== 'ok') return ['insufficient_data', 'insufficient_variation', 'unavailable'].includes(String(item.status)) && item.spearman_rho === null && item.p_value === null
    return item.n >= minPairs && typeof item.spearman_rho === 'number' && Number.isFinite(item.spearman_rho) &&
      Math.abs(item.spearman_rho) <= 1 && typeof item.p_value === 'number' && Number.isFinite(item.p_value) && item.p_value >= 0 && item.p_value <= 1
  })
}

export async function getDailyAssociations(mode: DatasetMode, signal: AbortSignal): Promise<DailyAssociationsResponse> {
  const response = await fetch(apiUrl(`/analysis/daily-health-associations?dataset=${mode}`), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error('Could not load daily health associations. Check the backend and retry.')
  const body: unknown = await response.json().catch(() => null)
  if (!isDailyAssociationsResponse(body, mode)) throw new Error('Unexpected daily health analysis response. Please retry.')
  return body
}
