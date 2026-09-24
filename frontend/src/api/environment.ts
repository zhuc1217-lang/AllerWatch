import { apiUrl } from './base.ts'
import type { CurrentEnvironment } from '../types/environment'

const unavailableMessage = 'Environmental data are temporarily unavailable.'
const measurementFields = ['temperature_c', 'relative_humidity', 'pm2_5', 'pm10', 'us_aqi'] as const

function finiteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function utcTimestamp(value: unknown): value is string {
  return typeof value === 'string' && /(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value))
}

function isEnvironment(value: unknown): value is CurrentEnvironment {
  if (typeof value !== 'object' || value === null) return false
  const body = value as Record<string, unknown>
  if (!utcTimestamp(body.timestamp) ||
    !(body.weather_timestamp === null || utcTimestamp(body.weather_timestamp)) ||
    !(body.air_quality_timestamp === null || utcTimestamp(body.air_quality_timestamp)) ||
    !finiteNumber(body.latitude) || Math.abs(body.latitude) > 90 ||
    !finiteNumber(body.longitude) || Math.abs(body.longitude) > 180 ||
    !measurementFields.every((field) => body[field] === null || finiteNumber(body[field]))) return false

  const data = body as CurrentEnvironment
  const complete = measurementFields.every((field) => data[field] !== null)
  return data.status === (complete ? 'available' : 'partial') &&
    measurementFields.some((field) => data[field] !== null) &&
    (data.temperature_c === null || data.temperature_c >= -273.15) &&
    (data.relative_humidity === null || (data.relative_humidity >= 0 && data.relative_humidity <= 100)) &&
    [data.pm2_5, data.pm10, data.us_aqi].every((reading) => reading === null || reading >= 0) &&
    ((data.temperature_c === null && data.relative_humidity === null) || data.weather_timestamp !== null) &&
    ((data.pm2_5 === null && data.pm10 === null && data.us_aqi === null) || data.air_quality_timestamp !== null)
}

export async function getCurrentEnvironment(signal: AbortSignal): Promise<CurrentEnvironment> {
  const response = await fetch(apiUrl('/environment/current'), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(unavailableMessage)
  const body: unknown = await response.json().catch(() => null)
  if (!isEnvironment(body)) throw new Error(unavailableMessage)
  return body
}
