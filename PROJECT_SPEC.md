# AllerWatch: A Longitudinal Health Data Platform for Allergic Rhinitis

This file is the single source of truth for **current behaviour**, updated 2026-09-26 for China AQI estimates; public-demo deployment preparation remains in place. C1 and IMPORTANT audit fixes I1–I6 remain in place. Archived plans and dated reports are historical evidence, not current requirements.

## CURRENT BEHAVIOUR

### Motivation and research question

Motivated by personal experience with allergic rhinitis, AllerWatch is a local Health Data Science portfolio project exploring variation in self-reported symptoms and estimated ambient conditions.

**Implemented research question:** Within one individual, how are environmental exposure estimates and same-date self-reported health factors associated with severity across recorded allergic rhinitis symptom observations?

The primary implemented analysis unit is **one recorded symptom observation**. Multiple observations can occur on the same day. Each eligible observation contributes one pair, so days with more reports receive more observation-level weight. DailyHealthRecord values may be reused for several same-date symptom observations. This is exploratory within-person observation-level analysis, not a day-level average, population study or causal analysis. No retrospective aggregation is performed to fit the wording.

### Scope and non-goals

Windows local development, one personal dataset, no authentication. A separate synthetic-only public portfolio demo is prepared for Render but has not been deployed. Pages: Home, Log Symptoms, History, Daily Health, Dashboard and Analysis. Implemented: symptom logging/persistence, environmental snapshots, synthetic development data, descriptive statistics, environmental and daily-health Spearman associations, approximate 0/6/12/24-hour lag associations, and experimental next-observation logistic-regression evaluation.

AllerWatch is **not a medical diagnostic system**, **not a treatment recommendation system**, and **not a clinical decision support system**. No clinical alerts, medication recommendations, wearable integration, HealthKit, Apple Watch, mobile app, deep learning, pollen, cloud deployment, chatbot or payments.

### Technology and architecture

React + TypeScript + Vite + Recharts → VITE_API_BASE_URL, or the local same-origin /api proxy → FastAPI → SQLAlchemy + SQLite. FRONTEND_ORIGIN configures an exact CORS origin, alongside localhost development origins. FastAPI's environmental service alone calls Open-Meteo Weather/Air Quality using HTTPX. Pure analysis modules handle NumPy/SciPy/scikit-learn calculations, separate from routes and database models.

Runtime dependencies are pinned in backend/requirements.txt; testing additions are in backend/requirements-dev.txt. Frontend versions are in package.json/package-lock.json. No pandas/statsmodels workflow is currently implemented merely because earlier plans listed those libraries.

Local data defaults to data/private/allerwatch.sqlite3, resolved from the repository location, not the shell working directory. DATABASE_PATH can select another file; relative paths also resolve from the repository root. Public demo mode has a different default and rejects the private location. No live patient data is required to reproduce the application. No background synchronisation, independent environmental time series, historical exposure backfill, raw-response archive, or model-serving/personal prediction endpoint exists.

### Public portfolio demo — prepared, not deployed

PUBLIC_DEMO_MODE defaults to false. When true, use a clean database at DATABASE_PATH (default data/public_demo/allerwatch.sqlite3). Refuse the private directory, aliases of the known private DB, and any existing database without the public-demo marker. Never copy/load the private DB to initialize a demo. Marked demo databases containing real rows refuse startup without deleting or relabelling them.

Reuse the offline synthetic builders with seed 42, 90 past UTC days ending yesterday, and matching daily summaries. Seed in one transaction only when both health tables are empty; never append another dataset on a populated/partially populated database. The Render instructions use a disposable /tmp database and a single instance/worker; resets generate fresh synthetic data. No persistent disk or cloud resource has been created.

GET /config returns only public_demo_mode. The frontend displays “Demo mode — do not enter real health information” and waits for this mode before enabling saves. In demo mode both forms submit fictional data, the server forces is_synthetic=true regardless of the submitted flag, and daily reads/updates target synthetic records. Demo Analysis initially selects synthetic_only; API defaults and statistical calculations stay unchanged. Local mode keeps real-data submission and existing dataset separation. This shared unauthenticated demo is not suitable for private observations; synthetic labels do not anonymize entered text. All scientific disclaimers remain.

The shared Style D UI and existing charts/filters remain. DEPLOYMENT.md specifies Render build/start commands, frontend SPA rewrites, exact environment settings and local fallback. Preparation does not authorize deployment or publication of local files.

### Database model and measurements

**SymptomRecord**
- id; timezone-aware symptom timestamp returned in UTC; nullable server-assigned received_at.
- Nasal congestion, sneezing, runny nose, nasal itching and eye symptoms: strict integers 0–3.
- Overall severity: strict integer 0–10; medication_taken boolean; notes optional.
- is_synthetic boolean, default false.
- TNSS = nasal_congestion + sneezing + runny_nose + nasal_itching, range 0–12. A calculated read-only model property; never independently entered or stored. Eye symptoms and overall severity are excluded.
- Nullable temperature_c (°C), relative_humidity (%), pm2_5, pm10, nitrogen_dioxide, sulfur_dioxide, carbon_monoxide and ozone (all µg/m³).
- Nullable china_aqi_estimate (integer 0–500) and china_aqi_primary_pollutant (text; comma-separated ties, null when unavailable or AQI ≤50).
- us_aqi is a deprecated legacy column/read-only API field; never used in new snapshots, displays, statistics or model features. Existing values are retained unchanged.
- Nullable environment_timestamp = retrieval completion; weather_timestamp and air_quality_timestamp = provider valid times; saved monitoring latitude/longitude.
- API-only environment_time_eligible flags are computed per exposure, not persisted.

**DailyHealthRecord**
- id; literal calendar date; sleep_duration_hours 0–24; sleep_quality integer 1–5; stress_level integer 1–5; exercise_minutes integer 0–1440; optional notes; is_synthetic default false.
- created_at and nullable updated_at are UTC server save times. Future API-created rows set both; accepted PUT changes updated_at and preserves created_at. Invalid requests and reads do not advance them.
- Unique (date, is_synthetic): one real and one separately labelled synthetic diary may coexist without overwriting one another.
- Quality: Very poor/Poor/Fair/Good/Very good. Stress: Very low/Low/Moderate/High/Very high.
- Sleep refers to the main sleep ending on that date; stress/exercise summarize the date, with today potentially incomplete.

SQLite stores UTC datetimes through the existing UTCDateTime adapter and restores aware UTC on reads. Dates never undergo timezone conversion.

### Write-time and provenance policies (I1/I3)

Symptom API validation compares real observation time to an injected server UTC clock. Accept timestamps through **server receipt time + 60 seconds inclusive**, a fixed allowance for clock skew; reject anything later with field-specific HTTP 422 before environmental retrieval or persistence. Historical real timestamps remain allowed. An omitted symptom timestamp is assigned from the same clock as received_at. The web form records symptoms now and never sends a device timestamp or exposes future scheduling.

Real daily dates must be **on or before today's date in the fixed UTC+08:00 study calendar**, without a next-day grace period. Enforce on POST and PUT. Today is allowed as an explicitly potentially incomplete summary. The frontend uses GET /daily-health's server today for its maximum date and validation; reload after study-calendar midnight. The study calendar is independent of browser timezone and configured environmental coordinates.

Explicit synthetic API fixtures may use controlled future dates; local forms create real records, while public demo forms create synthetic demonstration records. The development symptom generator still rejects current/future end dates and simulates complete past UTC days. Validation occurs on writes, not on reading old records; existing future/legacy observations are never automatically deleted or relabelled.

received_at records server acceptance after input validation, before enrichment. It is independent of the caller's symptom timestamp and remains available during environmental outages. Clients cannot supply received_at, created_at or updated_at. Nullable metadata added to legacy rows remains **null/unknown**, without invented historical times. updated_at describes only the latest accepted save, not a version history. Recording these fields does not enable historical lifestyle predictors.

### Safe additive migration

Startup registers both models and creates missing tables. For existing tables, inspect actual columns, obtain a write reservation, make one consistent private SQLite backup (including committed WAL content) through SQLite's backup API, then add missing environmental/provenance columns in one explicit transaction. Roll back column additions on failure; a failed backup prevents additions. Never rebuild/delete the database to migrate.

Nullable migration columns include symptom_records.received_at, daily_health_records.updated_at, and the four additional gases plus china_aqi_estimate and china_aqi_primary_pollutant. Legacy rows retain nulls. Existing values, IDs, constraints and indexes are preserved. Repeat startup is idempotent; fresh databases need no migration backup. Backups remain in data/private/backups and are private. Addition of a missing whole table uses SQLAlchemy create_all.

### APIs and data flow

- GET /health returns status ok.
- GET /config exposes public_demo_mode only; no database paths or secrets.
- POST /symptoms, GET /symptoms, GET /symptoms/{id}, DELETE /symptoms/{id}.
- POST /daily-health, GET /daily-health, GET /daily-health/{date}, PUT /daily-health/{date}. Type is explicit; real is default.
- GET /environment/current.
- GET /analysis/descriptive, /analysis/associations, /analysis/lagged-associations, /analysis/daily-health-associations.
- GET /analysis/risk-model with real_only or synthetic_only; all is rejected for training.

Symptom submission: validate numeric/time input → assign received_at → retrieve current exposure once → save symptoms plus any usable snapshot → return authoritative TNSS. Environmental failure never prevents valid symptom logging. Missing environmental values remain null; zero is never a missing-data code. The browser waits up to **20 seconds** for symptom submission, preserves input on failure/uncertain save and does not retry automatically.

### Environmental monitoring and freshness (I4)

Manually configured coordinates in backend/app/config.py: public London development defaults 51.5074, −0.1278; optional ALLERWATCH_LATITUDE and ALLERWATCH_LONGITUDE environment overrides. They are a monitoring location, not inferred personal location. Both APIs use the same coordinates and request UTC Unix timestamps.

Capture an injected/testable UTC clock **once after both provider requests complete**, retaining this instant as retrieval time R. For each provider independently accept source valid time V only when **R − 3 hours ≤ V ≤ R**, inclusive. The three-hour age limit is a conservative engineering policy for current-condition snapshots, not a clinical threshold. No future-valid grace is used for environmental sources. Missing, malformed, stale or future-valid source timestamps make that provider's measurements and accepted source time unavailable. Do not claim a new retrieval makes an old source current.

Preserve the other provider's usable values in a partial response. If all values are unusable, return controlled HTTP 503. Numeric/unit/range checks remain in place. No replacements, extrapolation or historical backfill. Per-provider total timeout is 10 seconds; HTTPX I/O timeout 8 seconds, connect timeout 4 seconds; providers run in parallel with no automatic retries.

Provider valid time and retrieval time are always separate. Freshness applies to new retrieval only and never rewrites stored snapshots.

### China AQI estimate — HJ 633—2026

China AQI estimates are calculated according to HJ 633—2026 using modelled pollutant concentrations provided by Open-Meteo. They are intended for exploratory analysis and are not equivalent to AQI published by an official environmental monitoring station.

Use one central backend calculator for live snapshots and generated synthetic records. Apply the realtime breakpoint tables with linear interpolation and upward integer rounding, then take the maximum of all six IAQIs, capped at 500. For hourly SO2 >800 µg/m³ use IAQI 200. CO remains raw µg/m³ in DB/API, divided by 1000 inside the calculator for mg/m³ breakpoints. Missing/invalid required pollutant => null estimate and null primary pollutant; preserve other raw values, including real zero. Assign all tied maximum pollutant labels only when AQI >50.

Request six hourly pollutant arrays (Open-Meteo calls SO2 sulphur_dioxide; our field is sulfur_dioxide). Select the latest non-future valid time within [R−3h,R] after both requests finish. All pollutant values must come from that one array index; no borrowing from older/future hours. Malformed/missing arrays or wrong units make that pollutant unavailable. Existing weather timing, freshness, C1, lag and prediction-availability rules remain unchanged.

Open-Meteo describes its hourly concentrations as instantaneous model values. They approximate, rather than verify, the monitored one-hour concentration basis of the standard; provider spatial/temporal modelling further limits interpretation. This is not official station AQI or exact personal exposure. PM2.5 and PM10 remain independent analytical variables.

Keep old us_aqi only as deprecated storage/read-only compatibility. Do not request, display or analyse it. Descriptive statistics, ordinary/lag associations, relationship plots and the model now use china_aqi_estimate. Existing snapshots are not backfilled; old AQI values cannot be converted without all six concentrations. Entirely missing training columns remain omitted, so legacy-only datasets currently fit six environmental/symptom predictors rather than seven. Other statistical methods, splits and provenance modes remain unchanged.

Synthetic generation adds noisy persistent gases on an independent seed stream; it does not modify the existing symptom formula, original random stream, or outcomes to improve results. Approximately 6% of records retain environmental missingness; unavailable required pollutants produce null AQI. Existing synthetic records are not rewritten/reseeded during migration. Public demo first-start/empty-only seeding and private DB isolation are unchanged.

Full methodology/API units: [docs/CHINA_AQI.md](docs/CHINA_AQI.md). Official reference: [HJ 633—2026, Technical specifications on ambient air quality index](https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/jcffbz/202602/t20260225_1144441.shtml), Ministry of Ecology and Environment of the People's Republic of China, effective 1 March 2026.

### Raw snapshots versus analytic contemporaneous exposure (C1)

A historical symptom submitted today may store today's current snapshot. **Temporal co-storage is not temporal alignment.** History, raw descriptive summaries and raw environmental trends retain stored values and label them accurately.

For ordinary Spearman and Dashboard scatter pairs, let T = symptom time, V = that record's provider valid time, R = retrieval completion. Require all three timestamps, **T − 3 hours ≤ V ≤ T**, and **V ≤ R**, in aware UTC. PM2.5/PM10/AQI use air_quality_timestamp; humidity/temperature use weather_timestamp. No missing time is inferred. R may follow T because validation precedes retrieval; this is an approximate contemporaneous comparison, not prediction availability. It is a different reference window from current-provider freshness above.

Each exposure partitions selected record_count into **aligned n + temporally_excluded_pairs + missing_pairs**. Count missing/non-finite TNSS or exposure first; otherwise time failure/unknown metadata is a temporal exclusion. Preserve real zero. Dashboard consumes the backend's read-only time flags and fails closed for older responses without them. No raw value is overwritten, deleted or replaced.

### Analysis protocol

All non-model analyses support real_only, synthetic_only and all, default real_only even when insufficient. Responses identify record count, real/synthetic counts, mode and date range. All mode explicitly labels included synthetic development data. It does not combine different provenance when looking up a lag source or daily summary.

Descriptive statistics cover TNSS, overall severity, temperature, humidity, PM2.5, PM10 and China AQI (estimated): n, missing, mean, median, sample SD (ddof=1), min, Q1, Q3, max. Linear percentiles; null estimates for empty data, SD null when n<2. No imputation, missing-to-zero conversion, interpolation or automatic outlier removal.

Ordinary environmental Spearman uses temporally eligible pairwise-complete observations, minimum **10 pairs**, at least two distinct values in each variable; otherwise insufficient_data or insufficient_variation. Report rho and unadjusted two-sided asymptotic p-value; non-finite output becomes unavailable. P-values are exploratory, do not establish causality, and do not account for dependent repeated observations or multiple comparisons.

Lag analysis is **approximate**, based only on irregular symptom-time snapshots, not continuous exposure history. Lags are 0, 6, 12 and 24 hours for PM2.5, AQI and humidity. Lag-0 uses C1. For other lags set target=T−lag; select the latest same-provenance/source-location valid time within [target−3h,target], requiring source report and retrieval at/before target and valid time at/before retrieval. No future matching, distant carry-forward or interpolation. Equal valid times use latest eligible retrieval then largest ID. Real records need identical known coordinates; synthetic unknown fictional coordinates may match one another. Lag responses retain the existing combined unmatched/missing count and report actual offsets/distinct sources.

Daily health joins use (symptom timestamp converted to UTC+08:00 calendar date, is_synthetic), without a hard symptom-diary foreign key. Multiple symptoms reuse a daily summary; more frequently reported days have more observation-level weight. Unmatched symptom observations remain present with missing lifestyle values. Same-date associations use the same Spearman safeguards. Diary-only dates do not create symptom observations.

### Experimental logistic regression — implemented, not clinical

Target: the NEXT chronological symptom observation has TNSS ≥6, an operational research threshold. Features come from the previous report or earlier and must precede the target; no current-target score/exposure, medication, random shuffle, oversampling or test-set feature selection.

The model has **seven environmental/symptom candidate predictors** (entirely missing training columns are omitted): previous TNSS, previous overall severity, PM2.5, PM10, China AQI (estimated), humidity and temperature. Entirely missing training columns are omitted. All four previous-day lifestyle candidates remain excluded because historical availability cannot safely be proven. New daily updated_at does not reconstruct legacy values or enable lifestyle features in this milestone.

Preserve the conservative availability rule: real records still require environmental retrieval metadata; a known received_at adds a lower bound to report availability. Legacy unknown receipt remains null, with the existing documented report/retrieval proxy unchanged. Only generated synthetic outages have the simulation reporting-time fallback. Do not enable real outage rows merely because a receipt field now exists. Predictions and training labels must have become available before the relevant target/split boundary.

Keep oldest floor(80% of eligible rows) for training, newest remainder for testing. Require ≥30 rows, ≥24 train, ≥6 test, ≥5 targets of each class overall and ≥3 each in training. Train-only median imputation → StandardScaler → fixed LogisticRegression (seed 42). No mixed real/synthetic training. Compare with training-majority baseline. Report accuracy, precision, recall, F1, AUC where defined, confusion matrix, coefficients, class balance and temporal ranges. Undefined metrics are null with reasons. Coefficients are fitted associations, not causal effects. No individual prediction display or clinical recommendation.

### Ethical, privacy and scientific limitations

Local health notes and dates are private. Ignore database files, WAL/SHM files, backups, generated/raw/exported data, environment/private configuration, work, local output reports and browser screenshots. Ignore rules cannot prove a file was never committed. Follow PUBLICATION_CHECKLIST.md before any release; there is no publication authorisation in this milestone.

This is a small N-of-1 observational prototype. Self-reported symptoms, sleep and stress have measurement error; ambient modelled conditions are exposure estimates, not inhaled dose. Reporting frequency and medication/confounding may affect associations. Same-day associations do not establish direction; multiple comparisons and serial dependence limit p-values. Synthetic observations are demonstrations, never clinical evidence. Model performance may not generalise to another person.

### Current completion criteria

Keep existing observations/TNSS/provenance separation intact. I1–I6 completion requires backend and frontend suites plus production build; deterministic future-date, UTC/calendar boundary, freshness, migration and model-availability tests; recomputation of current statistics/model results; verification of old-column data preservation; ignore-rule inspection and a publication checklist. Do not implement OPTIONAL audit recommendations or add new scientific methods.

## ARCHIVED MILESTONE NOTES

The full pre-I1–I6 documents, including original future proposals, dated M1–M12 notes and old completion criteria, are preserved at [docs/archive/PROJECT_SPEC_before_I1-I6_2026-09-23.md](docs/archive/PROJECT_SPEC_before_I1-I6_2026-09-23.md) and [docs/archive/README_before_I1-I6_2026-09-23.md](docs/archive/README_before_I1-I6_2026-09-23.md). Their earlier scope/timeout/schema statements are historical, not current behaviour.

Dated audit, C1 and milestone reports in local outputs/ remain unchanged. Current documentation supersedes conflicting historical plans; historical results are not rewritten.

## FUTURE WORK — NOT IMPLEMENTED OR AUTHORISED HERE

A prespecified daily sampling/aggregation protocol, independent environmental time series, historical exposure retrieval, raw-response archive, export workflow, research notebook, adjusted inference, and prospective lifestyle-feature availability validation remain future work. Any activation of lifestyle predictors requires a separately documented protocol and sufficient prospective evidence; last-edit metadata is not historical version reconstruction.

A clean clone and actual Git history must be inspected before publication. Do not claim legacy provenance can be recovered retrospectively. No OPTIONAL audit maintenance, idempotency redesign or final UI redesign is included in I1–I6.

