# Project Title

AllerWatch: A Longitudinal Health Data Platform for Allergic Rhinitis

This document is the single source of truth for the repository. It defines the intended scope, measurement conventions, architecture, analysis methods, and acceptance criteria. Implementation and supporting documentation must follow it. Changes to scope or measurement definitions must be recorded here before implementation; changes made after data collection begins must also be documented in the research report.

This is a project specification, not a statement that the application or any research findings already exist.

# Motivation

AllerWatch is motivated by the developer's personal experience with allergic rhinitis and is intended as a portfolio project for a master's application in Health Data Science.

Allergic rhinitis symptoms may fluctuate over time and may be associated with environmental exposure and personal health factors. A consistent daily diary, linked to environmental estimates, provides an opportunity to investigate these patterns while learning how to manage and analyse longitudinal health data.

The project's academic value comes from clear measurement definitions, reliable data integration, transparent handling of missingness, reproducible analysis, and responsible interpretation. Finding a strong association or producing an accurate prediction model is not required for success.

# Research Question

How are environmental exposures and daily health factors associated with day-to-day allergic rhinitis symptom severity?

For the initial study, the operational question is:

> Within one individual, how are daily environmental conditions and selected lifestyle factors associated with variation in self-reported allergic rhinitis symptoms?

The initial design is a prospective, single-person observational study. Daily records are repeated observations of one person, not independent participants. Results describe associations within that individual during the observation period and cannot establish causation or population-level effects.

# Project Scope

## Required MVP

Build a local browser application on Windows for one person and one configured study location at a time. It must support:

1. Recording and correcting one symptom diary per local calendar date.
2. Persisting longitudinal records in SQLite.
3. Automatically retrieving environmental data for missing study dates while the backend is running.
4. Displaying symptom history, environmental time series, and recording completeness.
5. Exploring descriptive associations between symptoms, environmental variables, and selected daily health factors.
6. Performing basic statistical summaries and exploratory correlations.
7. Comparing environmental exposure at lags of zero to three calendar days.
8. Exporting a documented dataset for reproducible analysis.
9. Producing a notebook and concise research report.

The frontend has four main views: daily diary, history, dashboard, and exploration/export. A small local configuration mechanism supplies study dates, location, and timezone; a settings interface is not required initially.

An experimental prediction model is optional and comes only after the required workflow is complete.

## Completed Implementation Slice — Milestone 1

The implementation scope was narrowed on 2026-09-17: M1 covers only the basic React/TypeScript/Vite frontend and Python/FastAPI backend. The homepage displays the project introduction and the connection status obtained from `GET /health`, which returns `{"status":"ok"}`. It must display `Backend status: Connected` only after a successful health response.

M1 includes dependency installation, a running-backend check, a frontend production build, and Windows PowerShell setup instructions. It does not include symptom logging, a database, environmental retrieval, charts, prediction, or authentication. Diary and persistence work from the original M1 is deferred and requires separate authorisation before environmental integration; the full research scope above remains the longer-term plan.

## Completed Implementation Slice — Milestone 2

On 2026-09-18, M2 was explicitly redefined as the backend symptom data model and persistence API. This replaces the earlier M2 environmental-integration milestone. Use SQLite, SQLAlchemy, and Pydantic to create a `SymptomRecord` with the fields specified below, initialise its database, and provide `POST /symptoms`, `GET /symptoms`, `GET /symptoms/{id}`, and `DELETE /symptoms/{id}`.

TNSS is calculated from the four nasal symptom components and returned as the read-only API field `tnss`. Eye symptoms and the separate 0–10 overall severity rating are not included in TNSS. Inputs cannot supply an ID or override TNSS. The API stores timestamped observations; multiple records on the same day are allowed in this milestone. A daily aggregation or uniqueness policy must be agreed before future longitudinal analysis.

M2 includes backend validation, database initialisation, persistence, and automated tests. It does not include frontend symptom logging, an update endpoint, environmental retrieval, charts, statistical analysis, prediction, or authentication. These newer M2 definitions take precedence over the earlier daily-diary sketch, which remains a future research direction.

## Completed Implementation Slice — Milestone 3

M3 is now the **Log Symptoms** interface, replacing the earlier dashboard/export milestone. Add a homepage link to `/log-symptoms` while preserving the homepage introduction and backend health status.

The form captures a current symptom observation: all five symptom scores with large selectable options `0 = None`, `1 = Mild`, `2 = Moderate`, and `3 = Severe`; an integer overall severity from 0 to 10; an explicit Yes/No medication choice; and optional notes. Required choices start unselected so missing answers are not mistaken for absent symptoms or no medication. The page must be responsive and keyboard accessible, with clear selected and focus states and no unnecessary animation.

Submit JSON to the existing `POST /symptoms` endpoint through Vite's `/api` proxy. Mark web-entered observations as `is_synthetic: false`, omit the timestamp so the backend assigns the observation time, and never submit or calculate TNSS in the frontend. Eye symptoms are recorded but do not contribute to the backend's four-item nasal TNSS definition.

After a confirmed successful response, display `Symptom record saved successfully.` and `TNSS: X / 12`, using the returned `tnss`. Provide a clear button to start another record. Validate required selections before submitting, explain field-specific validation failures, prevent duplicate submissions while saving, and preserve all entered values after an API error. A failed or uncertain response must not appear as a successful save; no automatic POST retries are performed.

Only the symptom-entry page, necessary navigation, and supporting frontend code/documentation belong to M3. No schema changes, backend TNSS changes, environmental data, charts, statistics, machine learning, authentication, or unrelated page redesign are authorised.

## Completed Implementation Slice — Milestone 4

M4 is explicitly redefined as **History**, replacing the earlier statistical-analysis milestone. It adds `/history` with simple navigation between Home, Log Symptoms, and History, preserving the existing homepage, health status, symptom form, and visual style.

Fetch all observations from the existing `GET /symptoms` endpoint through Vite's `/api` proxy. Show date, time, backend-returned TNSS, overall severity, and medication status in newest-first order (descending ID for equal timestamps). Each observation expands to show all five individual symptom scores, overall severity, TNSS, medication status, and notes. Missing notes are shown as not provided. Synthetic observations remain visible because this is a record-history view; label them clearly, including in the chart, so they are not mistaken for real data.

Provide Last 7 days, Last 30 days, and All records filters, defaulting to All records. Recent filters include timestamps from the current instant minus 7 or 30 elapsed 24-hour periods through the current instant, inclusive. Capture that instant on loading or changing the filter. All records imposes no time restriction. Display dates and times in the browser's local timezone and name that timezone on the page. Filtering compares absolute timestamps, not formatted dates; it does not establish a daily recall window or aggregate multiple observations per day.

Use Recharts for a simple TNSS line chart. Plot the filtered observations oldest first on a numeric date/time axis, with a fixed 0–12 TNSS axis and visible points. Preserve actual time spacing and multiple observations, with no daily averaging, smoothing, imputed scores, or frontend TNSS calculation. Keep gaps exceeding 24 hours visible by breaking the connecting line, while retaining every observed point; this is a display convention rather than an assertion that daily sampling was required. Distinguish synthetic points and do not connect real and synthetic observations as one trajectory.

Provide loading, readable API-error/retry, and empty states. With no records, show exactly: `No symptom records yet. Log your first symptom observation to begin building your longitudinal dataset.` If records exist outside the selected window, explain that the filter has no matches and allow All records. Failed loads must not be presented as an empty dataset.

M4 includes only History, its chart and filters, navigation, frontend verification, and documentation. Do not redesign existing pages or add environmental data, statistical analysis, prediction, authentication, database changes, or TNSS changes. All existing backend tests and the frontend build must pass. Verify several timestamped observations, filtering boundaries, record details, chart values/order, empty/error states, and the preserved logging workflow using isolated test data.

## Completed Implementation Slice — Milestone 5: Environmental Exposure Data

On 2026-09-19, the next authorised milestone is current environmental retrieval and display only. Add `GET /environment/current` and an Environmental Exposure section on the homepage, preserving symptom logging, History, TNSS, and the database. Do not store environmental snapshots, link them to symptoms, request browser geolocation, add pollen, interpret measurements medically, or implement analysis/prediction.

Keep all Open-Meteo request and normalisation logic in `backend/app/services/environment_service.py`. Use the existing HTTPX dependency, promoting its pinned runtime dependencies from the test requirements into runtime requirements. The route calls the service and translates its controlled unavailable exception to HTTP 503.

Use manually configured WGS84 monitoring coordinates from `backend/app/config.py`. `DEFAULT_LATITUDE` and `DEFAULT_LONGITUDE` designate a public London development example, not the user's inferred location. Optional `ALLERWATCH_LATITUDE` and `ALLERWATCH_LONGITUDE` environment variables override those defaults; validate finite values and latitude/longitude ranges. Both providers read the same configuration. The response and homepage identify the requested monitoring coordinates; Open-Meteo may select a nearby model grid cell.

Request Weather `current=temperature_2m,relative_humidity_2m` with Celsius units, and Air Quality `current=pm2_5,pm10,us_aqi`. Request `timezone=UTC` and `timeformat=unixtime` from both APIs. Decode Unix seconds as timezone-aware UTC and return ISO 8601 with an explicit UTC offset. The response `timestamp` is retrieval completion time, used for **Last updated**; separate nullable `weather_timestamp` and `air_quality_timestamp` retain each source's valid time. The UI shows these times explicitly in UTC, without assuming the two providers describe an identical instant.

Return the five nullable measurements, configured latitude/longitude, the three timestamps, and `status` (`available` or `partial`). Preserve finite numeric zero as a real value. Missing, invalid, non-finite, wrong-unit, or out-of-range data must never be replaced with zero or fabricated. Validate source timestamp metadata before accepting its values. Retain the other provider's usable data if one provider fails. Return a controlled 503 with `Environmental data are temporarily unavailable.` when none of the five measurements can be used. Use bounded HTTP timeouts (8 seconds per I/O operation, 4 seconds to connect, and 10 seconds total per provider) with parallel provider requests and no automatic retries.

The homepage loads this endpoint independently of the health check and displays temperature (°C), relative humidity (%), PM2.5 and PM10 (µg/m³), and US AQI (index). Include loading, available/partial, and unavailable/retry states. Label individual missing values **Unavailable**, show a partial-data notice when applicable, and provide Open-Meteo/CAMS attribution. Use neutral language such as Environmental Exposure and Current Conditions; these are modelled outdoor conditions at the configured location, not measured personal exposure or evidence of symptom causes.

Only retrieval and display are implemented here. Loading the homepage or manually refreshing requests data; no background synchronisation, caching, historical backfill, exposure storage, or symptom-triggered fetch is added. Future environmental linkage requires a separate milestone and timestamp/aggregation protocol.

## Completed Implementation Slice — Milestone 6: Environmental Snapshots on Symptoms

M6 extends each new symptom observation with a nullable environmental snapshot. Validate the original symptom request first, keep the existing four-component TNSS definition, then call the existing environmental service once. Save the returned measurements and metadata with the observation in the same SQLite row. Environmental HTTP errors, timeouts, malformed data, and other enrichment failures must never prevent a valid health observation from being saved. Partial results retain usable values; missing values stay null, and measured zero remains zero. Do not retry automatically or later overwrite snapshots when History or the homepage is read.

Add five nullable numeric columns: `temperature_c`, `relative_humidity`, `pm2_5`, `pm10`, and `us_aqi`. Store nullable `environment_timestamp` (retrieval completion), `weather_timestamp` and `air_quality_timestamp` (provider valid times), plus `environment_latitude` and `environment_longitude` (the configured monitoring point used for this snapshot). Location metadata prevents future configuration changes from making old observations ambiguous. These fields are response-only; they are not accepted from the symptom form or create request.

The symptom `timestamp` remains the observation time, defaulting to validation time before the network call. All four timestamps use UTC storage and timezone-aware API responses. Open-Meteo weather and air-quality times may differ from each other and from reporting time. A caller-supplied historical symptom timestamp remains supported, but the snapshot always describes current conditions at submission; it is not a reconstruction of historical exposure. Such records must not be assumed to have contemporaneous exposure without checking times. This milestone introduces no daily aggregation or matching tolerance for analysis.

On startup, inspect the existing SQLite table and add only missing nullable columns using `ALTER TABLE ... ADD COLUMN`, without dropping/rebuilding tables. Before changing an existing schema, create a consistent SQLite backup in `data/private/backups/`. Hold a write reservation, use a separate connection for the backup API, and execute all additions in one explicit transaction. A failed backup prevents migration; a failed addition rolls back the schema changes. Existing rows, IDs, indexes, score constraints, and values remain intact; old environmental fields remain null. Repeat startup performs no further migration/backup once columns exist. Fresh databases include the fields directly. The backup contains private data and stays excluded from version control.

History details contain **Symptoms** and **Environmental Exposure** sections, including measurement units, labelled UTC times, and saved monitoring coordinates. Show **Unavailable** for null or absent fields, without converting them to zero. Keep the existing TNSS chart, filters, homepage, and form. These are raw stored environmental snapshots, not necessarily conditions near symptom time, exact personal exposure measurements or evidence of causation. The C1 correction below requires temporal eligibility for relationship analysis while preserving these raw snapshots. No synthetic-data feature, pollen, new chart, statistics, correlation, lag analysis, prediction, authentication, or geolocation is added in M6.

## Completed Implementation Slice — Milestone 7: Synthetic Longitudinal Development Data

Add development-only command-line scripts `scripts/generate_demo_data.py` and `scripts/delete_demo_data.py`. Use the existing SymptomRecord model without schema, endpoint, or UI changes. Generated observations always have `is_synthetic: true`; the existing form continues to submit false. These fictional records support interface testing, later pipeline development, and clearly labelled demonstrations only. They are not patient observations, clinical evidence, or estimated historical conditions from Open-Meteo.

Generate 90 consecutive complete UTC calendar days, ending yesterday in UTC by default. Each day contains one or two observations at varied morning, afternoon, or evening times on a fictional UTC clock. The browser may display these instants in another timezone. Offer `--seed` (default 42) and `--end-date YYYY-MM-DD` for reproducibility; the same seed, end date, generator version and Python version reproduce all non-ID fields. IDs remain SQLite-managed and need not repeat after deletion. Reject current/future end dates to avoid fabricated future observations. Generated environmental timestamps simulate retrieval shortly after the observation, with separate quarter-hour weather and hourly air-quality valid times. Monitoring coordinates remain null because the scenario represents no actual place.

Use bounded, gradually varying environmental processes and several multi-day pollution episodes: temperature 5–35 °C, humidity 25–95%, PM2.5 1–100 µg/m³, and PM10 related to but greater than PM2.5 and bounded to 160 µg/m³. Generate an approximate PM2.5-based US AQI using concentration breakpoints only as a plausibility guide, not a regulatory daily AQI or NowCast. Do not interpret it medically. A small pollution/humidity contribution, independent persistent symptom variation, observation/component noise and occasional independent flares produce varied nasal and eye scores. These deliberately chosen simulation assumptions are not fitted clinical relationships. AQI shares the PM2.5 signal; it is not an additional independent causal effect. TNSS uses the unchanged model property; no TNSS column or override is added.

Medication is probabilistic and more likely at higher symptom scores, with exceptions; it never influences subsequent symptoms. Notes are usually null. Approximately 6% of observations lose one or more environmental measurements, using null rather than zero; complete source outages also clear that source's timestamp. A total environmental outage clears the retrieval timestamp. Symptom fields stay complete.

Scripts require an existing, current-schema SQLite database and default to the application's database. An optional `--database` selects an already initialised isolated development database. They never create, reset, migrate, or recreate a database. Use an explicit SQLite write transaction to protect the duplicate check and insert: stop without adding rows if any synthetic record exists. Deletion reports the synthetic count before execution, uses a strict `is_synthetic = true` predicate, and reports the committed deletion count and preserved real count. No overwrite/reset flag or automatic deletion is provided. Both scripts preserve real rows and use no external API or new dependency.

Verify offline generation, ranges, temporal structure, missingness, reproducibility, API flags/TNSS, duplicate protection, transaction rollback, and deletion safety. Then perform an authorised generate/read/delete/regenerate cycle in the application database, verifying the real-record checksum at every stage and leaving the final synthetic dataset available. Existing History labels and separate synthetic chart series must remain intact. No dashboard, additional chart, statistical/correlation/lag analysis, prediction, pollen, authentication, or unrelated redesign belongs to M7.

## Completed Implementation Slice — Milestone 8: Health Data Dashboard

Add a read-only Dashboard at `/dashboard`, reachable alongside Home, Log Symptoms and History. Reuse `GET /symptoms`; do not change the database, stored observations, TNSS, synthetic generator, or backend endpoints. Preserve the existing visual style and other pages, adding only necessary navigation links.

Default to All data and All observation types. A shared filter offers Last 7/30/90 days or All data, plus All/Real only/Synthetic only. Recent ranges use inclusive elapsed 24-hour windows ending at load/filter-selection time, consistent with History; compare absolute timestamps. All data imposes no time restriction. Apply both filters to the snapshot, dataset summary, all charts, and accessible data table. Label counts/date coverage as the selected subset and show selected versus loaded observation counts. Never fabricate observations to fill a requested range. Display dates/times in the named browser timezone.

The latest selected observation (timestamp descending, then ID descending for ties) supplies TNSS, overall severity, PM2.5, US AQI and its timestamp, with an explicit real/synthetic label. Missing environmental values show Unavailable, without falling back to another record. Dataset summary shows selected total, real and synthetic counts, actual date coverage, and missing PM2.5/AQI/humidity counts. Show Includes synthetic development data whenever the selection contains synthetic records.

Render seven Recharts plots: TNSS over time (0–12), separate PM2.5/AQI/humidity time series with individual labelled scales, and TNSS scatter plots against each environmental variable. Use observation timestamps on trend X axes; these plot stored environmental snapshots associated with the observations, not exact personal exposures or freshly retrieved conditions. Tooltips identify time, observation type, TNSS, and the relevant measurements; TNSS trend tooltips also show overall severity and medication. Keep multiple same-day and same-timestamp observations as separate records. Use raw points and straight connecting segments only, with no smoothing, aggregation, fitting, imputation or interpolation across missing values. Break time-series lines for missing values, changes between real/synthetic observations, and gaps longer than 24 hours.

Real points use circles and solid lines; synthetic points use diamonds and dashed lines, with a text legend and tooltip labels. Scatter plots use distinct shapes and never join points. Following C1, require at least two non-missing, temporally eligible pairs per scatter plot under the shared lag-0 rule documented below; otherwise display Not enough paired observations to display this relationship. Report total, aligned, temporally excluded and missing pair counts. A selected-observation table provides keyboard/screen-reader access to raw values, including excluded snapshots, missing markers and provenance. This is descriptive visualisation, not formal statistical analysis.

Handle loading, HTTP/network/timeout/invalid-response errors with retry, no observations, no filter matches, a lone observation, and all-missing environmental series. A completely empty dataset displays No symptom observations are available yet. Show the exact note: Dashboard visualisations are exploratory and do not establish causal relationships. Synthetic observations are used for development and demonstration.

Extend the existing lightweight Node frontend tests for filtering/data integrity; add no test dependency. Run all backend tests, frontend tests and the production build. Browser-check all seven charts using existing demo data, filter combinations, sparse/empty/missing/zero-valued fixtures, tooltips, navigation and narrow layouts without mutating stored observations. Verify the database row checksum remains unchanged. No correlation coefficients, p-values, lag analysis, machine learning, prediction, pollen, geolocation, authentication, treatment recommendations, or unrelated redesign is added.

## Study and Development Boundaries

- Plan for approximately 8–10 weeks of part-time software development, subject to the developer's experience.
- Aim for 90–120 days of prospective diary collection, which may extend beyond the initial software build.
- These durations are planning targets, not a statistical power calculation or a guarantee that modelling is justified.
- Begin collection after the measurement protocol is settled. A temporary diary using the same definitions is acceptable before the application is ready.
- Do not reconstruct long periods of symptoms from memory.
- Use synthetic data to develop and demonstrate the workflow. Keep synthetic records separate from real observations.
- Flag travel days rather than attempting route tracking or estimating exposure across multiple locations.

Before collection, milestone M0 must settle the study location, IANA timezone, observation dates, diary wording, environmental products, and availability of the required variables. These are unresolved configuration choices, not grounds for assuming a location from the development machine.

# Non-Goals

AllerWatch is:

- **not a medical diagnostic system**;
- **not a treatment recommendation system**;
- **not a clinical decision support system**.

The project does not include:

- Apple Watch integration or HealthKit;
- a mobile application;
- user authentication, multiple accounts, or participant management;
- cloud deployment or public hosting;
- payments or subscriptions;
- a chatbot or unrelated AI features;
- deep learning;
- clinical risk alerts or instructions to change medication;
- causal estimation of treatment effects;
- population-level prediction or clinical validation;
- continuous location tracking or indoor exposure measurement.

Docker, WSL, microservices, Redis, Celery, complex scheduling infrastructure, and model-serving infrastructure are unnecessary for the initial scope. Windows Task Scheduler may be considered later if unattended retrieval becomes useful; it is not an MVP dependency.

# Technology Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Development environment | Windows, PowerShell | Native local development |
| Frontend | React, TypeScript, Vite | Diary interface and research dashboard |
| Charts | Recharts | Interactive time series and association plots |
| Backend | Python, FastAPI | Validation, local API, ingestion, and analysis responses |
| API schemas | Pydantic | Input validation and typed response schemas |
| Database | SQLite, SQLAlchemy | Local persistence and relational access |
| Backend verification | pytest, HTTPX / FastAPI TestClient | Isolated API and persistence tests |
| Data preparation | pandas, numpy | Calendar alignment, aggregation, and analysis datasets |
| Basic statistics | scipy | Descriptive association calculations |
| Optional adjusted analysis | statsmodels | Small regression models and appropriate diagnostics |
| Optional prediction | scikit-learn | One simple experimental model and evaluation pipeline |
| Environmental sources | Open-Meteo weather and air-quality APIs | Modelled outdoor environmental estimates |
| Research workflow | Jupyter notebook and written report | Reproducible analysis and interpretation |

Use a Python virtual environment and npm for local dependencies. Record and pin a compatible dependency set during implementation. Requiring every listed analysis library to appear in the MVP is unnecessary; statsmodels and scikit-learn are used only if their corresponding analyses are justified.

# System Architecture

Use one frontend, one backend, and one local database.

```text
React / TypeScript / Recharts
          |
          | Local HTTP / JSON
          v
       FastAPI -------> Open-Meteo APIs
          |
          +-----------> SQLAlchemy / SQLite
          |
          +-----------> Local raw-response archive
          |
          +-----------> Shared Python analysis functions
                                  ^
                                  |
                         Research notebook
                                  |
                                  v
                         Figures and report
```

## Component Responsibilities

- **Frontend:** collect diary entries, show history and quality information, request analysis results, and provide exports.
- **Backend:** validate inputs, persist records, retrieve environmental data, aggregate exposures, construct analysis datasets, and return results.
- **Database:** store diary records, location definitions, daily environmental summaries, and retrieval provenance.
- **Raw-response archive:** retain original environmental responses and enough metadata to reproduce transformations.
- **Analysis functions:** provide a shared implementation for dataset preparation, summaries, correlations, and lags.
- **Notebook:** explain methods, call the shared functions, and generate report outputs. It must not contain a competing implementation of the core calculations.

The frontend and backend run on localhost. The browser does not call Open-Meteo directly. Diary persistence must succeed independently of environmental retrieval.

M6 fetches current environmental data during symptom submission and saves a snapshot; the homepage still fetches independently. Startup/History reads do not request environmental data. Future daily synchronisation, manual catch-up, historical backfill, raw-response archives, and analysis functions are not implemented. The application does not claim to collect data while the computer or backend is off.

## Intended Repository Organisation

```text
allerwatch/
├── PROJECT_SPEC.md
├── README.md
├── .gitignore
├── .env.example
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── api/
│       └── types/
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   ├── services/
│   │   └── analysis/
│   └── tests/
├── notebooks/
├── docs/
├── data/
│   ├── private/
│   └── synthetic/
└── reports/
    └── figures/
```

This is a proposed layout only. Supporting documents may expand the protocol or data dictionary, but must remain consistent with this specification.

# Data Flow

## Implemented M2 Record Flow

1. An API client submits a JSON symptom record. M3 adds the Log Symptoms browser form as a client of this existing endpoint.
2. Pydantic validates integer ranges, booleans, optional notes, and a timezone-aware timestamp. Omitted timestamps default to the current UTC time.
3. The existing environment service attempts both bounded Open-Meteo requests. SQLAlchemy saves symptoms and the available environmental snapshot together; a failed lookup still saves symptoms with null environment fields. All timestamps are normalised to UTC and retain an explicit UTC offset when returned.
4. The API returns the assigned ID, stored symptom/environment values, and calculated TNSS. Listing and reading records recalculate TNSS from their nasal components and use stored snapshots without new environmental requests.
5. Deletion removes the requested record. Missing IDs return HTTP 404; invalid input returns HTTP 422.
6. M4 retrieves the list for History, filters it by timestamp in the browser, shows newest-first expandable records, and plots the same filtered observations chronologically using their returned TNSS.

The database is initialised on backend startup. Initialisation is repeatable and preserves existing rows. Tests use separate temporary database files and must not write to the personal database.

## Measurement Time Convention

For a future daily-diary study, the proposed convention is to record symptoms for the previous completed local calendar day each morning. This recall window is not yet represented by the M2 timestamp-only API, and the following daily-date conventions must not be inferred from its timestamp automatically.

For a diary record dated **D**:

- Symptom severity refers to day D.
- Outdoor time and rhinitis medication use refer to day D.
- Sleep duration refers to the night ending on the morning of D.
- Same-day exposure refers to the local calendar day D.
- The entry creation timestamp records when the diary was actually submitted, usually D+1.

The form must state these recall periods explicitly. Late entries remain identifiable from the record date and creation timestamp. Future diary dates are invalid under this completed-day protocol.

## Future Environmental and Analysis Processing Sequence

1. React submits the diary to FastAPI.
2. FastAPI validates the input and saves it to SQLite.
3. The backend identifies missing environmental dates, including dates with no symptom diary.
4. The backend requests the selected weather and air-quality products.
5. It preserves the original responses and records retrieval metadata.
6. It assigns environmental timestamps to the configured local calendar days and calculates daily summaries.
7. It records per-variable time coverage and quality status.
8. It builds a complete daily calendar, then joins diary and exposure data by date and location.
9. It constructs lagged variables before excluding missing analysis pairs.
10. Shared analysis functions produce results for the frontend, notebook, and exports.

Use unambiguous timestamps when assigning observations to local days. Expected coverage must respect the timezone, including daylight-saving transitions where applicable. Repeated or missing clock hours must not silently create duplicates or shift dates.

## Retrieval and Quality Rules

- Repeated synchronisation must not create duplicate daily exposure rows.
- Use bounded timeouts and retries; report failures without losing diary entries.
- Request historical coverage needed for the maximum three-day lag before the first symptom date, where available.
- Keep weather and air-quality retrieval states separate.
- A missing, unsupported, or failed value is not zero.
- Require complete expected returned time coverage for each exposure variable in the primary analysis.
- Retain identifiable partial summaries, but exclude them from the primary analysis. A documented relaxed-coverage sensitivity analysis may be added later.
- An hourly API output can represent interpolated model data; hourly values are not independent personal exposure measurements.
- Choose and document one product per source family for a given analysis. Do not silently mix forecast archives, reanalysis, or regional products to fill gaps.
- Freeze the analysis dataset and record its source snapshot, code version, aggregation rules, and date range before producing a final report.

# Database Model

## Current Entity (M2, Extended in M6)

Only the `symptom_records` table is implemented in M2. Its SQLAlchemy entity is `SymptomRecord`.

| Field | Storage / API type | Rules |
| --- | --- | --- |
| `id` | Integer primary key | Assigned by the database; not accepted in create requests |
| `timestamp` | UTC datetime | Time of the symptom observation; defaults to the current UTC time when omitted; supplied values require a timezone |
| `nasal_congestion` | Integer | Required, 0–3 inclusive |
| `sneezing` | Integer | Required, 0–3 inclusive |
| `runny_nose` | Integer | Required, 0–3 inclusive |
| `nasal_itching` | Integer | Required, 0–3 inclusive |
| `eye_symptoms` | Integer | Required, 0–3 inclusive; excluded from TNSS |
| `overall_severity` | Integer | Required, 0–10 inclusive; independent of TNSS |
| `medication_taken` | Boolean | Required; JSON `true` or `false` |
| `notes` | Nullable text | Optional; defaults to null |
| `is_synthetic` | Boolean | Defaults to false; identifies synthetic records |
| `tnss` | Calculated response integer | 0–12; derived from the four nasal scores; no independent storage column or input field |
| `temperature_c` | Nullable float | Environmental snapshot temperature, °C |
| `relative_humidity` | Nullable float | Relative humidity, % |
| `pm2_5`, `pm10` | Nullable float | Modelled particulate concentrations, µg/m³ |
| `us_aqi` | Nullable float | Provider's US AQI index; no medical interpretation |
| `environment_timestamp` | Nullable UTC datetime | Snapshot retrieval completion time |
| `weather_timestamp`, `air_quality_timestamp` | Nullable UTC datetime | Separate provider valid times |
| `environment_latitude`, `environment_longitude` | Nullable float | Requested monitoring coordinates at submission |

## API Contract

| Endpoint | Success | Other expected responses |
| --- | --- | --- |
| `POST /symptoms` | 201 with the saved record and TNSS | 422 for invalid fields, missing required values, or extra fields such as `tnss` |
| `GET /symptoms` | 200 with an array, newest timestamp first and highest ID first for ties; empty array when no records exist | Includes both real and synthetic records with their flags; no pagination in M2 |
| `GET /symptoms/{id}` | 200 with the matching record and TNSS | 404 if absent; 422 for an invalid ID |
| `DELETE /symptoms/{id}` | 204 with an empty body | 404 if absent; 422 for an invalid ID |

`GET /health` keeps its existing response. The list endpoint is a record-management API, not an analysis dataset: later analysis must exclude synthetic observations explicitly.

## Integrity and Storage Rules

- Apply Pydantic validation and SQLite constraints to score ranges and required values.
- Score inputs must be actual JSON integers; reject strings, fractional numbers, and booleans rather than coercing them into scores.
- Accept actual JSON booleans for `medication_taken` and `is_synthetic`; do not infer an omitted medication answer as false.
- Use a timezone-aware API contract and normalise timestamp storage to UTC. SQLite's handling of timezone information must not make response timestamps ambiguous.
- Do not enforce one record per date or conflate observation time with a separately collected recall date in M2.
- Calculate TNSS whenever a record is read. Do not maintain a second editable copy.
- Use the repository-relative path `data/private/allerwatch.sqlite3`, resolved independently of the shell's working directory and excluded from version control.
- Initialise missing tables without resetting existing records. M6 applies the backed-up, additive migration described above to existing symptom tables.
- Use temporary, isolated SQLite files for backend tests.
- No user, location, exposure, or analysis-results tables are required for this milestone.

## Deferred Data Model

Location records, daily exposure summaries, ingestion provenance, sleep, outdoor time, and additional diary context remain future work. Before adding them, update this specification with the daily recall convention, within-day aggregation rules, synthetic-data exclusions, relationships, and migration plan. Do not create these tables or fields in M2.

# Symptom Variables

## Current M2 Measurement Fields

| Variable | Scale | Role |
| --- | --- | --- |
| Nasal congestion (`nasal_congestion`) | Integer 0–3 | TNSS component; corresponds to the earlier nasal blockage item |
| Sneezing (`sneezing`) | Integer 0–3 | TNSS component |
| Runny nose (`runny_nose`) | Integer 0–3 | TNSS component |
| Nasal itching (`nasal_itching`) | Integer 0–3 | TNSS component |
| Eye symptoms (`eye_symptoms`) | Integer 0–3 | Separate symptom item; excluded from TNSS |
| Overall severity (`overall_severity`) | Integer 0–10 | Separate overall rating; not derived from TNSS |

Use consistent labels: **0 = None, 1 = Mild, 2 = Moderate, 3 = Severe** in the M3 interface. None means the symptom is absent. Keep explanatory wording stable after the pilot.

The planned primary outcome is the four-item nasal symptom sum, named **TNSS** in this implementation:

`TNSS = nasal_congestion + sneezing + runny_nose + nasal_itching`

TNSS ranges from **0 to 12**. It is calculated from its components and cannot be independently edited. Eye symptoms and overall severity remain separate. This implementation must not be described as a clinically validated instrument, diagnostic score, or validated risk category. Statistical analysis is not implemented in M2.

All five symptom scores, overall severity, and medication status are required when creating a record. Missing observations are not zero-symptom observations. A fixed daily recall window and handling of multiple observations per day remain prerequisites for future daily analysis.

## Deferred Daily Health and Context Variables

The following earlier diary proposal is retained for future protocol design only. M2 uses the required boolean `medication_taken` and optional notes defined above. M11 now implements a separate daily health record with required sleep duration, sleep quality, stress and exercise under its explicit protocol below; that implementation supersedes the nullable sleep proposal in this table. Outdoor time, tri-state medication answers and context flags remain deferred.

| Variable | Definition | Missingness |
| --- | --- | --- |
| Sleep duration | Hours slept during the night ending on the morning of D | Nullable |
| Outdoor time | Approximate total minutes outdoors during D | Nullable |
| Rhinitis medication used | Whether rhinitis medication was used during D | Yes / no / unknown |
| Possible respiratory illness | Participant-reported illness context during D; not an application diagnosis | Yes / no / unknown |
| Away from study location | Whether the configured location poorly represents the participant's location during D | Yes / no / unknown |
| Notes | Optional short context | Nullable |

Detailed medication doses, treatment-effect estimation, extensive lifestyle questionnaires, and additional symptom domains are outside the MVP. Keep the diary brief enough to support consistent completion.

# Environmental Variables

## M5 Current Conditions and M6 Stored Snapshots

Retrieve current temperature, relative humidity, PM2.5, PM10, and US AQI for the homepage and, in M6, snapshot storage on new symptom submissions. US AQI is returned as the provider's index without health categories or advice. M9 explicitly includes PM10 in its observation-level exploratory analysis; this does not change the future prespecified primary lag relationship. Current-condition values are not daily means. Preserve unavailable values as null and retain separate provider timestamps as specified above.

## Deferred Daily Research Variables

| Variable | MVP summary | Unit | Role |
| --- | --- | --- | --- |
| PM2.5 | Daily mean | µg/m³ | Primary environmental exposure |
| Temperature at 2 m | Daily mean | °C | Secondary exposure and possible adjustment variable |
| Relative humidity at 2 m | Daily mean | % | Secondary exposure and possible adjustment variable |

Calculate means from valid returned samples on the documented time grid. Record coverage independently for each variable. Values are modelled outdoor conditions and must be described as proxies for personal exposure.

Wind, precipitation, and pollen remain deferred extensions. Their availability does not justify adding them automatically to the analysis. PM10 analysis is included only as explicitly authorised for M9.

Open-Meteo currently documents pollen coverage only in Europe during pollen season. Pollen availability must be verified for the study location, dates, and selected product; it is not a required dependency. Missing pollen data must not be interpreted as an absence of pollen exposure.

Weather reanalysis and historical forecast archives have different origins and availability. M0 must select the products and document their temporal coverage, regional coverage, resolution, retrieval latency, and relevant attribution requirements.

Reference documentation:

- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)

# Statistical Analysis Plan

## C1 correction — contemporaneous environmental eligibility (2026-09-22)

Temporal co-storage does not establish temporal alignment. Ordinary environmental associations and Dashboard relationship plots now share the existing lag-0 time rule, applied independently to all five environmental variables. For symptom time **T**, the same record's provider valid time **V** must lie in the inclusive interval **[T − 3 hours, T]**. Use `air_quality_timestamp` for PM2.5, PM10 and US AQI, and `weather_timestamp` for humidity and temperature. Retrieval completion **R** (`environment_timestamp`) must exist and satisfy **V ≤ R**. Compare timezone-aware instants in UTC; never infer missing source times. Missing metadata, future-valid sources, stale sources more than three hours before T, and retrieval before source valid time fail eligibility. No substitute exposure is fetched or inferred.

As in lag-0, R may follow T because submission validates symptoms before retrieving a snapshot. This is an approximate contemporaneous comparison, not a claim that exposure was already known at T or a prediction-availability rule. The tolerance measures source age relative to the symptom, not relative to today's clock. Nonzero lag and model availability rules remain unchanged.

Keep all raw values and observations unchanged. History, raw descriptive summaries and environmental trend displays retain stored snapshots and label them as such; raw co-storage must not imply conditions at symptom time. Backdated symptoms enriched with later current exposure remain readable but their incompatible pairs are excluded from ordinary relationships and lag-0. API symptom responses add read-only, per-variable `environment_time_eligible` flags computed centrally in the analysis package, never persisted. Dashboard uses these flags and fails closed when they are absent; it does not implement a second timestamp rule.

For each ordinary association, `record_count` is the total selected symptom observations. The mutually exclusive partition is **record_count = n + temporally_excluded_pairs + missing_pairs**: missing/non-finite TNSS or exposure counts as missing first; otherwise a failed time check counts as temporally excluded; only remaining pairs enter Spearman. Thus missing time metadata on a numerically complete pair counts as temporally excluded. Scatter plots report the same partition. Genuine numerical zero is retained when eligible. Dataset modes, minimum ten-pair threshold, TNSS, raw records, synthetic generation, nonzero lag analysis and modelling are unchanged. This correction supersedes the unrestricted ordinary-pairing statements in M8/M9 below; the dated Step 16 audit remains historical evidence and is not rewritten.

## Completed Implementation Slice — Milestone 9: Descriptive Statistics and Exploratory Associations

Authorised on 2026-09-20, M9 adds a dedicated read-only analysis package, `GET /analysis/descriptive`, `GET /analysis/associations`, and an Analysis page. This observation-level slice takes precedence over the future daily/lag protocol below. Retain multiple observations per day without aggregation or time shifting. Following C1, ordinary relationships pair TNSS only with temporally eligible same-record exposures under the rule above; descriptive summaries retain raw stored values. Snapshots are ambient estimates, not exact personal exposure. This is not the future prespecified previous-day analysis.

Both endpoints accept `dataset=real_only|synthetic_only|all`, defaulting to **real_only**, even when empty or small. Never switch silently to development data. Return selected mode, record count, real/synthetic counts, inclusion notice, and UTC first/last observation timestamps. The Analysis selector refreshes both responses and labels synthetic-only and mixed results explicitly. Analysis does not inherit Dashboard filters.

Summarise TNSS, overall severity, temperature, humidity, PM2.5, PM10, and US AQI: finite non-missing n, missing count, mean, median, sample SD (`ddof=1`), minimum, Q1, Q3, maximum. SD is null for n < 2; all estimates are null for n = 0. Use NumPy's linear percentile convention; this interpolates quantile positions, not missing observations. Non-finite values are treated as unavailable and counted with missing values. Preserve genuine zeros. TNSS comes from the existing model property, with no redefinition or eye-symptom inclusion.

For each of PM2.5, PM10, US AQI, humidity, and temperature, use only records with both finite TNSS and that exposure, passing the C1 contemporaneous rule. Return aligned n, temporally_excluded_pairs and missing_pairs relative to the selected record_count, with the disjoint definitions above. Compute SciPy `spearmanr(..., alternative="two-sided")` only for **at least 10 valid pairs** and at least two distinct values in both variables. Otherwise return `insufficient_data` or `insufficient_variation` with null rho and p-value. Ten pairs is an interface safeguard, not a reliability or power guarantee. Unexpected non-finite computed results become `unavailable`, not JSON NaN/Infinity.

Display the unadjusted, two-sided asymptotic p-values requested for this exploratory milestone, with no significance stars, causal/clinical claims, or multiple-testing correction. Repeated observations within one person are temporally dependent; these p-values assume independent observations and are not valid confirmatory evidence for this diary. Small samples and tied ranks further limit the approximation (SciPy cautions about samples below roughly 500). Five related exposures are examined; synthetic AQI shares its simulated PM2.5 signal. Do not tune the generator or data to obtain particular results.

The Analysis page provides a compact overview, both numerical tables, and a horizontal rho chart fixed to −1 through +1 with a visible zero line. Omit unavailable coefficients and explain statuses. Display the paired-observation methodology, exploratory p-value caveat, and development-data notice. Keep loading/error/retry, empty and small-dataset states readable. No writes, imputation, missing-value interpolation, outlier deletion, lag analysis, regression, prediction, or unrelated redesign is included.

References: [SciPy Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html), [NumPy sample SD](https://numpy.org/doc/stable/reference/generated/numpy.std.html), [NumPy percentiles](https://numpy.org/doc/stable/reference/generated/numpy.percentile.html).

## Completed Implementation Slice — Milestone 10: Approximate Lagged Environmental Associations

Research question: **Do environmental exposures measured before symptom reporting show different associations with allergic rhinitis symptom severity?** This milestone compares TNSS with PM2.5, US AQI, and relative humidity at 0, 6, 12, and 24 hours only. It adds a read-only `/analysis/lagged-associations` endpoint and a section in Analysis, reusing the M9 dataset modes, default real_only, Spearman implementation, and minimum 10 complete pairs.

Inspection on 2026-09-20 found only symptom-time snapshots in `symptom_records`, not an independent environmental time series. The 140 synthetic observations have a median adjacent reporting gap of about 13.48 hours (range 2.47–37.29 hours). The genuine dataset has only one observation. Exact 6/12/24-hour exposure cannot be reconstructed from this sampling. The approximation is fixed before inspecting correlations and must not be tuned for larger n or p-values.

**Time semantics:** use timezone-aware UTC internally, retaining the existing SQLite UTC adapter. PM2.5 and AQI use `air_quality_timestamp`; humidity uses `weather_timestamp`. These are the provider's estimated-condition valid times. `environment_timestamp` is retrieval completion, not the exposure's valid time. Never replace a missing provider timestamp with the symptom timestamp or guess an exposure time. Reject naive timestamps in the analysis helper rather than silently interpreting them as local time.

**0h:** use only the same record's finite exposure, provided its provider valid time is in `[T − 3 hours, T]`, where T is the symptom timestamp. Require retrieval completion to exist and not precede source valid time. No substitute record is used. This contemporaneous baseline is also approximate (actual offsets are reported). As with existing symptom submission, this same-report snapshot is retrieved after validation; its retrieval completion may follow T, while its environmental valid time must never be after T. It is not a claim that the value was already available for prediction at T. Backdated records with later source valid times are excluded. Following C1, ordinary environmental associations share this same time rule for all five exposures. The lag API retains its existing combined unmatched/missing pair count; ordinary associations additionally distinguish temporal exclusions.

**6/12/24h:** target = T − lag. Among finite exposures of the same provenance and monitoring location, choose the latest provider valid time in the closed interval `[target − 3 hours, target]`. Require the source symptom record timestamp and its retrieval completion timestamp both to be at or before target; require provider valid time at or before retrieval completion. These extra checks prevent using a later report or later retrieval of a past-labelled value to reconstruct information unavailable at target. Never use a source after target even if closer. Equal valid times choose the latest eligible retrieval, then largest record ID. No match becomes null; do not interpolate, extend tolerance, or manufacture history. An older finite observation within tolerance may be used when a nearer observation lacks this particular variable.

The one-sided 3-hour tolerance deliberately leaves unmatched records: nominal 6h represents actual offsets of 6–9h, 12h represents 12–15h, and 24h represents 24–27h. These windows stay distinct despite sparse 1–2/day sampling. Report actual matched offset min/median/max, pair-specific n/missing counts, real/synthetic pair counts, and distinct source-record count. A source can be reused for multiple outcomes, so n is not a count of independent exposures or participants. Each lag may use a different subset; differences in rho must not be interpreted as evidence of a best biological delay.

In all mode, outcomes from both types are included but a real outcome never uses synthetic exposure or vice versa. For nonzero lags, real snapshots require the same known latitude/longitude; unknown real locations cannot establish comparability and are unmatched. Synthetic snapshots may share their intentionally unknown fictional location. Exact stored coordinate equality is used, with no inferred location or tolerance-based geographic matching.

The response provides the matching method, three-hour tolerance, UTC convention, approximate flag, all dataset counts and all 12 results (including insufficient/constant statuses). The frontend uses a labelled 3×4 table with subdued diverging intensity, signed rho, n, missing count, p-value and status; supplementary details expose actual offsets and distinct sources. Visible notes cover ambient-exposure estimates, sparse snapshots, no causal evidence, differing subsets, repeated observations and multiple comparisons. Synthetic selection displays: **These lagged results are based on synthetic development data and are not clinical findings.** Mixed results carry an explicit synthetic-inclusion notice.

No database/schema changes, environmental retrieval, new stored observations, generator adjustment, TNSS change, extra lags, sleep/daily-health variables, regression, prediction, or UI redesign is included. The following daily-study/calendar-lag and adjusted-analysis sections remain **deferred research**, distinct from M10's approximate hourly matching.

## Completed Implementation Slice — Milestone 11: Daily Health and Sleep

M11 adds a separate `DailyHealthRecord` table, a Daily Health form/history page, and four exploratory same-day TNSS associations: sleep duration, sleep quality, stress, exercise. It does not change TNSS, environmental results, or stored symptom records.

The study calendar is explicitly **fixed UTC+08:00**, matching the developer's current calendar context but independent of monitoring coordinates and browser timezone. Define it once in backend configuration. It is a fixed offset without DST, not an automatically inferred geographic timezone. Store `date` as an ISO calendar date without time; never convert that date through JavaScript UTC/local Date parsing. The backend list response supplies the calendar label and today's study date. Convert aware symptom timestamps to this study offset, then take `.date()` for joins. Changing the study calendar after collection requires an explicit data-protocol migration, not a silent settings toggle.

Daily fields: ID; date; finite numeric sleep duration 0–24 hours; integer sleep quality 1–5 (Very poor/Poor/Fair/Good/Very good); integer stress 1–5 (Very low/Low/Moderate/High/Very high); integer exercise 0–1440 minutes; optional notes; immutable is_synthetic (default false); server-assigned aware UTC created_at. Sleep describes the main sleep ending on the selected date; stress and exercise summarize that calendar day (today may still be incomplete).

Enforce **one row per (date, is_synthetic)** with a database unique constraint. This permits one real summary and one explicitly labelled fictional demo summary on an overlapping date; a synthetic row must never block or overwrite a real diary. POST creates and returns 201, duplicate same-type dates return 409, PUT updates an existing date/type or returns 404. GET list supports the existing dataset modes (default real_only); date-specific GET/PUT default to real and can explicitly select `is_synthetic=true`. PUT cannot change date/provenance/ID/created_at. No delete API is needed for this milestone.

Add the table with SQLAlchemy's checked create-table operation, not a database rebuild. Existing tables/records are left untouched; startup is idempotent. Inspect the existing schema first and create a private SQLite backup before populating the new daily table. The backup may include the empty additive table created by backend reload. Test legacy/fresh startup and symptom preservation.

Daily Health allows create/update of real summaries only; source type is not a form control. Load an existing real date before editing. Required score controls start unselected; optional notes stay optional. Show save/update success, field-specific validation and readable load/save errors without discarding inputs. Display recent daily rows newest first with explicit real/synthetic labels; synthetic history is read-only. Add navigation without redesigning other pages. A small Dashboard addition is optional and deferred here.

Analysis uses a **left join from every selected symptom observation to (study calendar date, is_synthetic)**, without a hard foreign key. Unmatched symptoms remain in the denominator with four missing daily values; daily rows without symptoms add no outcome pairs. Multiple same-day symptoms each receive the same daily summary, so paired n counts observations, not independent days. Report distinct matched days, per-type pair counts, matched/unmatched symptom counts and daily records without symptoms. All mode includes both types but never cross-matches them. Reuse minimum 10 complete pairs, constant handling, finite-value guards and two-sided unadjusted SciPy Spearman calculation. Existing environmental APIs and result definitions remain unchanged.

Use a separate development CLI to generate daily summaries for the inclusive study-date span of existing synthetic symptoms (about 90 days; currently 91 after UTC+08 conversion). A fixed seed and sorted synthetic-only input give reproducible values. Use mostly 5–9 hours' sleep, noisy partially related quality/stress, and largely independent exercise (mostly 0–120 minutes), with substantial variation. Small predefined contributions from synthetic daily symptom burden demonstrate association; this is reverse-conditioned simulation, not a causal or sleep-effect model. Do not modify symptoms or tune coefficients/seeds after inspecting results. Stop if synthetic daily rows already exist. Keep existing symptom generation and deletion defaults compatible; extend the delete CLI with explicit `--daily-health` for daily-only deletion, and leave symptom deletion as its documented default. Both paths strictly delete only is_synthetic=true and preserve real rows.

Show **Daily Health Associations** inside Analysis using the same dataset selector, explicit synthetic notices, n/missing/rho/p/status and day counts. Self-reported sleep is not clinically measured sleep; stress is subjective; confounding, repeated observations and same-day timing limit interpretation. Associations do not establish temporal direction or causality. No imputation, causal claims, wearable integration, new prediction/ML, or final redesign is included. The following primary daily research protocol remains a deferred direction, distinct from this implementation slice.

## Primary and Secondary Analyses

The prespecified primary relationship is the association between **PM2.5 on D−1 and the symptom sum on D**. The primary summary is a descriptive Spearman correlation with the paired observation count and relevant plots.

Secondary exploratory analyses cover temperature, humidity, sleep duration, outdoor time, and environmental lags zero through three. Medication use and context flags primarily support description and sensitivity analyses. Do not interpret a medication–symptom association as treatment effectiveness.

Finalise variable definitions and analysis choices before examining associations. Record later changes and their reasons. Do not select the primary exposure or lag because it produces the strongest result.

## Data Preparation and Missingness

1. Construct a complete daily calendar for the observation period.
2. Validate dates, score ranges, units, duplicate constraints, and source selection.
3. Derive the symptom sum and exposure quality indicators.
4. Construct calendar-based exposure lags.
5. Apply the documented eligibility and quality rules for each analysis.
6. Report the original date range, expected days, diary days, excluded days, and usable pairs.

Do not interpolate missing symptom outcomes or treat them as symptom-free days. Use available complete pairs for each descriptive association, reporting a separate sample count for each. Missing lifestyle data should not remove an otherwise eligible environmental–symptom pair.

Keep gaps visible in plots. Any trailing seven-day average is a display aid, must report or document its minimum coverage, and must not replace raw daily outcomes in the primary analysis.

## Descriptive Statistics

Report symptom and exposure distributions using medians, interquartile ranges, ranges, and relevant counts. Show daily symptom trajectories, individual symptom patterns, environmental trajectories, missingness, and recording completeness. Use clear units and date labels.

## Association and Lag Analysis

Use scatterplots and Spearman correlation to describe monotonic associations. Report direction, magnitude, and paired sample size. Return an explicit unavailable result for constant variables or insufficient valid pairs.

| Lag | Pairing |
| --- | --- |
| 0 | Exposure on D with symptoms on D |
| 1 | Exposure on D−1 with symptoms on D |
| 2 | Exposure on D−2 with symptoms on D |
| 3 | Exposure on D−3 with symptoms on D |

Lagging must occur on the complete calendar before missing rows are excluded. Yesterday means the previous calendar date, not the previous available record. Show every prespecified lag and its usable sample count; do not report only the strongest lag.

Neighbouring days may be dependent and both symptoms and exposures may share time trends. The MVP must not attach significance stars, automatic trigger claims, or causal interpretations to these correlations. Ordinary independent-observation p-values are not an adequate inferential approach for this diary. SciPy also cautions about its usual Spearman p-value approximation for smaller samples: [SciPy Spearman documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html).

## Optional Adjusted Analysis

After sufficient data collection and inspection of data quality, consider one small regression model relating the symptom sum on D to previous-day PM2.5, previous-day temperature, previous-day humidity, and a linear time trend.

- Document the justification for the adjustment set rather than automatically including every recorded variable.
- Treat linear regression on a bounded symptom sum as an approximation.
- Inspect residuals, influential observations, predictor correlation, and serial dependence.
- Consider time-series-aware uncertainty estimates, such as HAC standard errors for a suitable contiguous daily series.
- Prespecify and report any lag/bandwidth choice used for uncertainty estimation.
- Do not compress missing calendar dates and then treat the remaining rows as consecutive daily observations.
- If an appropriate uncertainty calculation cannot be supported, omit inferential claims and keep the result descriptive.
- Robust standard errors do not correct unmeasured confounding, measurement error, or an unsuitable model.

Medication use may follow symptom worsening. It must not be automatically treated as an ordinary confounder or used to claim treatment benefit or harm.

Reference: [statsmodels robust covariance documentation](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.get_robustcov_results.html).

## Sensitivity Analyses and Reporting

Keep sensitivity analyses limited and documented:

- Exclude days flagged for travel or possible illness, reporting how unknown flags are handled.
- Compare the primary exposure-coverage rule with one prespecified relaxed rule.
- Examine whether a small number of unusual observations dominate the result, without deleting valid observations solely to improve findings.

Clearly distinguish the primary analysis, secondary exploration, and any analyses added after inspecting results. Report weak, null, unstable, and inconclusive results honestly. Neither software completion nor portfolio success depends on statistical significance.

# Experimental Prediction Plan

## Completed Milestone 12 — Experimental Logistic Regression

On 2026-09-22, M12 is explicitly redefined as a small next-observation logistic regression experiment. This supersedes the earlier ridge/daily-target proposal below; portfolio release is deferred to M13. This is not a clinical prediction model. No stored observations, synthetic generators or schema are changed.

The operational target is **next_observation_tnss_gte_6**: the next chronological symptom observation has backend TNSS >= 6. This is an experimental threshold, not a validated clinical cutoff. Select real_only or synthetic_only before constructing adjacent pairs; all is rejected. Sort by aware UTC symptom timestamp. Do not bridge over an invalid pair or choose a later target to obtain a usable pair. Pairs touching tied timestamps are excluded and counted because their order is ambiguous.

The prediction point is completion of the previous report's snapshot: feature_timestamp = max(previous symptom timestamp, its recorded environmental retrieval completion). This is slightly after the reported symptom time when downloading the snapshot. Require feature_timestamp < next symptom timestamp. A retrieval at/after the next symptom excludes that pair. For simulated complete outages without a retrieval timestamp, the previous simulated report time is used and all exposure inputs are missing. Real records without a retrieval/availability marker are conservatively excluded from this retrospective experiment. These conventions use recorded report/retrieval times, not an assertion that the app has an immutable clinical event audit.

Use previous_tnss, previous_overall_severity and the previous record's five environmental values only. Accept an exposure only with a known source valid time in [previous report time - 3h, previous report time], and known retrieval at/before feature_timestamp. Do not use the target record's environment, symptoms or metadata as predictors. Record target availability separately; no training label may become available after the first test prediction point. Later test rows may use earlier already-observed test symptoms, as in sequential one-step evaluation with a fixed trained model; do not refit on test data. The forecast horizon is the next recorded observation, not a fixed next-day interval; report interval coverage.

Daily-health candidates would come from the **calendar day before the prediction point**, in the fixed UTC+08:00 study calendar, with matching provenance and creation at/before that point. Do not use the next target's date to choose predictors: its eventual timing is not known when predicting. However, the current mutable daily table has no update timestamps or version history. It cannot prove which stored values existed earlier, and all current synthetic diaries were created after the historical symptom period. Therefore all four daily-health candidates remain missing/excluded in this first model, with explicit reasons and availability counts. An earlier calendar date alone is not proof of earlier availability. Medication is excluded because timing is ambiguous. Do not fabricate historical availability or change the generator to make daily predictors usable.

Prespecify an approximately 80/20 chronological holdout using floor(0.8 * usable rows); no random shuffle, stratification, seed search or hyperparameter search. Require >=30 usable rows, >=24 train and >=6 test rows, >=5 examples of each class overall, and >=3 of each class in training. These engineering safeguards do not establish statistical adequacy. Single-class testing retains valid metrics but ROC-AUC is null with an explanation. Report class counts/percentages for all rows and both periods, exact UTC ranges/split point, row exclusions and missingness.

Before fitting, remove columns entirely missing in training only (report them; never fill these with zero). Fit one scikit-learn Pipeline on training data only: median SimpleImputer, StandardScaler, LogisticRegression with fixed C=1, default L2 regularization, lbfgs, max_iter=1000, random_state=42 and no class weighting/resampling. Freeze the pipeline for testing. Use a fixed probability threshold of 0.5. Report accuracy, precision, recall, F1, ROC-AUC when defined and explicit TN/FP/FN/TP. Undefined metric denominators yield null plus a reason. Compare accuracy with always predicting the training majority class (tie -> low). Do not optimize the threshold or tune against the held-out period. Treat a convergence failure as unavailable rather than displaying unreliable coefficients.

Return standardised model coefficients, intercept, used/omitted features and training-only preprocessing summaries. Coefficients are fitted log-odds directions per training SD, not causal effects; correlated PM2.5/PM10/AQI inputs limit interpretation. No individual probability display, persisted model, prediction alert or recommendation is included. GET /analysis/risk-model defaults to real_only; all/invalid modes return 422. Analysis displays the experiment after existing analyses, with separate loading/error/insufficient states and disabled training in All data.

Display the research-only and synthetic-performance warnings. Explain small N-of-1 samples, repeated observations, measurement error, ambient exposure estimates, uncertain historical availability, lack of calibration/clinical validation and limited generalisability. Add deterministic leakage, split, imputation/scaling, class, metrics, coefficient and provenance tests. Run existing tests/build, inspect actual synthetic results once without tuning, verify real-only insufficiency, and preserve full database checksums. Stop before project audit or UI redesign.

## Deferred Earlier Prediction Proposal

The following daily ridge-regression plan remains historical planning context, not the M12 implementation.

## Initial Experiment

- Prefer one ridge regression model predicting the daily symptom sum.
- Define a fixed morning prediction time and the target symptom day before constructing features.
- Use only diary records and environmental information actually available by that prediction time.
- Do not use the target day's completed symptoms, full-day realised environmental summaries, or future data.
- Retrospectively retrieved environmental products must not be assumed to have been available at historical prediction times. Document their availability or limit the experiment accordingly.
- Compare against the training-period mean score and the most recently available symptom score.
- Use a small, prespecified feature set; avoid extensive model searches.

## Evaluation

- Train on earlier dates and evaluate on later dates.
- Use a fixed chronological holdout or expanding-window evaluation with calendar-aware boundaries.
- Fit preprocessing and any tuning only within training data.
- Preserve meaningful forecast horizons across missing dates.
- Report mean absolute error, baseline results, evaluation dates, and the number of evaluated predictions.
- Report instability and uncertainty appropriate to a small single-person dataset.
- Skip the experiment if there is inadequate temporal coverage, outcome variation, or usable evaluation data.

The collection target alone does not establish adequate model sample size. A model that fails to outperform a baseline remains a valid result.

If a later experiment predicts a high-symptom category, define its threshold in advance, explain that it is an operational research definition rather than a validated clinical threshold, and verify adequate examples of both categories in training and evaluation periods. Such an extension requires updating this specification.

No prediction is a diagnosis, a treatment recommendation, a clinical risk estimate, or grounds for a medical alert. Model deployment and a live risk interface are outside the initial scope.

Reference: [scikit-learn TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).

# Ethical and Privacy Considerations

- Initial real observations belong only to the developer as the self-tracking participant. Recruiting others is outside scope.
- Keep personal health records, location details, notes, database files, and personal exports out of version control.
- Use synthetic data for public demonstrations and label it clearly. Synthetic patterns are not research evidence.
- Review screenshots, figures, and reports for identifying information before sharing them.
- Store only the location precision necessary for the selected environmental product; a home address is unnecessary.
- Environmental API requests send coordinates and dates to the provider. Do not send symptoms, medication use, notes, or other diary contents to Open-Meteo.
- Restrict application access to localhost. Lack of authentication is appropriate only within this local, single-user scope.
- Local storage is not automatically encrypted or anonymised. Device access controls and private backups remain relevant.
- Support correction, deletion, and export of diary records, with clear handling of any retained exports or backups.
- Do not require changes to normal behaviour or treatment to produce more interesting data.
- Provide attribution to Open-Meteo and the underlying providers as required by the selected datasets.
- Any future participant recruitment, external data sharing, or institutional research use requires a separate review of applicable ethics and consent requirements before expanding the project.

# Limitations

1. **Single participant:** results do not establish population-level relationships.
2. **Observational design:** temporal association does not demonstrate that an exposure caused symptoms.
3. **Self-report measurement:** recall, interpretation of severity labels, and reporting consistency may change over time.
4. **Missingness:** missed entries may relate to symptom severity or daily circumstances, producing bias.
5. **Exposure approximation:** modelled outdoor conditions do not measure inhaled dose, indoor exposure, commuting conditions, or personal allergen exposure.
6. **Unmeasured factors:** pollen, indoor allergens, infections, medication timing, and other influences may be unavailable or imperfectly recorded.
7. **Reverse causation:** symptoms may affect sleep, outdoor activity, and medication use.
8. **Time dependence:** serial correlation, seasonal patterns, and shared trends complicate interpretation.
9. **Limited observation period:** 90–120 days may not represent different seasons or provide sufficient variation for reliable modelling.
10. **Multiple comparisons:** exploring several variables and lags increases the chance of apparently interesting patterns.
11. **Data-source variation:** API availability, revisions, model updates, and spatial resolution may affect exposure estimates.
12. **Prediction limits:** performance on one person's short series does not establish clinical utility or transferability to other people or periods.

# Development Milestones

Effort estimates are planning aids, not deadlines. Real data collection proceeds alongside development and may continue after the software is usable.

| ID | Milestone | Estimated effort | Deliverable |
| --- | --- | --- | --- |
| M0 | Study specification and feasibility | 4–6 hours | Final measurement protocol, data dictionary, location/timezone choice, and API feasibility evidence |
| M1 | Windows application scaffold and health connection | 3–6 hours | Minimal React homepage, FastAPI health endpoint, verified connection, and Windows setup instructions |
| M2 | Backend symptom model and persistence API | 6–10 hours | SQLAlchemy entity, Pydantic schemas, SQLite initialisation, four symptom endpoints, and automated backend tests |
| M3 | Symptom logging interface | 6–10 hours | Responsive Log Symptoms form, existing-API submission, backend-authoritative TNSS, validation, and error recovery |
| M4 | Symptom history | 6–10 hours | Newest-first expandable records, 7/30-day filters, and a Recharts TNSS time series using the existing API |
| M5 | Current environmental exposure data | 6–10 hours | Open-Meteo service, configurable coordinates, current-environment endpoint, homepage display, and offline tests |
| M6 | Environmental snapshots on symptom records | 6–10 hours | Safe additive migration, failure-tolerant enrichment, combined History details, and offline tests |
| M7 | Synthetic longitudinal development data | 4–8 hours | Reproducible offline generation, synthetic-only deletion, duplicate protection, documentation and tests |
| M8 | Descriptive health data dashboard | 6–10 hours | Shared filters, labelled real/synthetic charts, latest snapshot, dataset summary, accessible records and verification |
| M9 | Descriptive statistics and exploratory associations | 6–10 hours | Independent analysis package, labelled dataset modes, descriptive/Spearman APIs, Analysis tables/chart, and deterministic tests |
| M10 | Approximate lagged environmental associations | 6–10 hours | Strict backward snapshot matching, 0/6/12/24h results, labelled matrix/coverage, and leakage tests |
| M11 | Daily health and sleep | 8–12 hours | Validated daily diary, date/provenance join, exploratory lifestyle associations, safe synthetic daily data and offline tests |
| M12 | Experimental next-observation logistic regression | 8–12 hours | Prespecified temporal features/split, training-only pipeline, baseline, labelled evaluation and leakage tests |
| M13 | Portfolio release (deferred) | 8–12 hours | README, verified workflow, and concise research report |

After a short pilot, freeze diary definitions before the main collection period. If measurement definitions change later, document the change, identify affected dates, and decide whether periods remain comparable before pooling them.

M2 provides symptom persistence, M3 current-observation logging, M4 History, M5 current environmental display, M6 environmental snapshots, M7 synthetic development records, M8 a descriptive Dashboard, M9 observation-level descriptive/Spearman analysis, M10 approximate hourly lag matching, M11 a daily health diary with same-date exploratory associations, and M12 an experimental next-observation classifier. Daily aggregation of symptoms/exposures, calendar-day lag analysis, dependence-aware inference, and export/report work remain deferred. Completing M12 does not imply the full daily research workflow exists. These prerequisites require their own agreed scope before portfolio release.

# Completion Criteria

## M0 — Study Specification and Feasibility

- The study location, timezone, observation window, and diary recall periods are explicit.
- Symptom wording, scoring, primary exposure, missingness rules, and lag direction are documented.
- Sample weather and air-quality responses have been checked for the intended location and dates.
- Selected products, variables, units, coverage, limitations, and attribution requirements are recorded.
- The analysis plan is settled before exploratory association results are inspected.

## M1 — Windows Application Scaffold and Health Connection

- The frontend and backend run locally using documented Windows instructions.
- The homepage displays `AllerWatch`, `Personal Allergic Rhinitis Health Data Tracker`, and `Research prototype for exploring symptom and environmental data.`
- `GET /health` returns HTTP 200 with the JSON body `{"status":"ok"}`.
- The frontend requests the endpoint and displays `Backend status: Connected` after a successful response.
- Loading and failed connections have clear status text rather than a false connected state.
- Dependencies are installed, the backend is run and checked, and the frontend builds successfully.
- No diary, database, environmental API, chart, machine learning, or authentication feature is implemented in this milestone.

## M2 — Backend Symptom Model and Persistence API

- A `SymptomRecord` contains exactly the requested stored fields and a read-only calculated TNSS.
- SQLite initialises on startup and retains records across restarts without destructive reinitialisation.
- The create, list, read-by-ID, and delete endpoints return the documented HTTP responses.
- All five symptom scores enforce integer values 0–3; overall severity enforces integer values 0–10; invalid payloads return HTTP 422.
- TNSS equals the four nasal scores, ranges from 0–12, excludes eye symptoms and overall severity, and cannot be overridden by a request.
- Medication status is required, notes are optional, and `is_synthetic` defaults to false.
- Timestamps have unambiguous UTC round trips; timezone-aware historical observations may be supplied.
- Tests cover valid creation, invalid symptom scores, TNSS calculation, retrieval, deletion, and persistence using isolated databases. All backend tests pass.
- The existing health endpoint and frontend remain functional; no frontend symptom logging or later milestone features are added.

### Verified Windows Test Procedure — 2026-09-18

The user confirmed that the original test command without an explicit temporary directory failed in their PowerShell session. After recreating `backend/.pytest_tmp`, running the following command from `backend/` succeeded:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp="$PWD\.pytest_tmp" -q
```

The screenshot showed **82 passed, 3 warnings**: two dependency deprecation warnings and one pytest cache permission warning. Future instructions for this machine must use the explicit local `--basetemp` argument. Keep `.pytest_tmp` as disposable test data, excluded from version control. Do not infer the earlier failure's root cause or automatically repeat directory deletion or permission changes from the screenshot.

## M3 — Symptom Logging Interface

- The homepage links to Log Symptoms and retains its original introduction and health status.
- All five symptom fields provide large, clearly selected 0–3 controls with the specified labels.
- Overall severity accepts only integers 0–10, medication requires Yes/No, and notes are optional.
- The form works on desktop and narrow screens and supports keyboard operation.
- Missing or invalid fields receive readable field-specific feedback before submission; backend validation errors are also explained.
- Submitting uses the existing `POST /symptoms` API with `is_synthetic: false`, without an independently supplied TNSS.
- A successful save displays the exact success message and the backend-returned TNSS, followed by an explicit way to start a fresh record.
- API failures preserve user input and show a readable error; repeated clicks during saving do not create duplicate requests.
- The database schema and backend TNSS implementation remain unchanged.
- All existing backend tests pass using the documented explicit local pytest temporary directory, and the frontend production build succeeds.
- Browser verification covers success, validation, unavailable backend, input retention, starting another record, and desktop/narrow layouts using isolated test data.

## M4 — Symptom History

- Home, Log Symptoms, and History are reachable through simple navigation; the homepage and logging workflow are preserved.
- History retrieves all observations using the existing list endpoint, with clear loading/error/retry states.
- Records appear newest first and show date, time, TNSS, overall severity, and medication status.
- Each record expands to show every requested symptom/context field, including optional notes.
- Last 7 days, Last 30 days, and All records use the documented inclusive timestamp windows; the record list and chart use the same filtered subset.
- The Recharts chart uses chronological timestamps, a fixed 0–12 TNSS axis, backend-provided values, and visible individual observations, including a single-record case.
- No frontend TNSS calculation, eye-symptom inclusion, smoothing, aggregation, or missing-as-zero values are introduced. Synthetic observations are identified.
- An empty database shows the exact requested message; an empty filter has a distinct message and recovery option.
- Existing backend tests pass with an explicit local temporary directory, and the frontend production build succeeds.
- Browser verification uses several records in an isolated database and covers filters, details, chart, navigation, loading, empty/error states, and the existing logging workflow.
- No backend model, schema, TNSS, environmental, statistical, prediction, authentication, or unrelated UI changes are made.

## M5 — Current Environmental Exposure Data

- A dedicated service fetches and validates both Open-Meteo current-condition responses using centrally configured coordinates.
- `GET /environment/current` returns the requested measurements, explicit UTC times, location, and availability status; no missing value becomes zero.
- Missing variables, partial provider failure, timeouts, HTTP errors, malformed JSON/structures, and invalid values are handled without breaking the backend or discarding usable data from the other provider.
- Homepage loading, available, partial, and unavailable states display units, timestamps, configured coordinates, neutral language, and attribution.
- Offline service/endpoint tests cover success, missing/zero values, provider failures, malformed responses, and timeouts. All existing backend tests and the frontend build still pass.
- Manual endpoint verification and browser verification show environmental values; test data and symptom regression checks use isolated databases.
- No symptom linkage, database/schema change, TNSS change, pollen, analysis, prediction, geolocation, authentication, or unrelated redesign is introduced.

## M6 — Environmental Snapshots on Symptom Records

- Inspect the existing schema before changes; migration creates a private backup and preserves all original records and constraints.
- New symptom records store complete/partial snapshots, source times, retrieval time, and monitoring coordinates; old records remain readable with null environment fields.
- Invalid symptom requests return 422 before any provider request. Snapshot fields are server-managed and TNSS remains unchanged, excluding eyes.
- Environmental timeout, connection/HTTP failure, missing values, or malformed responses still allow a successful 201 symptom save. Genuine zeros survive storage and retrieval.
- POST and both GET symptom endpoints expose the stored snapshot; History reads never refresh it.
- History separates symptoms from environmental estimates and shows Unavailable for missing fields, explicit units, and UTC environmental times.
- All backend tests and frontend build pass; offline tests verify persistence, failure fallback, migration, rollback, nulls/zeros, and unchanged TNSS.
- Manually verify one live enriched save and one simulated upstream failure using an isolated database; verify History on desktop/mobile. Never add verification observations to the personal database.
- Document time semantics and exposure limitations. Stop before synthetic-data features, analysis, or prediction.

## M7 — Synthetic Longitudinal Development Data

- Scripts use the existing model and always flag generated records as synthetic, with no change to real form submissions.
- Ninety complete UTC days have one or two varied-time observations each, valid complete symptoms, and plausible, temporally persistent environmental values with about 3–8% partial/missing environmental observations.
- Symptom variation includes small environmental contributions and substantial independent noise/persistence; medication is probabilistic without any treatment-effect model. No clinical claims or correlation calculation is introduced.
- The same seed and fixed end date reproduce non-ID fields; a repeated generation attempt stops without duplication.
- Synthetic-only deletion reports counts before and after, and real records remain byte-for-byte equal in field values after generation and deletion.
- Offline tests cover valid ranges, missingness, unchanged TNSS, persistence/API flags, reproducibility, duplicate protection, and deletion/rollback safety; all backend tests pass.
- Run generation, verify GET /symptoms, delete, verify preservation, and regenerate. Report final count, date range, real-record count, missing-environment count, and exact changed files.
- README documents Windows commands, assumptions, limitations, labelling, and deletion. Stop before dashboard or analysis implementation.

## M8 — Health Data Dashboard

- Navigation reaches Dashboard from Home, Log Symptoms and History without redesigning them.
- The existing GET /symptoms supplies all data; there are no new write operations/endpoints or TNSS calculations.
- Latest snapshot and labelled dataset summary use the shared 7/30/90/all and real/synthetic filters.
- All seven responsive charts have clear titles, axes, units, tooltips and an accessible record table. TNSS axes remain 0–12.
- Synthetic data has an inclusion notice, explicit labels, diamond points and dashed lines; real data uses circle points and solid lines. Separate types are never joined.
- Missing environment values remain missing; only actual zeros plot at zero. Scatter plots omit only the relevant incomplete pairs; time-series gaps remain visible.
- Empty, single/few-record, all-missing, mixed-type, and no-match states are readable and show no broken plots. Multiple observations per day remain separate.
- All backend tests, frontend tests and frontend build pass. Browser checks verify every chart, time/type filters, sparse/missing/zero data, accessible tooltips and mobile layout.
- Stored-record checksum is unchanged, and the exact exploratory/non-causal disclaimer is displayed. Stop before formal statistics.

## M9 — Descriptive Statistics and Exploratory Associations

- Statistical calculations live in `backend/app/analysis/`, separate from routes, models, and frontend code.
- Both read-only APIs default to real_only, support all three dataset modes, and report correct provenance counts and UTC date ranges.
- All seven numeric summaries exclude missing/non-finite values, retain genuine zeros, and document sample SD and percentile conventions.
- Five same-record Spearman results report pair-specific n/missing counts; fewer than 10 pairs, constants, and non-finite estimates return explicit statuses with null estimates.
- Analysis navigation, selector, overview, tables, coefficient chart, unavailable/loading/error states and cautious methodology work on desktop and narrow screens.
- Synthetic-only and mixed results are explicitly labelled, with no significance stars or causal/clinical claims.
- Deterministic offline tests cover known positive/negative associations, missing pairs, constants, empty/small datasets, all modes, unchanged TNSS, and no database writes. All backend/frontend tests and frontend build pass.
- Inspect and report actual current synthetic rho/p/n results without changing the generator or observations; verify three modes and missing/small states in the browser.
- Verify the database's full-field checksum is unchanged and report exact file changes. Stop before lag analysis.

## M10 — Approximate Lagged Environmental Associations

- Inspect and document snapshot-only sampling and timestamp semantics before selecting the fixed matching rule.
- Dedicated analysis code handles only PM2.5, AQI and humidity at 0/6/12/24h, with three-hour backward tolerance, explicit UTC normalization, nulls, and no invented timestamps/history.
- Provider valid times never exceed the lag target. Nonzero sources must also have been reported and retrieved by target, with matching provenance and compatible location. Lag 0 is explicitly a same-report contemporaneous snapshot, not an as-of prediction.
- Endpoint defaults to real_only, supports all three modes and returns all 12 results, dataset/pair provenance counts, statuses, actual offset summaries and distinct source counts.
- The Analysis selector refreshes lag results; the accessible 3×4 matrix includes signed rho/n/p/missing/status, unavailable cells and coverage details without relying on colour alone.
- All backend tests, frontend tests and build pass. Deterministic tests cover every lag, future valid/report/retrieval times, tolerance boundaries, missing values/times, positive/negative/constant associations, small/empty/mixed data and timezone offsets.
- Browser checks cover synthetic, real and all modes, insufficient/constant/zero/negative cells, empty/error states, no non-finite display, cancellation and responsive layout.
- Audit actual matches, report all current synthetic results and approximation limits, preserve full database checksum, and list exact changed files. Do not proceed to Daily Health / Sleep or prediction.

## M11 — Daily Health and Sleep

- Create only the additive daily_health_records table; preserve all existing symptom fields, TNSS and observations. Repeated initialization is safe.
- Validate date-only YYYY-MM-DD input and all numeric bounds with Pydantic and database constraints. Enforce unique (date, is_synthetic). Web-created records are real; demo rows cannot be overwritten by loading the same date in the real diary.
- POST creates, GET lists/loads, PUT updates the existing row without changing its ID/date/provenance/creation timestamp. Duplicate POST returns 409; invalid input returns 422.
- Daily Health provides decimal sleep, clearly labelled quality/stress choices, exercise minutes, optional notes, success/errors, input preservation after failed saves, and newest-first labelled recent history. Existing pages retain their behavior.
- Convert aware symptom timestamps into the fixed UTC+08:00 study date and left-join on (date, is_synthetic), with no stored foreign key or updates to symptoms. Missing diaries remain missing; extra diaries do not fabricate symptom outcomes.
- Dedicated analysis reuses pairwise Spearman and minimum 10 pairs, supports all modes without cross-matching, and reports four variables, n/missing/rho/p/status, provenance counts and distinct daily summaries. Analysis shows synthetic and scientific limitations.
- Generate approximately 90 days using only existing synthetic symptoms, fixed seed, modest predefined relationships and substantial noise. Do not modify or tune symptom data. Stop on duplicate generation. The daily-only deletion option preserves real daily records and every symptom record; existing symptom-only deletion leaves all daily records untouched.
- All backend tests, frontend tests and build pass; browser checks cover create/update/duplicate/error handling, mobile layout, all analysis modes, insufficient data, correct dates across browser timezones and no non-finite display. Test writes use an isolated database.
- Report actual synthetic coefficients and date coverage, verify original symptom checksum, and list exact changed files. Stop before prediction or machine learning.

## M12 — Experimental Logistic Regression

- Dedicated analysis code predicts the next chronological TNSS >= 6 target using only preceding, available predictors; the threshold is labelled experimental. No TNSS definition or stored records change.
- Dataset selection precedes pairing; real and synthetic never mix. All mode is rejected by the endpoint and disables model training in the UI. UTC timestamps and strict feature-before-target validation handle ties and delayed retrieval explicitly.
- Previous-record symptom/environment predictors meet the availability rule; future or stale exposures remain missing. Previous-day daily candidates are excluded without trustworthy historical versions; creation time alone cannot prove absence of later edits. Medication is omitted.
- The fixed 80/20 chronological split never shuffles. Training labels are available by the first test prediction point. Minimum row/class safeguards return explanatory insufficient_data states. Single-class test metrics are handled individually, with null ROC-AUC.
- Median imputation, scaling, all-missing-column removal and fitting use training data only. Model settings and threshold are fixed, with no test-driven feature/parameter/synthetic-data tuning.
- Report train/test periods, class counts/percentages, baseline, five model metrics, confusion matrix, signed standardised coefficients and omitted features. Convergence/non-finite failures are controlled.
- Analysis adds a secondary experiment section with medical-use and synthetic-data warnings, a zero-centred coefficient chart, readable unavailable/error/loading states and mobile accessibility. No individual probability or recommendation is added.
- Deterministic leakage, metrics, class, missingness, provenance and reproducibility tests pass alongside all existing tests and frontend build. Verify synthetic results, real insufficiency and disabled mixed training in the browser.
- Preserve both existing tables and full-field checksums; report actual metrics/coefficients and exact changed files. Stop before final project audit or redesign.

## M13 — Portfolio Release

- Setup instructions have been followed successfully in a clean local Windows environment.
- The complete diary-to-storage-to-exposure-to-analysis-to-export workflow has been verified.
- Relevant data-integrity, ingestion, aggregation, and lag-alignment checks pass.
- A fixed dataset and documented environment reproduce the report's figures and numerical summaries.
- The report explains motivation, methods, data quality, results, and limitations, approximately four to six pages where appropriate.
- Real results state the actual observation duration and usable sample sizes. Preliminary or descriptive-only findings are labelled accordingly.
- A public synthetic demonstration works without private records, private coordinates, or personal notes.
- Private data is excluded from repository contents and intended public artifacts.
- The implemented scope and documentation remain consistent with this specification.

## Overall Definition of Done

The required project is complete when M0–M13 and the deferred research-workflow prerequisites are satisfied and another person can run the synthetic demonstration on Windows, understand the measurement and analysis choices, and reproduce the reported demonstration outputs without accessing private data.

The real-data research report must accurately state what the available observations support. A short or inconclusive study may justify only descriptive findings. Strong associations, statistically significant results, and improved prediction accuracy are not required for completion.
