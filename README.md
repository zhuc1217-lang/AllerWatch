# AllerWatch

Personal Allergic Rhinitis Health Data Tracker — a local Windows research prototype.

A separate synthetic-only Render portfolio demo is now prepared, **not deployed**. See [DEPLOYMENT.md](DEPLOYMENT.md) for exact settings. Local defaults and the private database are unchanged; do not upload the local database.

## CURRENT BEHAVIOUR

**Research question:** Within one individual, how are environmental exposure estimates and same-date self-reported health factors associated with severity across recorded allergic rhinitis symptom observations?

The implemented analysis unit is a **recorded symptom observation**. Several observations can occur on one date; each eligible observation receives one unit of weight, so more frequently reported days contribute more pairs. DailyHealthRecord values may be reused for multiple same-date symptom observations. This is exploratory within-person observation-level analysis, without retrospective daily averaging.

[PROJECT_SPEC.md](PROJECT_SPEC.md) defines the current protocol. Home, Log Symptoms, History, Daily Health, Dashboard and Analysis use React/TypeScript/Vite/Recharts, FastAPI, SQLAlchemy/SQLite, SciPy/NumPy and scikit-learn. Implemented features include exposure snapshots, synthetic development data, descriptive/Spearman/approximate lag analyses and experimental logistic-regression evaluation.

AllerWatch is **not a medical diagnostic system**, **not a treatment recommendation system**, and **not a clinical decision support system**. No authentication, cloud deployment, wearables, clinical alerts or individual prediction display.

### Windows setup

Tested for the IMPORTANT fixes: **Python 3.12.14; Node v24.19.0**. Use Python 3.12 and a Node version compatible with frontend/package.json (Node 24, or supported Node 22.12+). Dependencies are pinned. No WSL/Docker is required.

Open PowerShell at the source directory; replace the example path if the project moves:

~~~powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio'
py -3.12 -m venv .\backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
npm.cmd --prefix .\frontend ci
~~~

If the Python launcher is absent, use an installed Python 3.12 executable with -m venv .\backend\.venv. Recreate the environment if its base installation moves. No activation or execution-policy change is needed. Runtime requirements are in backend/requirements.txt; requirements-dev.txt adds tests. Network access is needed for initial installation/live retrieval; tests mock providers.

Backend, PowerShell terminal 1:

~~~powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

Frontend, PowerShell terminal 2:

~~~powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\frontend'
npm.cmd run dev
~~~

Open [AllerWatch](http://127.0.0.1:5173). The homepage checks GET /health and shows Backend status: Connected after success. Vite proxies /api to localhost:8000 when VITE_API_BASE_URL is unset; an explicit backend URL instead receives requests directly. Both development servers bind locally. Stop each with Ctrl+C.

~~~powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:5173/api/health'
~~~

### Database and migration

With PUBLIC_DEMO_MODE=false (default) and DATABASE_PATH unset, startup creates missing tables in **data/private/allerwatch.sqlite3**, resolved from the repository directory, and safely migrates older tables. It does not reset or recreate the database. DATABASE_PATH optionally selects a different file. Public demo mode uses a separate database; see the isolation rules in DEPLOYMENT.md.

Before adding nullable columns, the migration makes a consistent private SQLite backup in **data/private/backups/** and applies additions transactionally. Failed backups prevent additions; failed additions roll back. Existing values, IDs, constraints and indexes remain. Repeat startup is idempotent; fresh databases need no migration backup.

I3 adds nullable **symptom_records.received_at** and **daily_health_records.updated_at**. Legacy rows remain **null/unknown**, without invented timestamps. New API symptoms receive a server acceptance time before enrichment, independent of environmental success. New daily records receive created_at and updated_at; accepted edits advance updated_at and preserve created_at. These are server-managed metadata, not an edit history. Never delete the database to resolve migration errors.

### Logging and date rules

Log Symptoms records current symptoms with score controls. Nasal/eye scores are 0–3; overall severity is 0–10. TNSS is calculated by the backend from the **four nasal scores**, excluding eye symptoms. Local forms submit is_synthetic=false; public demo forms submit true, and the server enforces true for every demo submission. Forms omit timestamps, IDs, server provenance and TNSS. GET /config supplies the mode and saves wait until it is known.

Real symptom timestamps later than **server receipt time + 60 seconds** receive HTTP 422. The inclusive allowance covers clock skew, not future scheduling. Offsets normalize to UTC. Omitted time uses the same server clock as received_at. Historical timestamps remain allowed, but a current snapshot is not historical exposure.

Daily Health permits one summary per (date, real/synthetic type). Real POST/PUT dates after **today in the fixed UTC+08:00 study calendar** are rejected. Today is allowed but may be incomplete. The frontend uses the server's today for its maximum date and validation; reload after study-calendar midnight. Literal YYYY-MM-DD dates are not shifted through browser UTC conversion. Explicit synthetic fixtures may use controlled future dates. Existing records remain readable; validation never automatically deletes them.

The symptom submission timeout is **20 seconds**. Errors/uncertain saves retain input and are not retried automatically. A lost response may follow a successful commit; inspect History before manually resubmitting. Entries are not durable drafts across reloads.

### Environmental monitoring and freshness

Optional PowerShell overrides, set before starting the backend:

~~~powershell
$env:ALLERWATCH_LATITUDE = '51.5074'
$env:ALLERWATCH_LONGITUDE = '-0.1278'
~~~

Public London defaults identify a monitoring location, not the user's inferred location. No geolocation or .env loader is used. Monitoring coordinates and the study calendar are independent.

GET /environment/current retrieves temperature (°C), humidity (%), PM2.5/PM10 (µg/m³) and US AQI. Providers return UTC Unix timestamps. Capture one injected UTC clock after both calls complete as retrieval R. Independently require provider valid time V in **[R − 3 hours, R]**, inclusive; no future-valid allowance. This is an engineering freshness policy, not a medical threshold.

Stale, future, missing or malformed source times make that provider unavailable; the other provider may produce a partial response. No usable values gives controlled HTTP 503. Missing remains null, never zero. Valid and retrieval times stay separate. Requests run in parallel with 10-second total, 8-second I/O and 4-second connection limits per provider, without retries.

Homepage refresh and symptom submission retrieve current data. There is no continuous environmental series, background sync, raw-response archive or historical backfill. Environmental failure never blocks valid symptom logging; saved snapshots are never refreshed on read.

### Raw snapshots versus analytic relationships

History, raw descriptive summaries and environmental trends show what was stored, not necessarily conditions at symptom time. **Temporal co-storage does not establish temporal alignment.**

Ordinary associations, Dashboard scatters and lag-0 require, for symptom T, the same record's source V in **[T − 3 hours, T]**, plus known retrieval R with **V ≤ R**, in aware UTC. PM2.5/PM10/AQI use air_quality_timestamp; humidity/temperature use weather_timestamp. Missing time is never inferred. R may follow T; contemporaneous alignment is not prediction availability.

Backdated observations retain later current snapshots but incompatible pairs are excluded. No replacement is fabricated. Per ordinary variable, **record_count = aligned n + temporally_excluded_pairs + missing_pairs**. Missing numerical values count first; otherwise failed/unknown time alignment is a temporal exclusion. Zero remains valid. Dashboard uses backend environment_time_eligible flags; older responses without flags fail closed for relationships while remaining readable as raw data.

### Analysis

Local Analysis defaults to real_only even when insufficient; the public demo page initially selects synthetic_only. API defaults stay real_only. synthetic_only/all are explicit and labelled. Real/synthetic records are never cross-joined for daily/lag matching and never mixed in model training. Dashboard filters apply only to its panels.

- Descriptive statistics use finite raw values: n, missing, mean, median, sample SD, min, Q1, Q3, max. Empty estimates and SD with n<2 are unavailable.
- Spearman uses temporally eligible environmental pairs or same-study-date/provenance daily-health pairs. Minimum 10 complete pairs and variation in both variables; otherwise no rho/p. Unmatched symptoms keep missing lifestyle values. Multiple symptoms reuse daily summaries and receive observation-level weight.
- Approximate lags are 0/6/12/24 hours. Nonzero lags select the latest valid source in [T−lag−3h, T−lag], requiring report/retrieval at or before the target and compatible provenance/location. No future source, interpolation or distant carry-forward. Lag missing counts retain combined unmatched/absent pairs.
- Unadjusted exploratory p-values do not account for within-person dependence or multiple comparisons and do not establish causality. Self-report, reporting frequency, confounding and ambient exposure estimates limit interpretation. No daily averaging is performed.

### Experimental Logistic Regression — implemented

The experiment evaluates whether the **next observation has TNSS ≥6**, using prior information. It is a research pipeline, not a clinical model or individual probability service.

The current synthetic demonstration has **seven active predictors**: previous TNSS, previous overall severity, PM2.5, PM10, US AQI, humidity and temperature. **Sleep duration, sleep quality, stress and exercise remain excluded** because historical availability cannot safely be established. New updated_at does not reconstruct diary versions or enable lifestyle features.

Preserve the conservative report/retrieval availability rule; known received_at adds a lower bound, preventing late-entered information from moving predictions earlier. Legacy receipt stays unknown. Real records without retrieval metadata remain excluded even when receipt is known; only generated synthetic outages have a reporting-time fallback.

Oldest ~80% train, newest ~20% test, without random shuffling. Train-only median imputation and scaling feed fixed logistic regression, seed 42; entirely missing training columns are omitted. Minimum sample/class requirements, baseline, coefficients and undefined-metric rules are in PROJECT_SPEC.md. No target leakage, oversampling, test-set feature selection or tuning for a desired accuracy. Dated verification reports retain historical results; maintenance reports compare against captured baselines.

### Synthetic Development Data

Fictional observations support UI/pipeline development and public synthetic-only screenshots, never clinical findings. Generated records always have is_synthetic=true; real records are preserved. Duplicate protection stops a second complete demo dataset. Generator algorithms were not changed for I1–I6.

After starting the backend once, from the repository root:

~~~powershell
.\backend\.venv\Scripts\python.exe .\scripts\generate_demo_data.py --seed 42 --end-date 2026-09-18
.\backend\.venv\Scripts\python.exe .\scripts\generate_daily_health_demo.py --seed 42
~~~

The symptom generator creates 90 complete past UTC dates with one or two observations daily. The daily generator maps their span to the study calendar, potentially 91 dates. Record seed, end date, source revision and Python version; IDs and creation times are not identical-regeneration guarantees.

Explicit deletion commands:

~~~powershell
.\backend\.venv\Scripts\python.exe .\scripts\delete_demo_data.py
.\backend\.venv\Scripts\python.exe .\scripts\delete_demo_data.py --daily-health
~~~

The first deletes only synthetic symptoms; the second only synthetic daily summaries. Neither removes real records. For public demos use a separate initialized database through --database; never copy the private DB.

### API reference

| Resource | Methods |
| --- | --- |
| /health | GET |
| /config | GET; public demo mode only, no private configuration |
| /symptoms | POST, GET |
| /symptoms/{id} | GET, DELETE |
| /daily-health | POST, GET, dataset=real_only/synthetic_only/all |
| /daily-health/{date} | GET, PUT; explicit is_synthetic where needed |
| /environment/current | GET |
| /analysis/descriptive, /analysis/associations | GET, all three dataset modes |
| /analysis/lagged-associations, /analysis/daily-health-associations | GET, all three modes |
| /analysis/risk-model | GET, real_only/synthetic_only only |

See local [OpenAPI documentation](http://127.0.0.1:8000/docs). Raw environment fields, TNSS and provenance metadata are response-only.

### Verification commands

From backend, use the verified Windows approach with a fresh explicit temporary directory:

~~~powershell
$AllerWatchTestRoot = Join-Path (Resolve-Path ..).Path ('work\pytest-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $AllerWatchTestRoot | Out-Null
.\.venv\Scripts\python.exe -m pytest --basetemp="$AllerWatchTestRoot\tmp" -o "cache_dir=$AllerWatchTestRoot\cache" -q
~~~

The user's previously verified --basetemp="$PWD\.pytest_tmp" command also remains valid when that directory is writable. Do not delete unrelated computed paths to resolve permissions.

From frontend:

~~~powershell
npm.cmd test
npm.cmd run build
npm.cmd run preview
~~~

Production preview is [localhost:4173](http://127.0.0.1:4173); keep the backend running. Node's built-in test runner needs no added framework. Backend tests use isolated SQLite and mocked providers. Existing deprecation/bundle-size notices are separate OPTIONAL maintenance.

### Publication and privacy

Follow [PUBLICATION_CHECKLIST.md](PUBLICATION_CHECKLIST.md). Ignore rules exclude DBs/backups, private/local configuration, generated/raw/exported health data, work, screenshots and local audit/output artifacts. They cannot remove tracked files or erase history. Never share an unfiltered working-directory ZIP.

The application folder was **not a Git repository** at I6 inspection. Git history is not claimed clean, and absence of a private DB from earlier commits elsewhere cannot be established. Actual index/history inspection and a clean-clone install remain publication gates.

## ARCHIVED MILESTONE NOTES

The previous README/specification are preserved unchanged under [docs/archive](docs/archive/README.md). They contain dated results and superseded plans, not current instructions. Step 16/C1 and other dated reports remain unchanged in ignored local outputs/.

## FUTURE WORK

Prospective timing verification, predeclared daily aggregation, independently sampled environmental history, raw-response archiving, exports/notebooks and validation of lifestyle availability remain deferred. No OPTIONAL audit maintenance, final UI redesign or new scientific analysis belongs to I1–I6.

Provider attribution: [Open-Meteo Weather](https://open-meteo.com/en/docs), [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), CAMS. Data are ambient estimates, not personal exposure measurements.

