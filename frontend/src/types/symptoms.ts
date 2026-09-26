export const symptomLabels = {
  nasal_congestion: 'Nasal congestion',
  sneezing: 'Sneezing',
  runny_nose: 'Runny nose',
  nasal_itching: 'Nasal itching',
  eye_symptoms: 'Eye symptoms',
} as const

export const fieldLabels = {
  ...symptomLabels,
  overall_severity: 'Overall severity',
  medication_taken: 'Medication taken',
  notes: 'Notes',
} as const

export type SymptomField = keyof typeof symptomLabels
export type FormField = keyof typeof fieldLabels
export type FieldErrors = Partial<Record<FormField, string>>

export type SymptomRecordInput = Record<SymptomField, number> & {
  overall_severity: number
  medication_taken: boolean
  notes: string | null
  is_synthetic: boolean
}

// Only the server-assigned values needed by the save confirmation.
export type SavedSymptomRecord = {
  id: number
  tnss: number
}

export type SymptomRecord = Omit<SymptomRecordInput, 'is_synthetic'> & {
  id: number
  timestamp: string
  received_at?: string | null
  tnss: number
  is_synthetic: boolean
  // Optional for older API responses; null means no stored measurement.
  temperature_c?: number | null
  relative_humidity?: number | null
  pm2_5?: number | null
  pm10?: number | null
  nitrogen_dioxide?: number | null
  sulfur_dioxide?: number | null
  carbon_monoxide?: number | null
  ozone?: number | null
  china_aqi_estimate?: number | null
  china_aqi_primary_pollutant?: string | null
  environment_timestamp?: string | null
  weather_timestamp?: string | null
  air_quality_timestamp?: string | null
  environment_latitude?: number | null
  environment_longitude?: number | null
  // Server-computed time eligibility only; raw values may still be missing.
  // Older responses without these flags remain readable, but cannot form analytic pairs.
  environment_time_eligible?: Record<'pm2_5' | 'pm10' | 'china_aqi_estimate' | 'relative_humidity' | 'temperature_c', boolean>
}
