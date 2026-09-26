# China AQI change verification — 2026-09-26

Completed only the requested China-standard estimate replacement. No deployment or publication. Historical audit reports are unchanged. Method and official references: [CHINA_AQI.md](CHINA_AQI.md).

## Validation

- 576 backend tests passed (two existing dependency deprecation warnings). Existing migration, temporal validity, freshness, real/synthetic separation, public-demo isolation and leakage tests passed. Obsolete US-breakpoint tests were replaced with six-pollutant HJ breakpoint coverage.
- 86 frontend tests passed. TypeScript checking and Vite production build passed; the existing bundle-size warning remains.
- Browser smoke checks passed for Home, Dashboard, expanded History and Analysis against an isolated synthetic demo DB and mocked current provider. The production bundle showed the new names/values/disclaimer, AQI trend/scatter and model coefficient. No JavaScript errors or NaN/Infinity/undefined text; mobile had no horizontal page overflow. No live Open-Meteo availability claim is made.
- Used the production additive migration on the local DB after the migration tests passed. One private backup was created. All original columns of all 141 symptom rows (140 synthetic, one real) and 91 daily rows matched the pre-change capture exactly. Only the six new nullable columns were added. No observations were deleted, replaced, relabelled or backfilled.
- For seed 42/end date 2026-09-18, every original generated symptom, timestamp, medication, PM, weather and provenance value remained identical, excluding the deliberately retired US index. New gases use an independent stream; no outcome or model tuning. The 140-record fixture has 134 complete China AQI values and six missing, with eight records containing any missing environmental value.
- Existing stored snapshots lack the four gases. Their China AQI values remain null, and the active AQI association correctly reports n=0, missing=140. The existing model omits that entirely missing training column. Fresh synthetic results below come from a separate fixture; they were not written over the existing dataset.

## Fixed-protocol model results

All comparisons use the same 111 training / 28 test pairs, chronological order, no random shuffle, training-only preprocessing and no real/synthetic mixing. All predictors precede their targets. The actual local pre-change protocol was evaluated read-only for comparison.

| Metric | Existing stored synthetic, before | Existing stored synthetic, after | Fresh six-pollutant synthetic |
| --- | --- | --- | --- |
| Accuracy | 0.642857 | 0.642857 | 0.642857 |
| Precision | 0.571429 | 0.571429 | 0.571429 |
| Recall | 0.363636 | 0.363636 | 0.363636 |
| F1 | 0.444444 | 0.444444 | 0.444444 |
| ROC-AUC | 0.609626 | 0.614973 | 0.609626 |
| Training-majority baseline accuracy | 0.607143 | 0.607143 | 0.607143 |
| Active predictors | 7 | 6 | 7 |

All three confusion matrices: TN=14, FP=3, FN=7, TP=4. No individual risk output or clinical claims.

| Dataset | Train high / low | Test high / low |
| --- | --- | --- |
| Stored before | 39 / 72 | 11 / 17 |
| Stored after | 39 / 72 | 11 / 17 |
| Fresh fixture | 39 / 72 | 11 / 17 |

Real-only mode still returns insufficient_data. Lifestyle predictors remain excluded for unknown historical availability.

Fresh fixture coefficients (per training standard deviation):

| Feature | Coefficient |
| --- | --- |
| previous_tnss | 0.821909 |
| previous_overall_severity | 0.497063 |
| pm2_5 | 0.339750 |
| pm10 | 0.088900 |
| china_aqi_estimate | -0.383561 |
| relative_humidity | 0.227500 |
| temperature_c | 0.144907 |

## Fresh synthetic exploratory associations

Seed 42; 90 UTC days ending 2026-09-18. These are development pipeline outputs, not clinical findings.

| Exposure | Aligned n | Missing | Temporally excluded | Rho | p |
| --- | --- | --- | --- | --- | --- |
| pm2_5 | 135 | 5 | 0 | 0.205982 | 0.016539 |
| pm10 | 135 | 5 | 0 | 0.223634 | 0.009125 |
| china_aqi_estimate | 134 | 6 | 0 | 0.207624 | 0.016075 |
| relative_humidity | 135 | 5 | 0 | 0.324312 | 0.000124 |
| temperature_c | 135 | 5 | 0 | -0.152824 | 0.076801 |

China AQI lagged results retain the existing approximate backward-only matching rule:

| Lag | n | Missing/unmatched | Rho | p |
| --- | --- | --- | --- | --- |
| 0h | 134 | 6 | 0.207624 | 0.016075 |
| 6h | 12 | 128 | 0.208492 | 0.515512 |
| 12h | 25 | 115 | 0.202530 | 0.331590 |
| 24h | 27 | 113 | 0.360449 | 0.064752 |

## Changed files

48 source/test/documentation files:

```text
PROJECT_SPEC.md
README.md
backend/app/analysis/environment_timing.py
backend/app/analysis/lagged_associations.py
backend/app/analysis/risk_model.py
backend/app/analysis/schemas.py
backend/app/environment_schemas.py
backend/app/migrations.py
backend/app/models.py
backend/app/routers/symptoms.py
backend/app/schemas.py
backend/app/services/china_aqi.py
backend/app/services/environment_service.py
backend/tests/test_analysis.py
backend/tests/test_china_aqi.py
backend/tests/test_demo_data.py
backend/tests/test_environment.py
backend/tests/test_environment_timing.py
backend/tests/test_important_fixes.py
backend/tests/test_lagged_associations.py
backend/tests/test_risk_model.py
backend/tests/test_symptom_environment.py
backend/tests/test_symptoms.py
docs/CHINA_AQI.md
docs/CHINA_AQI_VERIFICATION.md
frontend/src/analysis.ts
frontend/src/api/analysis.ts
frontend/src/api/environment.ts
frontend/src/api/symptoms.ts
frontend/src/components/ChinaAqiNote.tsx
frontend/src/components/DashboardCharts.tsx
frontend/src/components/EnvironmentalExposure.tsx
frontend/src/components/LaggedAssociations.tsx
frontend/src/components/RiskModel.tsx
frontend/src/dashboard.ts
frontend/src/laggedAnalysis.ts
frontend/src/pages/Analysis.tsx
frontend/src/pages/Dashboard.tsx
frontend/src/pages/History.tsx
frontend/src/types/analysis.ts
frontend/src/types/environment.ts
frontend/src/types/riskModel.ts
frontend/src/types/symptoms.ts
frontend/tests/china-aqi.test.mjs
frontend/tests/dashboard.test.mjs
frontend/tests/fixtures/contemporaneous-records.json
frontend/tests/lagged-analysis.test.mjs
scripts/demo_data.py
```

Private SQLite/backup files and test outputs under work/ are ignored local artifacts; never publish them. No dependencies, deployment settings, public-demo guards or unrelated UI styles changed.
