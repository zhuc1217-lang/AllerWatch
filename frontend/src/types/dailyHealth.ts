export type DailyValues = { sleep_duration_hours: number; sleep_quality: number; stress_level: number; exercise_minutes: number; notes: string | null }
export type DailyRecord = DailyValues & { id: number; date: string; is_synthetic: boolean; created_at: string; updated_at?: string | null }
export type DailyList = { calendar_timezone: string; today: string; records: DailyRecord[] }
export type DailyVariable = 'sleep_duration_hours' | 'sleep_quality' | 'stress_level' | 'exercise_minutes'
export const dailyLabels: Record<DailyVariable, string> = {
  sleep_duration_hours: 'Sleep Duration (hours)', sleep_quality: 'Sleep Quality (1–5)',
  stress_level: 'Stress Level (1–5)', exercise_minutes: 'Exercise Minutes',
}
export const qualityOptions = ['Very poor', 'Poor', 'Fair', 'Good', 'Very good'].map((label, i) => ({ value: i + 1, score: String(i + 1), label }))
export const stressOptions = ['Very low', 'Low', 'Moderate', 'High', 'Very high'].map((label, i) => ({ value: i + 1, score: String(i + 1), label }))

export type DailyAssociation = { variable: DailyVariable; n: number; missing_pairs: number; spearman_rho: number | null;
  p_value: number | null; status: AssociationStatus; real_pairs: number; synthetic_pairs: number; distinct_daily_records: number }
export type DailyAssociationsResponse = DatasetMetadata & {
  outcome: 'tnss'; calendar_timezone: string; join_method: 'study_date_and_same_provenance'; minimum_pairs: number;
  p_value_method: 'two_sided_asymptotic_unadjusted'; daily_record_count: number; real_daily_count: number; synthetic_daily_count: number;
  matched_symptom_count: number; missing_daily_symptom_count: number; matched_daily_records: number; daily_records_without_symptoms: number;
  associations: DailyAssociation[]
}
import type { AssociationStatus, DatasetMetadata } from './analysis'
