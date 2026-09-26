import { apiUrl } from './base.ts'
import { fieldLabels, symptomLabels } from '../types/symptoms'
import type { FieldErrors, FormField, SavedSymptomRecord, SymptomRecord, SymptomRecordInput } from '../types/symptoms'

export class SymptomSubmissionError extends Error {
  constructor(message: string, readonly fieldErrors: FieldErrors = {}) {
    super(message)
    this.name = 'SymptomSubmissionError'
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isIntegerInRange(value: unknown, minimum: number, maximum: number): boolean {
  return typeof value === 'number' && Number.isInteger(value) && value >= minimum && value <= maximum
}

function isSymptomRecord(value: unknown): value is SymptomRecord {
  return isObject(value) &&
    isIntegerInRange(value.id, 1, Number.MAX_SAFE_INTEGER) &&
    typeof value.timestamp === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value.timestamp) &&
    Number.isFinite(Date.parse(value.timestamp)) &&
    Object.keys(symptomLabels).every((field) => isIntegerInRange(value[field], 0, 3)) &&
    isIntegerInRange(value.overall_severity, 0, 10) &&
    isIntegerInRange(value.tnss, 0, 12) &&
    typeof value.medication_taken === 'boolean' &&
    typeof value.is_synthetic === 'boolean' &&
    (value.notes === null || typeof value.notes === 'string') &&
    (value.environment_time_eligible === undefined ||
      (isObject(value.environment_time_eligible) && !Array.isArray(value.environment_time_eligible) &&
        ['pm2_5', 'pm10', 'china_aqi_estimate', 'relative_humidity', 'temperature_c'].every(
          field => typeof (value.environment_time_eligible as Record<string, unknown>)[field] === 'boolean'))) &&
    ['temperature_c', 'relative_humidity', 'pm2_5', 'pm10', 'nitrogen_dioxide', 'sulfur_dioxide', 'carbon_monoxide', 'ozone', 'china_aqi_estimate', 'environment_latitude', 'environment_longitude']
      .every((field) => value[field] == null || (typeof value[field] === 'number' && Number.isFinite(value[field]))) &&
    (value.china_aqi_primary_pollutant == null || typeof value.china_aqi_primary_pollutant === 'string') &&
    (value.china_aqi_estimate == null || isIntegerInRange(value.china_aqi_estimate, 0, 500)) &&
    ['received_at', 'environment_timestamp', 'weather_timestamp', 'air_quality_timestamp']
      .every((field) => value[field] == null || (typeof value[field] === 'string' &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(value[field]) && Number.isFinite(Date.parse(value[field]))))
}

export async function getSymptomRecords(signal: AbortSignal): Promise<SymptomRecord[]> {
  const response = await fetch(apiUrl('/symptoms'), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error('Could not load symptom observations. Check that the backend is running, then try again.')

  const body: unknown = await response.json().catch(() => null)
  if (!Array.isArray(body) || !body.every(isSymptomRecord)) {
    throw new Error('The backend returned an unexpected symptom response. Please try again.')
  }
  return body
}

function validationErrors(body: unknown): FieldErrors {
  const errors: FieldErrors = {}
  if (!isObject(body) || !Array.isArray(body.detail)) return errors

  for (const detail of body.detail) {
    if (!isObject(detail) || !Array.isArray(detail.loc)) continue
    const field: unknown = detail.loc[detail.loc.length - 1]
    if (typeof field === 'string' && Object.hasOwn(fieldLabels, field)) {
      errors[field as FormField] = typeof detail.msg === 'string'
        ? detail.msg
        : 'Please check this field.'
    }
  }
  return errors
}

export async function saveSymptomRecord(payload: SymptomRecordInput): Promise<SavedSymptomRecord> {
  const controller = new AbortController()
  // Allow the backend's bounded 10-second environmental lookup to finish and save.
  const timeout = window.setTimeout(() => controller.abort(), 20000)

  try {
    const response = await fetch(apiUrl('/symptoms'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    const body: unknown = await response.json().catch(() => null)

    if (response.status === 422) {
      throw new SymptomSubmissionError(
        'Please review the highlighted fields. Your entries have been kept.',
        validationErrors(body),
      )
    }
    if (!response.ok) {
      throw new SymptomSubmissionError(
        'The backend could not confirm the save. Your entries have been kept. Check that the backend is running, then try again.',
      )
    }
    if (
      response.status !== 201 || !isObject(body) ||
      typeof body.id !== 'number' || !Number.isInteger(body.id) || body.id < 1 ||
      typeof body.tnss !== 'number' || !Number.isInteger(body.tnss) || body.tnss < 0 || body.tnss > 12
    ) {
      throw new SymptomSubmissionError(
        'The request was accepted, but the saved record could not be confirmed. Your entries have been kept. Check the backend before submitting again.',
      )
    }

    // TNSS comes directly from the backend; never calculate it from form values.
    return { id: body.id, tnss: body.tnss }
  } catch (error) {
    if (error instanceof SymptomSubmissionError) throw error
    throw new SymptomSubmissionError(controller.signal.aborted
      ? 'The request timed out, so saving could not be confirmed. Your entries have been kept. Check the backend before trying again.'
      : 'Could not reach the backend to confirm the save. Your entries have been kept. Check that it is running, then try again.',
    )
  } finally {
    window.clearTimeout(timeout)
  }
}
