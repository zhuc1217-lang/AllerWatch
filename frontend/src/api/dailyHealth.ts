import { apiUrl } from './base.ts'
import { isCalendarDate } from '../dailyHealth.ts'
import type { DailyList, DailyRecord, DailyValues } from '../types/dailyHealth'

function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function numberIn(value: unknown, min: number, max: number, integer = false): boolean {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max && (!integer || Number.isInteger(value))
}
export function isDailyRecord(value: unknown): value is DailyRecord {
  return object(value) && numberIn(value.id, 1, Number.MAX_SAFE_INTEGER, true) && isCalendarDate(value.date) &&
    numberIn(value.sleep_duration_hours, 0, 24) && numberIn(value.sleep_quality, 1, 5, true) &&
    numberIn(value.stress_level, 1, 5, true) && numberIn(value.exercise_minutes, 0, 1440, true) &&
    (value.notes === null || typeof value.notes === 'string') && typeof value.is_synthetic === 'boolean' &&
    (value.updated_at == null || (typeof value.updated_at === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value.updated_at) && Number.isFinite(Date.parse(value.updated_at)))) &&
    typeof value.created_at === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value.created_at) && Number.isFinite(Date.parse(value.created_at))
}
export class DailyHealthError extends Error {
  status: number
  fields: Record<string, string>
  constructor(message: string, status = 0, fields: Record<string, string> = {}) { super(message); this.status = status; this.fields = fields }
}

export async function getDailyList(signal: AbortSignal): Promise<DailyList> {
  const response = await fetch(apiUrl('/daily-health?dataset=all'), { signal, cache: 'no-store' })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error('Could not load daily health records. Check the backend and retry.')
  if (!object(body) || typeof body.calendar_timezone !== 'string' || !isCalendarDate(body.today) ||
    !Array.isArray(body.records) || !body.records.every(isDailyRecord)) throw new Error('Unexpected daily health response. Please retry.')
  return body as DailyList
}
export async function getDailyRecord(date: string, signal: AbortSignal, publicDemo = false): Promise<DailyRecord | null> {
  const response = await fetch(apiUrl(`/daily-health/${date}${publicDemo ? '?is_synthetic=true' : ''}`), { signal, cache: 'no-store' })
  if (response.status === 404) return null
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error('Could not load this date. Retry before editing it.')
  if (!isDailyRecord(body) || body.date !== date || body.is_synthetic !== publicDemo) throw new Error('Unexpected daily health record. Please retry.')
  return body
}
export async function saveDailyRecord(date: string, values: DailyValues, existing: boolean, signal: AbortSignal, publicDemo = false): Promise<DailyRecord> {
  const response = await fetch(apiUrl(existing ? `/daily-health/${date}${publicDemo ? '?is_synthetic=true' : ''}` : '/daily-health'), {
    method: existing ? 'PUT' : 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(existing ? values : { ...values, date, is_synthetic: publicDemo }),
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const fields: Record<string, string> = {}
    if (response.status === 422 && object(body) && Array.isArray(body.detail)) {
      for (const item of body.detail) if (object(item) && Array.isArray(item.loc) && typeof item.msg === 'string') fields[String(item.loc.at(-1))] = item.msg
    }
    throw new DailyHealthError(response.status === 409
      ? 'A record already exists for this date and type. Your entries have been kept. Load the saved record before updating.'
      : response.status === 422 ? 'Please correct the highlighted fields. Your entries have been kept.'
      : 'Saving could not be confirmed. Your entries have been kept. Check the backend and try again.', response.status, fields)
  }
  if (!isDailyRecord(body) || body.date !== date || body.is_synthetic !== publicDemo) throw new DailyHealthError('Saving could not be confirmed from the response. Your entries have been kept. Load the saved record before retrying.')
  return body
}
