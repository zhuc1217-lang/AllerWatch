import type { LagExposure, LagHours } from './types/analysis'

export const lagHours: LagHours[] = [0, 6, 12, 24]
export const lagExposures: LagExposure[] = ['pm2_5', 'china_aqi_estimate', 'relative_humidity']

export function lagCellBackground(rho: number | null): string {
  if (rho === null || !Number.isFinite(rho)) return '#f3f4f3'
  // Fixed -1/+1 scale: muted blue for negative, muted green for positive.
  // Intensity represents magnitude, never p-value or clinical risk.
  const end = rho < 0 ? [194, 209, 224] : [188, 218, 202]
  const weight = Math.min(1, Math.abs(rho))
  return `rgb(${end.map(channel => Math.round(255 + (channel - 255) * weight)).join(', ')})`
}
