export type DatasetMode = 'real_only' | 'synthetic_only' | 'all'
export type Exposure = 'pm2_5' | 'pm10' | 'china_aqi_estimate' | 'relative_humidity' | 'temperature_c'
export type AnalysisVariable = 'tnss' | 'overall_severity' | Exposure
export type AssociationStatus = 'ok' | 'insufficient_data' | 'insufficient_variation' | 'unavailable'

export type DatasetMetadata = {
  dataset_mode: DatasetMode
  record_count: number
  real_count: number
  synthetic_count: number
  includes_synthetic: boolean
  data_notice: string
  date_start: string | null
  date_end: string | null
  observation_unit: 'individual_observation'
}

export type DescriptiveSummary = {
  n: number
  missing: number
  mean: number | null
  median: number | null
  std: number | null
  min: number | null
  q1: number | null
  q3: number | null
  max: number | null
}

export type DescriptiveResponse = DatasetMetadata & {
  variables: Record<AnalysisVariable, DescriptiveSummary>
  standard_deviation: 'sample_ddof_1'
  percentile_method: 'linear'
}

export type AssociationResult = {
  variable: Exposure
  n: number
  missing_pairs: number
  spearman_rho: number | null
  p_value: number | null
  status: AssociationStatus
}

export type AssociationsResponse = DatasetMetadata & {
  outcome: 'tnss'
  minimum_pairs: number
  p_value_method: 'two_sided_asymptotic_unadjusted'
  temporal_tolerance_hours: number
  associations: (AssociationResult & { temporally_excluded_pairs: number })[]
}

export type AnalysisResponse = { descriptive: DescriptiveResponse; associations: AssociationsResponse }

export type LagHours = 0 | 6 | 12 | 24
export type LagExposure = 'pm2_5' | 'china_aqi_estimate' | 'relative_humidity'
export type LagResult = Omit<AssociationResult, 'variable'> & {
  variable: LagExposure
  lag_hours: LagHours
  real_pairs: number
  synthetic_pairs: number
  distinct_source_records: number
  actual_lag_hours_min: number | null
  actual_lag_hours_median: number | null
  actual_lag_hours_max: number | null
}
export type LaggedResponse = DatasetMetadata & {
  outcome: 'tnss'
  minimum_pairs: number
  p_value_method: 'two_sided_asymptotic_unadjusted'
  lags_hours: LagHours[]
  matching: {
    approximate: true
    tolerance_hours: number
    timezone: 'UTC'
    method: 'same_record_0h_backward_source_time_other_lags'
    exposure_time_fields: Record<LagExposure, string>
    nonzero_source_record_and_retrieval_before_target: true
    cross_provenance_matching: false
    zero_lag_note: string
  }
  results: LagResult[]
}
