import type { DailyValues } from './types/dailyHealth'

export function isCalendarDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1]
}

export type DailyDraft = { sleep: string; quality: number | null; stress: number | null; exercise: string; notes: string }
export function dailyDateError(date: string, serverToday: string | undefined): string | null {
  if (!isCalendarDate(date)) return 'Choose a valid calendar date.'
  if (!serverToday || !isCalendarDate(serverToday)) return 'Load the study calendar before saving.'
  return date > serverToday ? 'Choose today or an earlier date in the UTC+08:00 study calendar.' : null
}
export function blankDailyDraft(): DailyDraft { return { sleep: '', quality: null, stress: null, exercise: '', notes: '' } }
export function validateDailyDraft(draft: DailyDraft): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!draft.sleep.trim() || !Number.isFinite(Number(draft.sleep)) || Number(draft.sleep) < 0 || Number(draft.sleep) > 24) {
    errors.sleep_duration_hours = 'Enter sleep duration from 0 to 24 hours.'
  }
  if (draft.quality === null || !Number.isInteger(draft.quality) || draft.quality < 1 || draft.quality > 5) errors.sleep_quality = 'Choose a sleep quality from 1 to 5.'
  if (draft.stress === null || !Number.isInteger(draft.stress) || draft.stress < 1 || draft.stress > 5) errors.stress_level = 'Choose a stress level from 1 to 5.'
  if (!draft.exercise.trim() || !Number.isInteger(Number(draft.exercise)) || Number(draft.exercise) < 0 || Number(draft.exercise) > 1440) {
    errors.exercise_minutes = 'Enter a whole number from 0 to 1440 minutes.'
  }
  return errors
}
export function dailyPayload(draft: DailyDraft): DailyValues {
  if (Object.keys(validateDailyDraft(draft)).length) throw new Error('Invalid daily-health form')
  return { sleep_duration_hours: Number(draft.sleep), sleep_quality: draft.quality!, stress_level: draft.stress!,
    exercise_minutes: Number(draft.exercise), notes: draft.notes.trim() || null }
}
