# China AQI (estimated)

China AQI estimates are calculated according to HJ 633—2026 using modelled pollutant concentrations provided by Open-Meteo. They are intended for exploratory analysis and are not equivalent to AQI published by an official environmental monitoring station.

## Method and source

Reference: **HJ 633—2026, 环境空气质量指数（AQI）技术规定 / Technical specifications on ambient air quality index**, Ministry of Ecology and Environment of the People's Republic of China. Effective **1 March 2026**. [Official standard page](https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/jcffbz/202602/t20260225_1144441.shtml); [official PDF, calculation and realtime reporting provisions](https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/jcffbz/202602/W020260225366493492011.pdf).

`backend/app/services/china_aqi.py` is the only calculator, used by the environmental service and synthetic generator. No frontend, route, analysis module or generator defines a second AQI formula.

For concentration Cp between adjacent breakpoints:

```text
IAQI = ceil(IAQI_lo + (IAQI_hi − IAQI_lo) × (Cp − BP_lo) / (BP_hi − BP_lo))
China AQI estimate = max(the six IAQIs), representation capped at 500
```

Decimal arithmetic avoids floating-point overshoot at exact boundaries. No pre-rounding/truncation of the available model concentrations. IAQI is zero for a measured zero. Values beyond the final breakpoint are represented as 500, except SO2's special hourly maximum of 200. When AQI >50, all pollutants tied at the maximum displayed IAQI are stored as the estimated primary pollutants; otherwise that field is null. No health category, clinical threshold or treatment advice is added.

Realtime breakpoint inputs:

| IAQI | 0 | 50 | 100 | 150 | 200 | 300 | 400 | 500 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PM2.5, µg/m³ | 0 | 35 | 60 | 115 | 150 | 250 | 350 | 500 |
| PM10, µg/m³ | 0 | 50 | 120 | 250 | 350 | 420 | 500 | 600 |
| NO2, µg/m³ | 0 | 100 | 200 | 700 | 1200 | 2340 | 3090 | 3840 |
| SO2, µg/m³ | 0 | 150 | 500 | 650 | 800 | — | — | — |
| CO, **mg/m³** | 0 | 5 | 10 | 35 | 60 | 90 | 120 | 150 |
| O3, µg/m³ | 0 | 160 | 200 | 300 | 400 | 800 | 1000 | 1200 |

SO2 hourly concentration above 800 µg/m³ uses IAQI 200. For example, raw CO 7500 µg/m³ becomes 7.5 mg/m³ and IAQI 75. PM2.5 35.01 µg/m³ gives IAQI 51 after upward rounding. A full estimate is **null unless all six valid non-negative finite pollutant inputs exist**, even if the available pollutants have calculable IAQIs. Partial values are never converted to zero or filled from another time.

## What an hourly snapshot means

Open-Meteo's [Air Quality API documentation](https://open-meteo.com/en/docs/air-quality-api) identifies pollutant values as hourly **instantaneous** model estimates in µg/m³. These approximate the monitored one-hour concentration basis used for realtime reporting in HJ 633; they are not verified monitoring-hour averages. CAMS native temporal/spatial resolution and provider processing vary by domain. This project does not infer missing within-hour values, calculate an official monitoring average, convert ambient gas reference conditions, or claim station compliance.

Request `hourly=pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone`, `past_hours=3`, `forecast_hours=1`, `timezone=UTC`, `timeformat=unixtime`. After both weather/air requests finish, capture retrieval R once. Select the latest air valid time V ≤ R; the existing inclusive freshness rule requires R−3h ≤ V ≤ R. All six readings come from that **same hourly index**. A missing value, malformed array or unexpected unit remains unavailable; no per-pollutant carry-forward or future substitution. Weather keeps its existing current-data request and independent source time.

## Storage and API

The current-environment endpoint and symptom response expose:

| Field | Unit / meaning |
| --- | --- |
| temperature_c | °C, weather provider |
| relative_humidity | %, weather provider |
| pm2_5, pm10 | µg/m³, hourly air provider |
| nitrogen_dioxide | NO2 µg/m³ |
| sulfur_dioxide | SO2 µg/m³; mapped from Open-Meteo `sulphur_dioxide` |
| carbon_monoxide | **Raw CO µg/m³**; division by 1000 happens only in the calculator |
| ozone | O3 µg/m³ |
| china_aqi_estimate | Nullable integer 0–500 |
| china_aqi_primary_pollutant | Nullable text, e.g. `PM2.5, PM10` |
| air_quality_timestamp | Selected hourly source valid time in UTC |
| weather_timestamp | Weather valid time in UTC |
| timestamp on /environment/current | Retrieval completion R |
| environment_timestamp on /symptoms | The stored retrieval completion R; symptom timestamp stays separate |

Environmental fields are server-managed and cannot be supplied in symptom POST bodies. Existing SQLite migrations first back up and then atomically add the six nullable columns (four gases and two AQI fields). Existing rows, original fields, provenance, IDs and the deprecated `us_aqi` column are preserved. The symptom read API retains `us_aqi` solely as an explicitly deprecated compatibility field; current environmental responses and active UI/analysis/model paths do not use it.

No legacy backfill occurs, including synthetic records. Historical US indices or PM alone cannot reconstruct a six-pollutant China estimate. Legacy `china_aqi_estimate` stays null. Existing public demo databases are not automatically reset; new empty public databases use the updated generator under the original isolation/empty-only policy.

## Analysis and simulation

Only the AQI exposure key changes to `china_aqi_estimate`. PM2.5 and PM10 remain separate. Numeric missingness, pair counts, ordinary three-hour alignment, lag matching, provenance/location rules, real/synthetic dataset modes, non-causal language and all statistical methods stay unchanged. Raw snapshots remain distinct from temporally eligible analytical pairs.

The model still predicts next-observation TNSS ≥6 with strictly prior features, the chronological 80/20 split, training-only imputation/scaling and fixed logistic regression. No random shuffling, feature selection on test data or tuning. It has seven environmental/symptom candidates; entirely absent training columns are omitted, including China AQI on legacy-only data. Lifestyle candidates remain excluded for historical-availability reasons.

The generator uses a separate fixed gas random stream (`<seed>:china-aqi-gases`), noisy persistent NO2/SO2/CO/O3, and the central calculator after missingness. It preserves original symptom, time, medication and PM random draws; no gas is added to the symptom burden equation. The existing approximately 6% missing-record mask remains; a missing gas also makes AQI missing. Generated rows are always synthetic. No existing health observations are replaced to improve results.

For reproducible comparisons use seed 42 and end date 2026-09-18 in a **separate initialized development database**, passing its path via the existing `--database` script option. The application never needs a private DB for a public demo. Deployment variables and Render settings remain as documented in [DEPLOYMENT.md](../DEPLOYMENT.md).
