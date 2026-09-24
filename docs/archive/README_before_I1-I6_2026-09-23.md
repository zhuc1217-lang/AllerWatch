# AllerWatch

Personal Allergic Rhinitis Health Data Tracker

Research prototype for exploring symptom and environmental data.

## Current scope

This implements milestones 1–12 in [PROJECT_SPEC.md](PROJECT_SPEC.md), the repository's source of truth: application scaffold, symptom API, logging interface, History, current environmental display, environmental snapshots, clearly flagged synthetic development data, a descriptive Health Data Dashboard, descriptive/Spearman analysis, approximate hourly lagged associations, a daily health/sleep diary, and an experimental next-observation logistic regression. Confirmatory inference remains deferred.

- React, TypeScript, and Vite render a minimal homepage.
- FastAPI exposes `GET /health`, returning `{"status":"ok"}`.
- The homepage checks the API and displays `Backend status: Connected` on success. A failed check shows `Unavailable` and a retry button.
- SQLAlchemy persists symptom records in SQLite, with Pydantic input validation.
- The API supports creating, listing, retrieving, and deleting symptom records. TNSS is calculated from the four nasal scores and is read-only.
- The homepage links to **Log Symptoms**, where large selectable controls record a current symptom observation and save it through the existing API.
- **History** displays expandable observations, time filters, and a Recharts TNSS line chart. Home, Log Symptoms, History, Daily Health, Dashboard, and Analysis are linked through simple navigation.
- The homepage's **Environmental Exposure** section displays current temperature, humidity, PM2.5, PM10, and US AQI from Open-Meteo through FastAPI.
- Each new symptom observation stores the available environmental snapshot; upstream failures leave nullable fields without blocking symptom logging. History displays these saved estimates.
- Offline development scripts generate a reproducible 90-day synthetic dataset and safely delete only synthetic records.
- **Dashboard** shows the latest selected observation, dataset completeness, four time-series charts and three exploratory scatter plots, with shared time/type filters and explicit synthetic labels.
- **Analysis** summarises seven variables and explores five environmental associations with TNSS, using separate real/synthetic/all dataset selections and explicit limitations.
- **Lagged Environmental Associations** compares PM2.5, AQI and humidity with TNSS at approximate 0/6/12/24h offsets, explicitly reporting matching coverage and limitations.
- **Daily Health** records and updates a daily summary of sleep, stress and exercise, with labelled recent history and four same-date associations in Analysis.
- **Experimental Symptom Risk Model** adds a fixed chronological logistic-regression evaluation after the existing analyses, with a majority-class baseline and explicit research-only warnings.
- Wearable integration, clinical predictions, and authentication are not implemented.

AllerWatch is not a medical diagnostic system, treatment recommendation system, or clinical decision support system.

## Prerequisites

- Windows and PowerShell.
- Node.js 24 LTS with npm (Node.js 22.12 or later in the 22 series is also supported).
- Python 3.12 or later. The setup below also supports the existing bundled Python runtime on this computer when Python is not on PATH.
- Internet access for the initial dependency installation and live Open-Meteo retrieval. Symptom logging/history remain usable without Open-Meteo access.

The commands use `npm.cmd` and the virtual environment's Python executable directly. No PowerShell execution-policy change or virtual-environment activation is needed.

## Initial setup

Open PowerShell and go to the repository root. If you move or clone the repository, replace this path with its new location:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio'
```

Create the backend virtual environment using an available Python installation:

```powershell
if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .\backend\.venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .\backend\.venv
} else {
    $AllerWatchPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $AllerWatchPython)) {
        throw 'Install Python 3.12 or later, reopen PowerShell, and retry.'
    }
    & $AllerWatchPython -m venv .\backend\.venv
}
```

Install backend and frontend dependencies from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
npm.cmd --prefix .\frontend ci
```

The virtual environment depends on its base Python installation. If that installation moves or is removed, recreate the environment. The bundled-runtime fallback is specific to this computer; a normal Python installation is sufficient elsewhere.

## Run the backend — PowerShell terminal 1

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open. The health endpoint is [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

Startup automatically creates the `symptom_records` table in `data/private/allerwatch.sqlite3`, relative to the repository root. The database path does not depend on the current PowerShell directory. Existing records are preserved across restarts. The database and its private directory are excluded by `.gitignore`.

The table is created only when the application starts, not when its module is imported. Initialisation creates missing tables; it does not migrate an older schema or reset existing data. No manual database setup is needed for this milestone.

## Run the frontend — PowerShell terminal 2

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\frontend'
npm.cmd run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). With the backend running, the homepage displays:

```text
AllerWatch
Personal Allergic Rhinitis Health Data Tracker
Research prototype for exploring symptom and environmental data.
Backend status: Connected
```

The status is checked on page load and when retrying a failed connection. It is not a continuous uptime monitor; reload the page to check again after stopping a previously connected backend.

Press **Ctrl+C** in each terminal to stop its server. Both servers bind to the local machine only.

## Log a symptom observation

From the homepage, select **Log Symptoms**, or open [http://127.0.0.1:5173/log-symptoms](http://127.0.0.1:5173/log-symptoms).

1. Select a score for each of the five symptoms: **0 = None**, **1 = Mild**, **2 = Moderate**, or **3 = Severe**.
2. Select overall severity from **0 to 10** and **Yes** or **No** for medication taken. Choices start blank so a missing answer is not mistaken for a zero.
3. Optionally add notes, then select **Save symptom record**.
4. A confirmed save shows **Symptom record saved successfully.** and **TNSS: X / 12**. Select **Start another symptom record** to open a blank form.

These are real observations (`is_synthetic: false`). The backend assigns the current UTC timestamp when saving; the form is for symptoms now, not retrospective daily summaries. Required answers are validated before submission. Keyboard users can navigate the radio groups with Tab and arrow keys.

The frontend sends JSON to `POST /api/symptoms`. The existing Vite proxy removes `/api` and forwards it to `POST http://127.0.0.1:8000/symptoms`. The request includes the five symptom scores, overall severity, medication, optional notes, and `is_synthetic: false`. It does not include an ID, timestamp, or TNSS. The confirmation displays `tnss` directly from the backend's 201 response. Eye symptoms remain separate from TNSS; the frontend does not calculate TNSS.

While saving, controls are disabled to prevent repeat submissions. Validation failures identify the relevant field; connection and API failures show a readable message and preserve all entries. Requests time out after ten seconds and are not retried automatically. If saving cannot be confirmed, check the backend before manually resubmitting: a lost response can occur after a record has already been stored. Entries are kept in the open form after an error, but are not saved as drafts across page reloads or navigation.

## Verify the connection

In another PowerShell terminal:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:5173/api/health' | ConvertTo-Json -Compress
```

Both commands should print `{"status":"ok"}`. The second command checks the frontend's proxy as well as the backend.

The frontend requests `/api/health` on its own origin. Vite forwards it to `http://127.0.0.1:8000/health`, removing `/api`. This keeps local development requests on the same browser origin without adding a permissive CORS configuration. The five-second frontend timeout prevents a check from remaining pending indefinitely.

## Current environmental exposure

The homepage fetches `GET /api/environment/current`. Vite forwards this to FastAPI's `GET /environment/current`, whose route calls the dedicated environmental service. That service requests the Open-Meteo Weather and Air Quality APIs in parallel, validates their timestamps, units, and values, and returns a small JSON response. No symptoms, notes, or medication information are sent to Open-Meteo.

HTTPX was already installed for backend tests. Its existing pinned version, `0.28.1`, and its runtime dependencies are now in `backend/requirements.txt` so a normal runtime installation supports the service. No new HTTP library or frontend package was added. Existing checkouts can update from the repository root with:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

### Monitoring location

`backend/app/config.py` is the single configuration source. `DEFAULT_LATITUDE` and `DEFAULT_LONGITUDE` use a public London development example (51.5074, -0.1278). They represent the environmental monitoring location, not the user's detected location. There is no browser geolocation request. The homepage shows the configured coordinates; Open-Meteo may return data from a nearby model grid cell.

To choose another location, stop the backend with Ctrl+C, set **both** environment variables in its PowerShell terminal, and restart it. Replace the example values below with your chosen monitoring coordinates. Use decimal points and valid ranges: latitude −90 to 90 and longitude −180 to 180.

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
$env:ALLERWATCH_LATITUDE = '51.5074'
$env:ALLERWATCH_LONGITUDE = '-0.1278'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

These variables apply to that PowerShell session and child processes. `.env` files are not automatically loaded. Without overrides, the central defaults are used. Invalid coordinate settings produce a controlled unavailable response; check them if retrieval remains unavailable.

### Measurements and times

| Response field | Display/unit | Source variable |
| --- | --- | --- |
| `temperature_c` | Temperature, °C | Weather `temperature_2m` |
| `relative_humidity` | Relative humidity, % | Weather `relative_humidity_2m` |
| `pm2_5` | PM2.5, µg/m³ | Air Quality `pm2_5` |
| `pm10` | PM10, µg/m³ | Air Quality `pm10` |
| `us_aqi` | US AQI, index without categories | Air Quality `us_aqi` |

Both requests specify `timezone=UTC` and `timeformat=unixtime`. The service decodes Unix seconds as UTC and serialises timestamps with `Z`. The UI also displays environmental times explicitly in UTC, even if History uses the browser's local timezone.

- `timestamp`: time retrieval completed; displayed as **Last updated: … UTC (retrieved)**.
- `weather_timestamp`: the weather provider's valid time, or null if no weather value is usable.
- `air_quality_timestamp`: the air-quality provider's valid time, or null if no air-quality value is usable.

These source times may differ; they are not replaced by retrieval time. Values are current modelled outdoor conditions, not daily averages or measured personal exposure. Attribution links to Open-Meteo and CAMS appear below the values.

### Availability and manual verification

The endpoint returns HTTP 200 with `status: "available"` when all five values are usable, or `status: "partial"` when at least one is usable. Missing/invalid fields are null and display **Unavailable**. Real numeric zeros remain zero. Failed requests, malformed source data, invalid timestamps, or incorrect units never generate invented readings.

Each provider has an 8-second HTTP I/O timeout, a 4-second connection timeout, and a 10-second overall deadline. One failed provider does not discard data from the other. When neither provides any usable measurements, FastAPI returns HTTP 503 with `{"detail":"Environmental data are temporarily unavailable."}`; the rest of the backend remains operational. The frontend has a 15-second deadline, readable error text, and a retry button.

With the backend and frontend running, these PowerShell commands verify the direct endpoint and Vite proxy:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/environment/current' | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri 'http://127.0.0.1:5173/api/environment/current' | ConvertTo-Json -Depth 4
```

Open [the homepage](http://127.0.0.1:5173) to see the five measurements and times. Loading the homepage or selecting **Refresh environmental data** requests new data. M6 also requests and stores a snapshot on symptom submission. There is no automatic polling, server cache, or historical backfill. A failed homepage refresh shows an unavailable state rather than presenting previous values as newly updated; it never changes saved symptom snapshots.

Provider references: [Weather API](https://open-meteo.com/en/docs), [Air Quality API and attribution](https://open-meteo.com/en/docs/air-quality-api).

## Review symptom history

With both servers running, select **History** from Home or Log Symptoms, or open [http://127.0.0.1:5173/history](http://127.0.0.1:5173/history). If updating an existing checkout, run `npm.cmd ci` from the frontend directory first to install the pinned Recharts and matching `react-is` dependency.

History loads all records through `GET /api/symptoms`, which the existing Vite proxy forwards to `GET /symptoms`. Each row shows date, time, TNSS, overall severity, and medication status. Select a row, or focus it and press Enter, to expand all five individual symptom scores and the other recorded fields, including notes. Dates and times use the browser's local timezone, named on the page. Missing notes display **No notes provided.** Synthetic records are labelled explicitly.

- **All records** is the default and includes every returned observation.
- **Last 7 days** and **Last 30 days** use inclusive rolling windows of 7 or 30 elapsed 24-hour periods, ending when records load or the filter is selected. Future timestamps are outside those recent windows but remain visible in All records.
- Filtering is performed locally on parsed timestamps; changing filters does not send another API request. Reload History to fetch newly recorded observations. These are observation windows, not a daily diary recall convention.
- The list sorts newest first, with descending ID for equal timestamps. The chart uses the same subset sorted oldest first, preserving multiple records per day and actual time spacing.
- Chart scores come directly from the API's `tnss`; no frontend TNSS sum, daily averaging, smoothing, or missing-as-zero values are used. The vertical axis stays at **0–12**. Hover or use the chart's keyboard navigation to inspect values; the expandable records provide the same values as text.
- Gaps longer than 24 hours break connecting lines using a null display marker, without adding an observation. Synthetic observations use a separate grey dashed series, while real observations use green. No line connects the two kinds of records.

An empty database displays **No symptom records yet. Log your first symptom observation to begin building your longitudinal dataset.** An empty time filter has a separate message and a **Show all records** button. Loading, connection failures, timeouts, and malformed responses have explicit states; errors offer **Retry loading history** and are not reported as an empty dataset.

## Health Data Dashboard

With the usual backend and frontend running, open [Dashboard](http://127.0.0.1:5173/dashboard), or follow its navigation link from Home, Log Symptoms or History. No new setup or dependency is required.

The page loads the existing `GET /symptoms` through Vite's `/api/symptoms` proxy, with loading/error/retry states. **Refresh observations** fetches again. Dashboard does not call Open-Meteo, add an endpoint, or write to SQLite; it displays the saved environmental snapshots. TNSS is always the value returned by the backend.

- **Shared filters:** Last 7/30/90 days or All data, combined with All/Real only/Synthetic only. All data and All types are the defaults. Recent ranges are inclusive rolling windows ending at load or filter-selection time, measured in elapsed 24-hour periods. The time filter reuses History's implementation. Changing filters operates locally without another request. Latest snapshot, summary, every chart and the accessible table use the same subset.
- **Latest observation:** newest timestamp, then highest ID for ties, within the selection. It shows TNSS, overall severity, PM2.5, US AQI, timestamp and observation type. Missing environmental values display Unavailable; an older value is never substituted.
- **Dataset summary:** selected total, real and synthetic counts, actual selected date range, and separate missing PM2.5/AQI/humidity counts. The page also shows selected versus loaded counts. Browser-local dates/times are labelled with the timezone; a UTC observation can fall on another local calendar date.
- **Time series:** TNSS (fixed 0–12), PM2.5 (µg/m³), US AQI (index) and humidity (%) each have separate labelled axes. X is the symptom observation time, not the environmental provider valid time. Multiple observations per day, including timestamp ties, remain separate. Points and straight line segments show raw observations without smoothing or averaging. Lines break at missing values, type changes and gaps exceeding 24 hours; they do not interpolate unavailable measurements.
- **Scatter plots:** pair TNSS with PM2.5, US AQI or humidity from the same record only when numerical values exist and the backend's contemporaneous time check passes (C1 rule below). Report total symptom observations, aligned pairs, temporal exclusions and missing numerical pairs separately. At least two eligible pairs are required; otherwise the requested insufficient-data message replaces the chart. The plots show no fitted line, correlation coefficient, p-value or causal claim. Raw snapshot trends, tables and History retain all stored values; they are not automatically aligned exposures.
- **Real versus synthetic:** the All view shows **Includes synthetic development data** when applicable. Real observations use circles/solid lines; synthetic observations use diamonds/dashed lines, text labels and tooltip provenance. Synthetic values are demonstration fixtures, not patient observations. Scatter points are never joined.
- **Missing and sparse data:** null/absent values remain missing, while measured zero stays zero. All-missing environmental series have an explicit unavailable message; one available time-series point remains visible. Empty datasets and no filter matches have distinct messages rather than broken plots. No requested date range is filled with invented observations.
- **Accessibility:** titled charts, labelled axes/units, readable tooltips, keyboard navigation and **View selected observations as a table** expose exact values without relying on colour. TNSS tooltips include time, overall severity and medication; scatter tooltips include time, TNSS, the environmental value and observation type. The table also identifies missing values and record provenance.

The page displays: **Dashboard visualisations are exploratory and do not establish causal relationships. Synthetic observations are used for development and demonstration.** Dashboard remains descriptive; the separate Analysis page provides M9 summaries/associations and M10 approximate hourly lag results. Prediction is not implemented.

## Descriptive statistics and exploratory associations (Milestone 9)

Open [Analysis](http://127.0.0.1:5173/analysis). The default is **Real data**, even if there is only one observation or none. Select **Synthetic data** explicitly to inspect the fictional demonstration dataset. **All data** includes both types with separate counts and an inclusion notice. Analysis uses all stored dates and is independent of Dashboard filters. Every observation remains separate, including multiple observations on one day.

After updating this milestone, install the new pinned NumPy/SciPy dependencies and start the backend in PowerShell:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second PowerShell window:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\frontend'
npm.cmd run dev
```

Two read-only endpoints accept `dataset=real_only`, `synthetic_only`, or `all`; omission defaults to real_only, and invalid modes return HTTP 422:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/descriptive?dataset=synthetic_only' | ConvertTo-Json -Depth 6
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/associations?dataset=synthetic_only' | ConvertTo-Json -Depth 6
```

React requests both endpoints through Vite's `/api` proxy when the selection changes. FastAPI reads stored symptom records, obtains TNSS from the unchanged model property, applies the selected provenance filter, and delegates calculations to `backend/app/analysis/`. No Open-Meteo request, database migration, record write, generator change, or frontend statistical calculation occurs. The frontend cancels obsolete requests, validates responses, and retries failed loads on demand; it does not display results from the previous dataset under a new label. If metadata differs between the two responses because records changed during loading, it asks for a refresh.

**Descriptive conventions:** TNSS, overall severity, PM2.5, PM10, US AQI, humidity, and temperature each report valid n, missing count, mean, median, sample SD (`ddof=1`), minimum, Q1, Q3, and maximum. SD is unavailable with fewer than two values; empty variables have null estimates. Q1/Q3 use NumPy's linear quantile convention, which does not fill missing observations. Missing or non-finite values are excluded, never converted to zero. JSON contains null for unavailable results. Actual measured zeros remain valid.

**Pairwise conventions (C1 correction, 2026-09-22):** TNSS is paired separately with each of the five environmental variables in the same stored record, using only analytic contemporaneous exposures that pass the time rule below. For every exposure, the selected `record_count` partitions into **n + temporally_excluded_pairs + missing_pairs**. First count missing/non-finite TNSS or exposure as missing; among numerically complete pairs, count failed or unverifiable time alignment as temporally excluded. There is no double counting. Only aligned pairs enter Spearman. At least **10 aligned complete pairs** and two distinct values in each paired variable are required. This is a practical interface threshold, not evidence of adequate power. Status is `insufficient_data`, `insufficient_variation`, or `unavailable` when no estimate is returned; otherwise it is `ok`. Tables explain these statuses and the rho chart omits unavailable coefficients instead of drawing zeros.

**Exact contemporaneous eligibility rule:** let T be symptom time, V the provider's source valid time, and R the snapshot retrieval completion time. Require all three timezone-aware timestamps, **T − 3 hours ≤ V ≤ T**, and **V ≤ R**, using UTC instants and inclusive boundaries. PM2.5, PM10 and US AQI use `air_quality_timestamp`; temperature and humidity use `weather_timestamp`. R is `environment_timestamp`. Missing source/retrieval metadata, a future-valid source, a source older than three hours relative to T, or retrieval before source time fails the check. Never substitute symptom time for a missing source time. R may follow T because symptom validation precedes retrieval, as in the existing lag-0 rule: this is an approximate contemporaneous comparison, not a claim that the value was available for prediction at T. Historical aligned pairs are not judged against today's clock.

**Raw versus analytic:** temporal co-storage does not establish temporal alignment. A backdated symptom submitted today may retain today's raw snapshot, but that incompatible pair is excluded from ordinary associations, Dashboard scatter plots and lag-0. No record or exposure value is deleted, overwritten, imputed or replaced; no historical Open-Meteo exposure is invented. History labels these as raw stored snapshots. Descriptive environmental statistics and raw trends still summarise stored values. `backend/app/analysis/environment_timing.py` supplies the single time rule. Symptom API responses expose read-only per-variable `environment_time_eligible` flags; Dashboard uses them rather than calculating a second rule. The flags describe time eligibility, so numerical completeness must also be checked. Older API responses without flags remain readable, but their numerical pairs are excluded as temporally unverified. No database migration is needed.

**Interpretation:** Spearman rho describes an exploratory monotonic association, not causation. P-values are unadjusted two-sided asymptotic SciPy estimates. P-values are exploratory and are not evidence of causality. Multiple environmental variables are being examined, so results should be interpreted cautiously. Repeated observations from one person are temporally dependent, contrary to the usual independent-observation p-value assumptions; small samples and tied ranks further limit the approximation. The p-values are displayed as requested for exploratory pipeline development, not confirmatory or clinical evidence. There are no significance stars, automatic significance claims, corrections, or treatment interpretations. Small p-values use scientific notation; a computational zero is displayed as `< 0.0001` rather than asserting an exact probability of zero.

Stored environmental snapshots are ambient estimates, not exact personal exposure measurements or daily averages. Ordinary associations now enforce the documented C1 temporal rule; incompatible backdated snapshots remain raw data only. The API reports observation date bounds as timezone-aware UTC; the page names the browser timezone used for display. There is no daily aggregation, imputation, missing-value interpolation, outlier deletion, or adjustment for confounding; M10 adds the separately documented lag section below. Synthetic associations describe the generator's assumptions; the generator must not be tuned to obtain desired p-values.

Method references: [SciPy Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html), [NumPy sample SD](https://numpy.org/doc/stable/reference/generated/numpy.std.html), [NumPy percentiles](https://numpy.org/doc/stable/reference/generated/numpy.percentile.html).

**Milestone 9 verification, 2026-09-20:** all **224 backend tests** (including the existing 193), **39 frontend tests**, the TypeScript/production build, and `pip check` passed. Browser checks verified all three dataset modes against the current database, exact displayed coefficients, missing/zero and constant-variable handling, empty/small datasets, loading/errors/retry, malformed responses, rapid selector changes, mobile layout, and existing navigation/pages. No browser warnings, errors, or write requests occurred. The database schema and all 141 records (140 synthetic, 1 real) retained their full-field checksum. Existing non-failing warnings remain: two backend dependency deprecations and Vite's bundle-size notice. See `outputs/MILESTONE_9_REPORT.md` for observed synthetic results and the exact change list.

## Approximate lagged environmental associations (Milestone 10)

Research question: **Do environmental exposures measured before symptom reporting show different associations with allergic rhinitis symptom severity?** Open the existing [Analysis page](http://127.0.0.1:5173/analysis) and use the same Real data / Synthetic data / All data selector. The new section compares PM2.5, US AQI and relative humidity with TNSS at **0, 6, 12, 24 hours only**. Its matrix shows rho, valid n, missing pairs, p-value and status; expand coverage details for actual time offsets, real/synthetic pair counts and distinct source records. The fixed muted colour scale represents signed rho, not significance or risk. A failed lag request has its own retry and does not remove the existing descriptive statistics.

The database contains **only snapshots saved at symptom reporting**, not an independent environmental time series. Existing synthetic observations are sampled 1–2 times per day, with median spacing 13.48 hours (range 2.47–37.29). Consequently this analysis is **approximate**, not an exact measurement of 6h/12h/24h exposure. No environmental history is fetched or fabricated, and no observations or generator code are changed.

**Exact matching rule (fixed before inspecting associations):**

1. Work in timezone-aware UTC. SQLite's existing UTC adapter restores timezone information; the matcher rejects naive datetimes. T is the symptom record timestamp. PM2.5/AQI use `air_quality_timestamp`, humidity uses `weather_timestamp`. These are source valid times, while `environment_timestamp` is download completion. Missing source times are never guessed from symptom times.
2. **0h** uses only the same record's finite exposure, with source valid time in the closed interval `[T − 3h, T]`. Require a retrieval timestamp consistent with source valid time. Its download normally finishes after symptom validation (the generator models three seconds later); this does not move the environmental valid time into the future. Lag 0 is a contemporaneous descriptive comparison, not an as-of prediction. Future or stale source valid times are rejected, and another record is not substituted. After C1, ordinary associations use this same time check for all five exposures. The existing lag response still includes unmatched temporal pairs in its `missing_pairs`; ordinary associations separately report temporal exclusions and missing numerical pairs.
3. **6/12/24h:** target = T − lag. Choose the latest finite source valid time in `[target − 3h, target]`. The source symptom timestamp **and retrieval completion must both be at or before target**, and valid time must not exceed retrieval completion. Thus a later report/retrieval cannot retrospectively supply earlier exposure. No observation after target is accepted just because it is closer. Ties use latest eligible retrieval, then highest record ID.
4. Use the same real/synthetic type for outcome and exposure even in All data. Nonzero real matches require identical known stored monitoring coordinates. Synthetic records may match their shared unknown fictional location; real records with unknown location cannot establish a comparable source. A source with this particular variable missing is skipped; an older finite value may be used only within the same fixed window.
5. If no eligible exposure exists, the pair is missing. Never convert it to zero, interpolate, extend the window, or use a distant observation. Nominal 6/12/24h correspond to actual offsets **6–9 / 12–15 / 24–27h**. The three-hour tolerance deliberately preserves missingness instead of spanning most of a sparsely sampled day.

Spearman uses the existing M9 implementation and **minimum 10 complete pairs**, with null estimates for insufficient pairs or constant inputs. Each exposure/lag has its own n and missing count; its subset may differ from other lags. A source can be reused for several symptom observations, so n is not the number of independent exposure measurements. Actual offset min/median/max and distinct source counts make this visible. More positive rho describes increasing ranks together in that matched subset; negative rho describes opposing ranks. Neither identifies a causal effect or a confirmed delay.

**Multiple exposure-lag combinations are explored, so individual p-values should be interpreted cautiously.** The 12 combinations share repeated observations and sometimes sources; unadjusted asymptotic p-values do not account for that dependence or establish causality. The page states: **These lagged results are based on synthetic development data and are not clinical findings.** All-data mode instead explicitly identifies synthetic inclusion. Do not choose a delay or tune the generator to obtain a desired correlation.

Read-only API (default `real_only`, invalid modes return 422):

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/lagged-associations?dataset=synthetic_only' | ConvertTo-Json -Depth 8
```

Responses include dataset metadata, matching assumptions/tolerance/time fields, an approximate flag and all 12 results. No new dependency or migration is needed; existing Windows run/test commands remain valid.

**Milestone 10 verification, 2026-09-20:** **265 backend tests**, **50 frontend tests**, and the TypeScript/production build passed. All 224 previous backend tests still pass. Deterministic tests include every lag, future valid/report/retrieval timestamps, tolerance boundaries, missing source times/values, real/synthetic/location separation, timezone offsets, positive/negative/constant cases and correct counts. Browser checks covered all three modes, 12 exact result cells, insufficient/empty data, missing versus genuine zero, negative coefficients, errors/retry, stale-response cancellation, coverage details, mobile scrolling and existing pages. Audit of 601 current-data pairs found all source valid times at or before target; all 197 nonzero-lag pairs additionally had source report and retrieval at or before target. No cross-provenance match occurred. Database schema and all 141 records remain unchanged. Existing dependency-deprecation and bundle-size warnings remain non-failing. See `outputs/MILESTONE_10_REPORT.md` for full results and exact files changed.

## Daily Health and Sleep (Milestone 11)

Open [Daily Health](http://127.0.0.1:5173/daily-health). Select a date, enter sleep duration in **hours** (decimals such as 6.5), select sleep quality and stress using the labelled 1–5 controls, and enter exercise in whole **minutes**. Notes are optional. Sleep refers to the main sleep ending on the selected date; stress and exercise summarize that day. Today's summary may still be incomplete.

The form loads a real record for the selected date before enabling edits. Save creates a new record or updates that date's existing record, preserving its ID. A confirmed response shows **Daily health record saved successfully.** Failed saves retain the entries. If another client has already created that date, the duplicate response offers an explicit **Load saved record** action before updating. Recent history shows the latest 14 summaries, newest first; synthetic demo entries are clearly labelled and read-only in the form. The form always submits real observations.

### Date and uniqueness conventions

The study calendar is fixed at **UTC+08:00** in `backend/app/config.py`, independently of browser timezone or the environmental monitoring coordinates. The API provides the study's current date for the form default. Daily dates are literal `YYYY-MM-DD` calendar labels, stored as SQL DATE and never passed through JavaScript timezone conversion. `created_at` remains an aware UTC audit timestamp. Changing the study calendar after collection would change joins and requires an explicit protocol/migration decision; it is not an automatic browser or location setting.

The database enforces one row per **(date, is_synthetic)**. There can be one real summary and one separately labelled fictional summary on the same date, so demo data never block or overwrite a real diary. A second row of the same type/date returns **409**. PUT cannot change date, ID, provenance or created_at. No foreign key or copied lifestyle fields are added to symptom records.

### Daily API and additive migration

| Method and path | Behavior |
| --- | --- |
| `POST /daily-health` | Create, 201; duplicate date/type, 409 |
| `GET /daily-health?dataset=real_only` | `{calendar_timezone, today, records}`; newest first; also supports `synthetic_only` and `all` |
| `GET /daily-health/YYYY-MM-DD` | Real record for this date; absent, 404 |
| `PUT /daily-health/YYYY-MM-DD` | Replace editable values on an existing real record; absent, 404 |
| `GET /analysis/daily-health-associations?dataset=real_only` | Four same-day associations and matching/provenance metadata; also supports both other modes |

Date-specific GET/PUT can explicitly select `?is_synthetic=true` for development API use. POST defaults `is_synthetic` to false. Sleep duration is finite 0–24; sleep quality and stress are integers 1–5; exercise is an integer 0–1440. All four numeric values are required; notes may be null. Invalid input returns **422**. PUT accepts the four values and optional notes, without a date or provenance field in its body.

On updated-backend startup, SQLAlchemy's checked `Base.metadata.create_all()` adds only the missing `daily_health_records` table and its constraints/index. It is idempotent; existing tables and observations are not rebuilt or dropped. The existing symptom/environment schema remains unchanged. The schema was inspected before this change, and a private SQLite backup was taken before daily-data generation (after reload had created the empty new table): `data/private/backups/allerwatch-before-daily-data-20260921T062313.sqlite3`. This backup includes the original symptoms plus the empty daily table. Migration tests confirm original records survive repeated initialization.

### Exact analysis join and limitations

For each selected symptom observation, convert its aware UTC timestamp to **UTC+08:00**, take the calendar date, and look up a daily row with that date **and the same is_synthetic value**. This is a left join performed in the analysis package without changing stored records. A missing matching diary leaves all four lifestyle values as `None`; the symptom remains in the denominator. An unmatched daily row creates no symptom outcome. Even All data never pairs a real symptom with a synthetic diary or vice versa.

The existing [Analysis page](http://127.0.0.1:5173/analysis) includes **Daily Health Associations** under the same Real / Synthetic / All selector. Spearman uses complete pairs separately for sleep duration, sleep quality, stress and exercise, the existing **10-pair minimum**, and null estimates for insufficient data or constant inputs. Missing values are not zero, imputed, or interpolated. Responses include n, missing pairs, rho, p-value, status, source counts and distinct matched daily summaries.

Several same-day symptom observations reuse the same daily summary. Thus n counts symptom pairs, **not independent days**. P-values are unadjusted exploratory approximations and do not account for this dependence or multiple comparisons. Self-reported sleep is not clinically measured sleep, stress is subjective, and confounding may affect associations. Same-day data do not establish temporal direction or causality. Synthetic results describe simulation assumptions, not clinical findings. Existing environmental and lag definitions are unchanged.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/daily-health?dataset=all' | ConvertTo-Json -Depth 5
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/daily-health-associations?dataset=synthetic_only' | ConvertTo-Json -Depth 6
```

### Synthetic daily health data

Start the updated backend once to create the new table. From the repository root, generate daily development records alongside the **existing** synthetic symptoms:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\generate_daily_health_demo.py --seed 42
```

This separate offline extension never regenerates or updates symptoms and never calls Open-Meteo. It covers the inclusive study-date span of existing synthetic symptoms: currently **91 days, 2026-06-21 to 2026-09-19**, because conversion from the original 90 UTC days crosses an extra study-calendar date. All new rows are synthetic, with null notes. Generation stops if any synthetic daily row already exists. `--database` can target an existing initialized test database. A fixed seed, unchanged synthetic symptom inputs, calendar and generator reproduce values/dates; database IDs and creation timestamps may differ.

Sleep is mostly 5–9 hours, quality and stress are noisy scores, and exercise is 0–120 minutes with many zero days. Small predefined contributions from the existing synthetic daily TNSS average create demonstration associations, with substantial independent variation. This is reverse-conditioned simulation, not a model of lifestyle causing symptoms. Parameters were set before inspecting results and were not tuned to obtain particular p-values.

To remove **only synthetic daily-health rows**, explicitly select:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\delete_demo_data.py --daily-health
```

This prints the count before deletion and the committed count afterward, preserves real daily entries, and leaves **all symptom records** unchanged. The existing delete command **without this flag** continues to delete only synthetic symptoms, leaving every daily record unchanged. To reset both demo datasets, explicitly run both deletion commands, then generate symptoms first and daily data second. Each deletion is transactional; no table or ID reset occurs.

**Milestone 11 verification, 2026-09-21:** 307 backend tests (all previous 265 plus 42 new), 60 frontend tests, and the frontend production build pass. Browser verification covers actual form POST/PUT on an isolated database, duplicate recovery, failed-save input retention, date loading errors, date consistency in a different browser timezone, mobile layout and all three analysis modes. Real data currently have no daily matches and show insufficient data. The 140 synthetic symptoms match 82 distinct daily summaries; 9 of the 91 daily records have no symptom observation. Existing 141 symptom rows (1 real, 140 synthetic) and their schema retain the pre-change checksum. See `outputs/MILESTONE_11_REPORT.md` for exact files and observed results. No machine learning is included.

## Experimental Logistic Regression (Milestone 12)

Open [Analysis](http://127.0.0.1:5173/analysis) and select **Synthetic data** to view **Experimental Symptom Risk Model** after the existing descriptive, environmental, lagged and daily-health analyses. Real data remains the default and currently returns an honest insufficient-data state. All data is disabled for model training; the existing descriptive/association analyses can still use it. No daily diary, symptom, environmental or synthetic generator data are changed by this experiment.

**Research prototype only. This model is not intended for medical diagnosis or clinical decision-making.** Synthetic performance demonstrates the modelling pipeline and is not clinical evidence. TNSS >= 6 is a predefined operational threshold, not a validated clinical severity cutoff.

### Feature construction in plain English

Take two consecutive symptom observations of the same type, in time order. Once the earlier report's environmental download has finished, use that earlier report's TNSS, overall severity and available environmental values to predict whether the next observation will have TNSS at least 6. Never use the next observation's scores or environment as predictors. The interval to the next report varies; this does not predict a fixed next-day outcome.

More precisely, the prediction point is `max(previous.timestamp, previous.environment_timestamp)`, in aware UTC. It must be strictly earlier than the next symptom timestamp; a delayed retrieval that reaches/passes that target excludes the pair. Simulated outages with no retrieval timestamp use the simulated report time with missing environment. Real rows without a known report/retrieval availability marker are conservatively excluded. Pairs touching duplicate report timestamps are excluded as ambiguous. Pairing occurs before these checks; a rejected pair is not bridged to a later target. A recorded source valid time must be within the three hours ending at the previous report timestamp, and retrieval must be known and completed by the prediction point. Otherwise that exposure is missing. No new or future exposure measurements are fetched.

There are 11 candidate columns: previous TNSS, previous overall severity, PM2.5, PM10, AQI, humidity, temperature, and four previous-day lifestyle variables. The current fitted experiment uses **7**. Medication is excluded because its timing is ambiguous.

**Why daily health is excluded from this first prediction model:** a date in the past is not proof that values were available then. Candidate diaries would need to be from the calendar day before the prediction point (fixed UTC+08:00), with matching real/synthetic type and creation before prediction. The table permits updates but has no update/version history. Furthermore, all current synthetic daily rows were created on September 21, after the historical symptoms ended September 18 UTC. Those values cannot safely enter earlier predictions. The four daily candidates therefore remain missing and are reported as omitted, even if a diary has an earlier creation date, because later edits cannot be ruled out. M11 same-day descriptive associations remain unchanged. No fictitious historical timestamps or modified synthetic data are introduced.

### Temporal split, preprocessing and evaluation

Keep the earliest `floor(0.8 × usable pairs)` for training and the final pairs for testing. No random train/test shuffling is used. The split is fixed before inspecting performance. All training target labels must have become available by the first test prediction point. Within the later test period the model stays fixed; a symptom observed earlier in that period may serve as the previous observation for the next prediction. This is sequential one-step evaluation, not forecasting an entire unseen future series at once.

Require at least 30 usable pairs, 24 training pairs, 6 test pairs, 5 high and 5 low targets overall, and 3 of each class in training. These are engineering safeguards, not proof that sample size is adequate. A single-class test set still permits accuracy and other mathematically defined measures, but ROC-AUC is null with an explanation. Precision/recall/F1 with undefined denominators are also null rather than fabricated values.

Remove columns entirely missing **in training** because no median can be learned. Fit one `SimpleImputer(strategy='median') → StandardScaler → LogisticRegression` pipeline on training rows only, then only transform/predict the test rows. Missing predictors are not replaced with arbitrary zeros. Fixed settings are default L2 regularization, C=1, lbfgs, max_iter=1000 and random_state=42; classification uses probability >= 0.5. There is no tuning, feature selection using test performance, resampling, class weighting or test-set refitting. This training-only preprocessing follows the [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

The baseline always predicts the **training** majority class (ties -> low), evaluated on the same test targets. The API/UI show train/test counts, periods and class balance; accuracy, precision, recall, F1 and valid ROC-AUC; TN/FP/FN/TP; and standardised coefficients. Coefficients describe conditional fitted log-odds per training SD and are not causal effects. PM2.5, PM10 and AQI are related inputs, limiting separate coefficient interpretation. The coefficient axis is not constrained to the correlation range [-1,1]. No individual probability display or persisted model is added.

### Current data results

The unchanged synthetic symptoms yield **139 usable pairs**: **111 training** (39 high / 72 low) and **28 testing** (11 high / 17 low). Overall high prevalence is 50/139 = **35.97%**. Training target times span **2026-06-22 14:35:18 to 2026-08-30 21:43:21 UTC**; test targets span **2026-08-31 08:08:53 to 2026-09-18 19:31:24 UTC**. The first test prediction is issued at **2026-08-30 21:43:24 UTC**. Prediction intervals span 2.46–37.29 hours, median 13.48 hours.

| Test measure | Value |
| --- | ---: |
| Training-majority baseline accuracy | 0.607143 |
| Logistic Regression accuracy | 0.642857 |
| Precision | 0.571429 |
| Recall | 0.363636 |
| F1 | 0.444444 |
| ROC-AUC | 0.609626 |

TN=14, FP=3, FN=7, TP=4. The model correctly classified 18/28 targets versus the baseline's 17/28: one additional correct classification, not evidence of clinical benefit. The data, seed and hyperparameters were not adjusted to improve these results. Exact coefficients, preprocessing summaries and files changed are reported in `outputs/MILESTONE_12_REPORT.md`.

There is one real symptom observation, yielding zero adjacent pairs; `real_only` returns `status='insufficient_data'` with reasons and null model results. Real and synthetic observations are never combined for training.

### Windows commands and API

From the repository root, install the newly pinned scikit-learn runtime dependencies into the existing backend environment:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m pip check
```

Restart the backend if it was running without reload. Existing Windows startup commands remain unchanged. The read-only endpoint retrains the same small fixed experiment on request; it writes no records or model files and uses no Open-Meteo calls:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/risk-model?dataset=synthetic_only' | ConvertTo-Json -Depth 8
Invoke-RestMethod 'http://127.0.0.1:8000/analysis/risk-model?dataset=real_only' | ConvertTo-Json -Depth 8
```

Default mode is `real_only`. `dataset=all` and unknown modes return 422. Responses include feature availability/missingness, omitted columns, exclusion reasons, class balance, UTC split periods, baseline, metrics and training-only preprocessing summaries. Convergence failures return a controlled unavailable state.

**Limitations:** this is a small N-of-1 repeated-observation experiment, not independent participants. Self-reported symptoms have measurement error; ambient exposure is an estimate. Recorded report/retrieval times do not provide a complete immutable historical audit. Synthetic observations are not clinical evidence. Coefficients and performance establish no causal relationship and may not generalise to another person. There is no clinical validation, calibration assessment, medication advice or prospective deployment.

**Verification, 2026-09-22:** all **339 backend tests** (including the existing 307), **68 frontend tests**, frontend build and `pip check` passed. Browser verification checked live synthetic metrics/coefficients, real insufficiency, disabled mixed training, single-class unavailable metrics, API/malformed-response handling, stale-response cancellation, mobile layout, and no non-finite output. All original symptom and daily-health records/schema are preserved. Existing backend dependency deprecations and Vite's bundle-size notice remain non-failing. This milestone stops before final project audit or UI redesign.

## Symptom API

M6 adds nullable, server-managed environmental snapshot fields to symptom responses. Existing symptom request fields and TNSS calculation remain unchanged.

The API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) while the backend runs.

| Method and path | Success response |
| --- | --- |
| `POST /symptoms` | 201 with the saved record, generated ID, and TNSS |
| `GET /symptoms` | 200 with an array, newest timestamp first; IDs descending for ties |
| `GET /symptoms/{id}` | 200 with one record |
| `DELETE /symptoms/{id}` | 204 with no response body |

Unknown record IDs return 404. Invalid request bodies or IDs return FastAPI's 422 validation response. An empty database returns `[]` from `GET /symptoms`.

### Record fields

- `nasal_congestion`, `sneezing`, `runny_nose`, `nasal_itching`, and `eye_symptoms`: required integers from 0 to 3.
- `overall_severity`: required integer from 0 to 10, recorded separately from TNSS.
- `medication_taken`: required JSON boolean.
- `notes`: optional text or null; defaults to null.
- `is_synthetic`: JSON boolean, default false.
- `timestamp`: optional timezone-aware observation timestamp; defaults to the current UTC time. Supplied timestamps are normalised to UTC and returned with a UTC timezone. Naive timestamps are rejected.
- `id`: generated by the database and returned only in responses.
- `tnss`: calculated response value, `nasal_congestion + sneezing + runny_nose + nasal_itching`, with range 0–12. It is not a database column or a create-request field. Eye symptoms and overall severity do not contribute to it.
- `temperature_c` (°C), `relative_humidity` (%), `pm2_5` and `pm10` (µg/m³), `us_aqi` (index): nullable environmental snapshot values, returned by POST and both GET symptom endpoints.
- `environment_timestamp`: nullable UTC retrieval-completion time. `weather_timestamp` and `air_quality_timestamp`: separate nullable UTC provider valid times.
- `environment_latitude` and `environment_longitude`: nullable monitoring coordinates used for this snapshot, retained even if configuration later changes.

### Environmental snapshot flow and timestamps

User submits symptoms → FastAPI validates the request → the existing environment service retrieves current weather and air quality → SQLAlchemy saves symptoms and the available snapshot in one row → History displays the stored combined record.

No database write transaction is held during the external lookup. Its existing parallel provider requests each have a 10-second total limit; no automatic retry is added. Failures or missing values leave null fields and still allow HTTP 201 for a valid symptom save. Available values from a successful provider are retained. The frontend allows 20 seconds for submission so the lookup can finish and SQLite can save. Database failures are still reported as save failures, rather than incorrectly reporting success.

The symptom timestamp defaults to UTC at validation, before retrieval begins. All environment timestamps are stored as UTC and returned with an explicit UTC offset (`Z`); History labels environmental times in UTC and symptom times in the browser timezone. The environmental retrieval time is distinct from each provider's valid time. A backdated API observation keeps its original symptom timestamp but receives **current** conditions at submission, not historical exposure. Compare these times before any future analysis. There is no retrospective backfill or daily aggregation in this milestone.

Snapshots are **environmental exposure estimates** at the configured monitoring location near reporting time, not exact personal exposure measurements or evidence that an environmental variable caused symptoms. History has separate Symptoms and Environmental Exposure sections; null/omitted values show **Unavailable**, while a stored numeric zero displays zero. Reading History or refreshing current conditions never updates a saved snapshot. Snapshot fields are response-only and are rejected if supplied in POST.

### Safe SQLite migration

Stop the backend with Ctrl+C before updating the project, then restart with the usual PowerShell command:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Startup inspects `PRAGMA table_info(symptom_records)`. For an existing table missing snapshot columns, it reserves the SQLite write lock, makes a consistent backup through Python's SQLite backup API using a separate read connection, and adds only missing nullable columns in one explicit transaction. No table is deleted or recreated. Existing IDs, timestamps, symptoms, notes, indexes, and constraints are retained; old environment values are null. Repeated startup is a no-op when the columns exist, and a fresh database gets the complete schema directly.

Backups are timestamped files in `data/private/backups/`, excluded from version control along with the personal database. If backup or migration fails, startup stops and schema changes roll back; resolve the reported file/lock issue and restart. **Do not delete the database to fix migration errors.** For recovery, stop all backend processes and retain both the current database and backup; restoring an older backup can discard records added since that backup.

References: [SQLite ADD COLUMN](https://www.sqlite.org/lang_altertable.html#alter_table_add_column), [Python SQLite backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).

Score strings, fractional scores, and booleans in score fields are rejected instead of converted. Boolean fields accept `true` or `false`, not strings or integers. Sending an ID, TNSS, or another unknown field in a create request returns 422.

M2 stores timestamped observations and allows multiple records per day. M3 adds a form for current observations. The timestamp does not independently establish a previous-day recall window. Daily aggregation and a daily diary form remain future work. The list API includes real and synthetic records with their flags; future research analyses must exclude synthetic data explicitly.

### PowerShell example

With the backend running, this example creates a **synthetic** record, reads it, and then deletes it. It changes the local application database; automated tests below use separate temporary databases instead.

```powershell
$AllerWatchRecord = @{
    timestamp = '2026-09-17T08:30:00+08:00'
    nasal_congestion = 3
    sneezing = 2
    runny_nose = 1
    nasal_itching = 0
    eye_symptoms = 2
    overall_severity = 7
    medication_taken = $true
    notes = 'Synthetic API example'
    is_synthetic = $true
} | ConvertTo-Json

$AllerWatchCreated = Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:8000/symptoms' `
    -ContentType 'application/json' -Body $AllerWatchRecord

$AllerWatchCreated | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/symptoms'
Invoke-RestMethod -Uri "http://127.0.0.1:8000/symptoms/$($AllerWatchCreated.id)"
Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8000/symptoms/$($AllerWatchCreated.id)"
```

The created record has `tnss: 6` and a normalised timestamp of `2026-09-17T00:30:00Z`.

## Synthetic Development Data

Synthetic observations are **fictional development data, not real patient observations or research evidence**. Use them for UI/dashboard testing, later statistical-pipeline development, and clearly labelled demonstration screenshots. Every generated record has `is_synthetic: true`; the existing symptom form continues to create `is_synthetic: false` records. The API exposes the flag. History already labels synthetic records and draws a separate synthetic TNSS series. Review screenshots before sharing: the same database can also contain private real observations.

The symptom scripts below use the existing SymptomRecord model directly, without calling `POST /symptoms` or Open-Meteo. The separate M11 daily-health extension is documented above. Start the updated backend at least once so its normal initialisation/migration has completed. Scripts require an existing current-schema database; a missing file or incompatible schema produces an error rather than creating or resetting anything.

From the repository root in Windows PowerShell:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio'
.\backend\.venv\Scripts\python.exe .\scripts\generate_demo_data.py --seed 42
```

The default target is the existing `data/private/allerwatch.sqlite3`, resolved from the script location rather than the working directory. `--database 'C:\path\to\existing-demo.sqlite3'` can target an already initialised isolated development database. No virtual-environment activation or PYTHONPATH configuration is needed.

The default range is 90 complete **UTC** dates ending yesterday in UTC, with one or two observations each day at varied morning, afternoon, or evening times on a fictional UTC clock. This avoids future observations. History converts symptom timestamps to the browser timezone, so its displayed date/time may differ. To reproduce every non-ID field on another day, keep the seed, end date, generator code and Python version fixed:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\generate_demo_data.py --seed 42 --end-date 2026-09-18
```

Generation **stops without adding records if any synthetic record already exists**, including synthetic records made manually through the API. It never silently appends another full dataset. To remove synthetic data, run:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\delete_demo_data.py
```

Deletion prints the number to remove before executing its strictly filtered delete, then the committed deletion count and preserved real-record count. Without flags it deletes **all symptom records with `is_synthetic: true` in the selected database**, not just the most recent generated batch; real symptoms and all daily-health rows are untouched. Use `--daily-health` instead for daily-only deletion. It is safe to run when no synthetic records exist. Use the same `--database` option on both commands if selecting another database. Run generation again after deletion to regenerate. SQLite IDs can differ; no ID reset occurs. Each operation uses a transaction; concurrent generator runs cannot both pass the duplicate check.

The generator prints record count, date range, seed, preserved real-record count, and the number of records with one or more missing environmental measurements. Refresh History or `GET /symptoms` to load the new observations.

### Simulation assumptions and limits

- Temperature and humidity change gradually; pollution episodes persist across several observations. PM10 tracks PM2.5 with additional variation. Simulation bounds are 5–35 °C, 25–95% humidity, PM2.5 1–100 µg/m³ and PM10 up to 160 µg/m³; these are fictional scenario bounds, not clinical thresholds or a location-specific climatology.
- Small pollution/humidity contributions combine with independent persistent symptom variation, component/observation noise and occasional flares. TNSS continues to use the existing four-nasal-score property, excluding eyes. Relationships are simulation assumptions, not findings or a model fitted to a patient. No correlations are calculated.
- Medication is sampled more often at higher symptom scores, but has exceptions. Medication never changes generated symptoms; no treatment effectiveness is modelled. Notes are usually null.
- Approximately 6% of records have one or more missing environmental measurements. Missing values use `None`/JSON `null`. Source timestamps are cleared for complete source outages; the retrieval timestamp is cleared for a total outage. Symptoms remain complete.
- Environmental timestamps are simulated near the observation time, with weather/air valid times rounded down to quarter-hour/hour boundaries. All are UTC. Coordinates stay null: this dataset represents no actual monitoring site, and none of its values come from Open-Meteo.
- Synthetic US AQI is an approximate PM2.5-only index using [EPA concentration breakpoints](https://aqs.epa.gov/aqsweb/documents/codetables/aqi_breakpoints.html) as a plausibility guide. It is not a regulatory daily AQI or NowCast, does not account for other pollutants, and has no medical interpretation. AQI shares PM2.5's signal rather than contributing a second independent symptom effect.

## Run all backend tests

From PowerShell, install the pinned development dependencies and run the complete backend suite:

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\backend'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
New-Item -ItemType Directory -Force .pytest_tmp
.\.venv\Scripts\python.exe -m pytest --basetemp="$PWD\.pytest_tmp" -q
```

No running server is needed. FastAPI TestClient starts the application with an isolated temporary SQLite file for each test. Tests cover valid records, score validation, defaults, UTC timestamps, calculated/non-editable TNSS, retrieval, deletion, database constraints, and persistence after restarting the application. They do not seed, clear, or modify the personal database.

**Windows verification, 2026-09-18:** the user reported that the original plain `pytest -q` command did not work in their PowerShell session. After recreating the test-only `.pytest_tmp` directory, the explicit `--basetemp="$PWD\.pytest_tmp"` command above succeeded: **82 passed, 3 warnings**. Use this explicit local temporary directory for future test instructions on this machine. Reserve it for disposable test data and exclude it from version control.

The three warnings shown were two third-party deprecation warnings and a pytest cache write-permission warning (`WinError 5` under `.pytest_cache`). The tests passed despite these warnings. The screenshot does not establish the cause of the earlier failed run. Directory cleanup or permission changes are not part of the routine command and should not be performed automatically just because they appeared in the troubleshooting screenshot.

**Milestone 3 verification:** all 82 backend tests also passed using a fresh explicit temporary directory and cache under the ignored `work/` folder, with two dependency deprecation warnings. The assistant's execution environment could not access the existing `.pytest_tmp` and `.pytest_cache` folders, so this run used separate directories without changing their permissions. The user's verified command above remains the default.

Browser verification used a separate SQLite database and a production frontend preview. Checks covered homepage navigation and health status, real API saves, backend-returned TNSS, required-field and API validation, input retention after connection/server errors, duplicate submission prevention, starting another record, keyboard operation, and desktop/360-pixel mobile layouts. No browser test observations were added to the personal database.

**Milestone 4 verification:** all 82 existing backend tests passed again, using a fresh explicit temporary directory and cache under `work/`, with the same two dependency warnings. No backend source, schema, or TNSS calculation changed. History browser checks used 12 API-created observations in an isolated SQLite database, then saved a thirteenth observation through the existing form. Checks covered newest-first ordering, timestamp ties, inclusive 7/30-day boundaries, matching chart points, the 0–12 axis, local time display, details, empty states, loading, API-error retry, malformed responses, mobile layout, and Home/Log Symptoms regression checks. The personal database was not used.

**Milestone 5 verification, 2026-09-19:** all **138 backend tests** passed, including the existing 82 tests and 56 environmental/configuration cases, with the same two dependency deprecation warnings. A fresh explicitly selected temporary directory/cache under `work/` avoided the assistant environment's existing-folder permission issue. Environmental tests use `httpx.MockTransport`, not live Open-Meteo. They cover request parameters, UTC times, success, missing/zero/invalid values, units, malformed bodies, HTTP/connection errors, per-request and total timeouts, partial results, unavailable responses, configuration, and unchanged symptom persistence.

The frontend build and nine History data tests passed. Separate manual verification of a locally running `GET /environment/current` obtained all five live values from Open-Meteo. Browser checks verified live desktop/mobile display, loading, partial data, genuine zeros, unavailable/retry states, malformed responses, frontend timeout, and the existing logging/History workflow. Verification used an isolated symptom database; no test observations were added to the personal database.

**Milestone 6 verification, 2026-09-19:** all **166 backend tests** passed: the 138 existing cases (with the obsolete no-enrichment expectation updated) plus 28 snapshot/migration cases. All external transports are mocked offline. Checks cover full/partial snapshots, SQLite persistence and restart, timeout/connection/HTTP/malformed failures, missing values and real zeros, validation before retrieval, server-managed fields, unchanged TNSS with eye symptoms excluded, old-record readability, idempotent migration, backup preservation, WAL mode, and rollback on migration/backup failure. Tests used fresh explicit temporary/cache directories under `work/`; the user's verified PowerShell command remains the default. The same two dependency deprecation warnings remain.

The frontend production build and all nine History data tests passed. The existing Vite bundle-size warning remains; no unrelated optimisation was added. Manual verification used a separate SQLite database: a live Open-Meteo enriched POST returned 201 with all five values, and a simulated upstream timeout produced environmental 503 while form submission still returned 201 with null snapshot values. Browser checks verified combined History details, desktop/mobile layouts, UTC labels, zeros versus Unavailable, older responses without environment fields, unchanged TNSS chart, and homepage health/current-condition display. No verification observations were inserted into the personal database.

The existing personal database was migrated with a pre-change backup: its one original observation retained the exact same original-field checksum, and its new fields are null. Both database and backup passed SQLite integrity checks. Ignored manual verification helpers and results are under `work/`; private database backups remain under `data/private/backups/`.

**Milestone 7 verification, 2026-09-19:** all **193 backend tests passed**, including the existing 166 and 27 new synthetic-data cases, with the same two dependency deprecation warnings. Tests cover score/environment bounds, temporal coverage, missingness, medication exceptions, unchanged TNSS, repeatability, GET response flags, duplicate and concurrent-run protection, transaction rollback, real-record preservation, and Windows script execution from another working directory. No live Open-Meteo dependency or new package was added.

The application database completed the requested generate → API read → delete → API read → regenerate cycle. The final dataset contains **140 synthetic observations** over **2026-06-21 through 2026-09-18 UTC** (90 days), generated with **seed 42**. **8 records** have one or more missing environmental measurements. The **1 real observation** retained exactly the same full-field checksum at every step; deletion removed all 140 synthetic records and no real record. Regeneration reproduced every non-ID field. SQLite integrity checks passed, and GET /symptoms returned the synthetic flags and correct TNSS values. The final demo dataset remains available for the next milestone. Browser verification confirmed 140 Synthetic record labels, the separate real record, and the existing chart legend/environment detail display without UI changes. No dashboard or analysis was implemented.

## Run frontend data tests

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\frontend'
npm.cmd test
```

The test command uses Node's built-in test runner and TypeScript stripping, without a new framework dependency. It runs nine existing History tests plus 18 Dashboard tests (27 total). Coverage includes filter boundaries and intersections, UTC offsets/DST, timestamp ties, non-mutating preparation, latest-record selection, missingness counts, genuine zero values, variable-specific scatter pairing, TNSS authority, provenance, chart gaps and empty/single-record domains.

**Milestone 8 verification, 2026-09-19:** all **193 backend tests**, **27 frontend tests**, and the frontend TypeScript/production build passed. Existing warnings remain: two backend dependency deprecations and the Vite chunk-size warning. No package dependency or lockfile changed.

Browser verification used the existing 140 synthetic and 1 real observations to check all seven charts, per-variable point counts, every time filter, real/synthetic filtering, latest snapshot and summary, tooltips, keyboard access, table values and 360 px layout. Browser-only fixtures covered three same-day observations, real zeros, missing PM2.5/AQI/humidity, one observation, all-missing series, no filter matches, empty data, loading, HTTP/network errors, malformed responses and timeout/retry. Navigation preserved Home health, Log Symptoms and History. No browser errors or warnings occurred. Dashboard made no write requests; all 141 stored records retained their exact pre-change full-field checksum. No statistical analysis or further milestone was started.

## Build and preview the frontend

```powershell
Set-Location 'C:\Users\carcar\Documents\Codex\2026-09-17\i-want-to-build-a-portfolio\frontend'
npm.cmd run build
npm.cmd run preview
```

The build checks TypeScript and writes static assets to `frontend/dist/`. Preview opens a local server at [http://127.0.0.1:4173](http://127.0.0.1:4173). Keep the backend running for its connection check and symptom logging; the preview server uses the same API proxy. The static files alone do not provide a backend or an API proxy. Deployment is outside this milestone.

The M4 production build passes. Recharts increases the bundled JavaScript enough to trigger Vite's 500 kB chunk-size warning. This is a non-failing size warning; bundle optimisation is deferred as requested for this milestone.

## Troubleshooting

- **Backend status: Unavailable:** start the backend, check its terminal for errors, then select **Retry connection** or reload. A non-200 response, invalid response body, timeout, or network error all count as unavailable.
- **Port already in use:** stop the previous instance using Ctrl+C. Vite uses strict ports so it will not silently move to a different address. These instructions expect backend port 8000 and frontend port 5173.
- **`npm` script execution is blocked:** use the documented `npm.cmd` commands.
- **`py` or `python` is not found:** use the initial setup block, which can use the existing local runtime, or install Python and reopen PowerShell.
- **Opening `index.html` directly does not work:** use the Vite development or preview server.

## Files and generated content

```text
PROJECT_SPEC.md                 Project scope and acceptance criteria
README.md                      Windows setup and run instructions
.gitignore                     Dependencies, builds, private data, and local artifacts
backend/
  requirements.txt             Pinned runtime dependencies
  requirements-dev.txt         Pinned test dependencies plus runtime requirements
  pytest.ini                   Backend test discovery and imports
  app/
    __init__.py                Python package marker
    main.py                    Application factory, startup, and health endpoint
    config.py                  Monitoring coordinates, timeouts and fixed study calendar
    database.py                SQLite engine, UTC handling, and request sessions
    migrations.py              Backed-up, additive environmental snapshot migration
    models.py                  SymptomRecord and calculated TNSS
    daily_health.py            DailyHealthRecord, validation and calendar-date conversion
    schemas.py                 Pydantic create and response schemas
    environment_schemas.py     Current-environment response with UTC metadata
    analysis/
      __init__.py              Analysis package marker
      dataset.py               Dataset selection, metadata, finite values and model TNSS adapter
      schemas.py               Typed analysis responses and minimum-pair threshold
      descriptive.py           Seven-variable numeric summaries
      associations.py          Pairwise Spearman calculations and unavailable statuses
      lagged_associations.py   UTC backward snapshot matching, coverage and lagged Spearman results
      daily_health_associations.py Same-date/provenance left join and four daily-health associations
      risk_model.py            Temporal next-observation features, fixed pipeline and evaluation
    routers/
      __init__.py              Router package marker
      symptoms.py              Create, list, retrieve, and delete endpoints
      environment.py           Current-environment endpoint and controlled errors
      analysis.py              Read-only descriptive and association endpoints
      daily_health.py          Daily create/list/read/update endpoints
    services/
      __init__.py              Service package marker
      environment_service.py  Open-Meteo requests, validation, and partial-data handling
  tests/
    conftest.py                Isolated database and client fixtures
    test_symptoms.py           Backend API and persistence tests
    test_environment.py        Offline service/endpoint/configuration tests
    test_symptom_environment.py Offline enrichment, persistence, and fallback tests
    test_migrations.py         Legacy preservation, backup, and rollback tests
    test_demo_data.py          Offline generation, reproducibility, API flags, and deletion safety
    test_analysis.py           Deterministic statistics, pairwise missingness, modes and API tests
    test_lagged_associations.py Lag matching, leakage, tolerance, timezones and endpoint tests
    test_daily_health.py       Daily validation, uniqueness, matching, simulation and deletion safety
    test_risk_model.py         Deterministic timing/leakage, split, preprocessing, metrics and model tests
frontend/
  package.json                 Frontend dependencies and commands
  package-lock.json            Reproducible npm dependency resolution
  index.html                   Browser entry point
  tsconfig.json                TypeScript configuration
  vite.config.ts               Local servers and API proxy
  src/
    main.tsx                   React entry point
    App.tsx                    Page selection, homepage, and health connection state
    index.css                  Homepage styling and navigation
    history.ts                 Time filtering, chronological chart data, local date/time labels
    dashboard.ts               Shared-filter selection, summary and raw chart data preparation
    analysis.ts                Statistical labels, display formatting and coefficient chart data
    laggedAnalysis.ts          Fixed lag/exposure labels and neutral matrix colour scale
    dailyHealth.ts             Calendar-date validation and daily form payloads
    api/
      symptoms.ts              POST/GET clients, response validation, and API errors
      environment.ts           Environment API client and response validation
      analysis.ts              Descriptive/environment/lag/daily clients and response validation
      dailyHealth.ts           Daily API clients, response validation and errors
      riskModel.ts             Experimental model API validation, availability and error handling
    components/
      ChoiceField.tsx          Accessible selectable score controls
      EnvironmentalExposure.tsx Homepage environmental values and request states
      EnvironmentalExposure.css Scoped styling matching the current homepage
      DashboardCharts.tsx      Reusable trend/scatter charts, provenance markers and tooltips
      LaggedAssociations.tsx   Lag matrix, independent request states, coverage and methodology
      DailyHealthAssociations.tsx Four same-day associations and methodological limits
      RiskModel.tsx           Secondary experimental model results, matrix and coefficient chart
      RiskModel.css           Scoped model-section styling
    pages/
      LogSymptoms.tsx          Observation form, validation, and save confirmation
      LogSymptoms.css          Responsive symptom form styling
      History.tsx              Record history, filters, chart, and expandable details
      History.css               History styling matching the existing interface
      Dashboard.tsx            Read-only Dashboard, shared filters, summary and accessible table
      Dashboard.css            Scoped responsive Dashboard styles
      Analysis.tsx             Dataset selector, overview, tables and Spearman coefficient chart
      Analysis.css             Scoped responsive Analysis styles
      DailyHealth.tsx          Real daily create/update form and labelled recent history
      DailyHealth.css          Scoped responsive daily form and history styles
    types/
      symptoms.ts              Form labels and symptom API types
      environment.ts           Current-environment response type
      analysis.ts              Analysis response and dataset types
      dailyHealth.ts           Daily records, form choices and association types
      riskModel.ts             Experimental model response types and feature labels
  tests/
    history.test.mjs           Filtering and chart data integrity tests
    dashboard.test.mjs         Dashboard filters, missingness, provenance and data integrity tests
    analysis.test.mjs          Statistical display, response validation and read-only API client tests
    lagged-analysis.test.mjs   Lag response validation, provenance, missing/zero display and API errors
    daily-health.test.mjs      Date/form validation, create/update client and source/missingness guards
    risk-model.test.mjs        Model response guards, timing/provenance, null metrics and API errors
scripts/
  __init__.py                  Development utility package marker
  demo_data.py                 Shared offline generation and transactional database utilities
  generate_demo_data.py        Development-only generation CLI with duplicate protection
  daily_demo_data.py           Offline synthetic daily summaries and daily-only deletion
  generate_daily_health_demo.py Daily-only generation CLI with duplicate protection
  delete_demo_data.py          Synthetic symptom deletion, or explicit --daily-health mode
```

`backend/.venv/`, Python and pytest caches, `frontend/node_modules/`, and `frontend/dist/` are generated locally and ignored by Git. Dependency installation and builds may recreate them. The application's SQLite database is stored under the ignored `data/private/` directory.

## Framework references

- [Vite getting started and runtime requirements](https://vite.dev/guide/)
- [Vite server proxy configuration](https://vite.dev/config/server-options#server-proxy)
- [Recharts LineChart API](https://recharts.github.io/en-US/api/LineChart/)
- [Recharts date/time axis configuration](https://recharts.github.io/en-US/api/XAxis/)
- [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [FastAPI lifespan and startup](https://fastapi.tiangolo.com/advanced/events/)
- [SQLAlchemy ORM quick start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [SQLAlchemy SQLite support](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [Pydantic field validation](https://pydantic.dev/docs/validation/latest/concepts/fields/)
