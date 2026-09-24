import type { AnalysisVariable, AssociationResult, AssociationStatus, DatasetMode, Exposure } from './types/analysis'

export const datasetOptions: { value: DatasetMode; label: string }[] = [
  { value: 'real_only', label: 'Real data' },
  { value: 'synthetic_only', label: 'Synthetic data' },
  { value: 'all', label: 'All data' },
]
export const exposureKeys: Exposure[] = ['pm2_5', 'pm10', 'us_aqi', 'relative_humidity', 'temperature_c']
export const variableKeys: AnalysisVariable[] = ['tnss', 'overall_severity', ...exposureKeys]
export const variableLabels: Record<AnalysisVariable, string> = {
  tnss: 'TNSS (0–12)', overall_severity: 'Overall severity (0–10)', pm2_5: 'PM2.5 (µg/m³)',
  pm10: 'PM10 (µg/m³)', us_aqi: 'US AQI (index)', relative_humidity: 'Humidity (%)', temperature_c: 'Temperature (°C)',
}
export const exposureLabels: Record<Exposure, string> = {
  pm2_5: 'PM2.5', pm10: 'PM10', us_aqi: 'US AQI', relative_humidity: 'Humidity', temperature_c: 'Temperature',
}
export const statusLabels: Record<AssociationStatus, string> = {
  ok: 'Calculated', insufficient_data: 'Insufficient paired observations',
  insufficient_variation: 'Insufficient variation', unavailable: 'Unavailable',
}

export function formatStatistic(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return 'Unavailable'
  // Avoid misleading negative zero from decimal rounding; preserve small magnitudes.
  if (value !== 0 && Math.abs(value) < 10 ** -digits) return value.toExponential(2)
  return value.toFixed(digits)
}

export function formatPValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return 'Unavailable'
  if (value === 0) return '< 0.0001'
  return value < 0.001 ? value.toExponential(2) : value.toFixed(3)
}

export function coefficientChartData(associations: AssociationResult[]) {
  // Plot backend estimates only. Missing results are not zero-length coefficients.
  return associations.filter(item => item.status === 'ok' && item.spearman_rho != null &&
    Number.isFinite(item.spearman_rho)).map(item => ({
      label: exposureLabels[item.variable], rho: item.spearman_rho!, n: item.n,
    }))
}
