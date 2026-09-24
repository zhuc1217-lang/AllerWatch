import type { DatasetMetadata } from './analysis'

export const modelFeatureLabels = {
  previous_tnss: 'Previous TNSS', previous_overall_severity: 'Previous overall severity',
  pm2_5: 'PM2.5', pm10: 'PM10', us_aqi: 'US AQI', relative_humidity: 'Relative humidity', temperature_c: 'Temperature',
  previous_day_sleep_duration: 'Previous-day sleep duration', previous_day_sleep_quality: 'Previous-day sleep quality',
  previous_day_stress_level: 'Previous-day stress', previous_day_exercise_minutes: 'Previous-day exercise',
} as const
export type ModelFeature = keyof typeof modelFeatureLabels
export type ModelMode = 'real_only' | 'synthetic_only'
export type ClassBalance = { n: number; positive: number; negative: number; positive_percent: number | null; negative_percent: number | null }
export type ModelPeriod = ClassBalance & { target_start: string | null; target_end: string | null; feature_start: string | null; feature_end: string | null }
export type ConfusionMatrix = { true_negatives: number; false_positives: number; false_negatives: number; true_positives: number }
export type ModelMetrics = { accuracy: number; precision: number | null; recall: number | null; f1: number | null; roc_auc: number | null;
  unavailable_reasons: Record<string, string>; confusion_matrix: ConfusionMatrix }
export type ModelCoefficient = { feature: ModelFeature; coefficient: number; train_missing: number; test_missing: number;
  imputation_median: number; scaler_mean: number; scaler_scale: number }
export type RiskModelResponse = DatasetMetadata & {
  dataset_mode: ModelMode; status: 'ok' | 'insufficient_data' | 'unavailable'; reasons: string[];
  target: 'next_observation_tnss_gte_6'; probability_threshold: 0.5; minimum_rows: number;
  split_method: 'chronological_80_20_no_shuffle'; feature_timing: string; daily_health_policy: string;
  model_row_count: number; candidate_pair_count: number; excluded_pair_counts: Record<string, number>;
  daily_candidate_counts: Record<string, number>; class_balance: ClassBalance; training: ModelPeriod; testing: ModelPeriod;
  first_test_prediction_time: string | null; horizon_hours: { min: number | null; median: number | null; max: number | null };
  feature_count: number; candidate_features: ModelFeature[]; used_features: ModelFeature[]; omitted_features: ModelFeature[];
  feature_missing_counts: Record<ModelFeature, number>; metrics: ModelMetrics | null; baseline_class: 0 | 1 | null;
  baseline_accuracy: number | null; coefficients: ModelCoefficient[]; intercept: number | null;
}
