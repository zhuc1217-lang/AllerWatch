import { filterHistory } from './history.ts'
import type { SymptomRecord } from './types/symptoms'

export type DashboardRange = '7' | '30' | '90' | 'all'
export type ObservationType = 'all' | 'real' | 'synthetic'
export type ExposureKey = 'pm2_5' | 'us_aqi' | 'relative_humidity'
export type MetricKey = 'tnss' | ExposureKey

export const timeRanges: { value: DashboardRange; label: string }[] = [
  { value: '7', label: 'Last 7 days' }, { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' }, { value: 'all', label: 'All data' },
]
export const observationTypes: { value: ObservationType; label: string }[] = [
  { value: 'all', label: 'All' }, { value: 'real', label: 'Real only' }, { value: 'synthetic', label: 'Synthetic only' },
]
export const exposureMetrics: { key: ExposureKey; label: string; unit: string; axis: string; title: string }[] = [
  { key: 'pm2_5', label: 'PM2.5', unit: 'µg/m³', axis: 'PM2.5 (µg/m³)', title: 'PM2.5 Over Time' },
  { key: 'us_aqi', label: 'US AQI', unit: '', axis: 'US AQI (index)', title: 'US AQI Over Time' },
  { key: 'relative_humidity', label: 'Relative humidity', unit: '%', axis: 'Humidity (%)', title: 'Relative Humidity Over Time' },
]

export function filterDashboard(records: SymptomRecord[], range: DashboardRange, type: ObservationType, now: number) {
  return filterHistory(records, range, now).filter(record =>
    type === 'all' || record.is_synthetic === (type === 'synthetic'))
}

export function metricValue(record: SymptomRecord, key: MetricKey): number | null {
  const value = record[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function summarizeDashboard(records: SymptomRecord[]) {
  const ordered = filterHistory(records, 'all', 0)
  const synthetic = records.filter(record => record.is_synthetic).length
  return {
    total: records.length, real: records.length - synthetic, synthetic,
    latest: ordered[0] ?? null,
    firstTimestamp: ordered.at(-1)?.timestamp ?? null,
    lastTimestamp: ordered[0]?.timestamp ?? null,
    missingPm25: records.filter(record => metricValue(record, 'pm2_5') === null).length,
    missingAqi: records.filter(record => metricValue(record, 'us_aqi') === null).length,
    missingHumidity: records.filter(record => metricValue(record, 'relative_humidity') === null).length,
  }
}

export type TrendPoint = {
  timestamp: number
  real: number | null
  synthetic: number | null
  record: SymptomRecord | null
}
export type PairedPoint = { timestamp: number; x: number; y: number; record: SymptomRecord }

export function makeTrendData(records: SymptomRecord[], metric: MetricKey): TrendPoint[] {
  const ordered = [...filterHistory(records, 'all', 0)].reverse()
  const points: TrendPoint[] = []
  for (const record of ordered) {
    const timestamp = Date.parse(record.timestamp)
    const previous = points.at(-1)
    if (previous && timestamp - previous.timestamp > 86400000) {
      points.push({ timestamp: (previous.timestamp + timestamp) / 2, real: null, synthetic: null, record: null })
    }
    const value = metricValue(record, metric)
    // Retain null rows so lines break at missing measurements and changes of type.
    points.push({ timestamp, real: record.is_synthetic ? null : value,
      synthetic: record.is_synthetic ? value : null, record })
  }
  return points
}

export function makePairedData(records: SymptomRecord[], key: ExposureKey): PairedPoint[] {
  return relationshipData(records, key).points
}

export function relationshipData(records: SymptomRecord[], key: ExposureKey) {
  let missingPairs = 0, temporallyExcludedPairs = 0
  const points: PairedPoint[] = []
  for (const record of [...filterHistory(records, 'all', 0)].reverse()) {
    const value = metricValue(record, key)
    if (value === null || metricValue(record, 'tnss') === null) missingPairs += 1
    // Use the server's shared rule; absent eligibility fails closed for older APIs.
    else if (record.environment_time_eligible?.[key] !== true) temporallyExcludedPairs += 1
    else points.push({ timestamp: Date.parse(record.timestamp), x: value, y: record.tnss, record })
  }
  return { points, total: records.length, missingPairs, temporallyExcludedPairs }
}

export function metricDomain(records: SymptomRecord[], metric: MetricKey): [number, number] {
  if (metric === 'tnss') return [0, 12]
  if (metric === 'relative_humidity') return [0, 100]
  const maximum = Math.max(0, ...records.map(record => metricValue(record, metric) ?? 0))
  // Axis padding only: no missing values are added to chart points.
  return [0, Math.max(1, Math.ceil(maximum * 1.1))]
}

export function displayValue(value: number | null | undefined, unit = ''): string {
  return value == null ? 'Unavailable' : `${value}${unit ? ` ${unit}` : ''}`
}
