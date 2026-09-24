# Public portfolio demo on Render — preparation only

No service has been deployed. These settings are for a future source-only release; complete PUBLICATION_CHECKLIST.md before publishing a repository. Never upload the local SQLite database, backups, .env, private exports, work/ or outputs/. No private health data is required to build or start this demo.

## Backend Web Service

| Render setting | Exact value |
| --- | --- |
| Service type | Web Service |
| Runtime / Language | Python 3 |
| Root Directory | **Leave blank (repository root)** |
| Build Command | `pip install -r backend/requirements.txt` |
| Start Command | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Instances / workers | One instance; default one Uvicorn worker |
| Pre-deploy Command | None |
| Persistent disk | None for this disposable demonstration |

Keep the repository root available because runtime initialization reuses `scripts/demo_data.py` and `scripts/daily_demo_data.py`. Render excludes files outside a configured root directory, so **do not set the backend Root Directory to backend**. The start command changes into backend so the standard `app.main:app` import works. Render supplies PORT; do not hardcode it. These commands follow [Render's FastAPI setup](https://render.com/docs/deploy-fastapi) and [root-directory rules](https://render.com/docs/monorepo-support).

Set backend environment variables:

| Variable | Value |
| --- | --- |
| `PUBLIC_DEMO_MODE` | `true` |
| `DATABASE_PATH` | `/tmp/allerwatch-demo/allerwatch.sqlite3` |
| `FRONTEND_ORIGIN` | `https://YOUR-FRONTEND.onrender.com` — replace with the actual Static Site origin; no path |
| `PYTHON_VERSION` | `3.12.14` |

The public London monitoring defaults remain; optional ALLERWATCH_LATITUDE / ALLERWATCH_LONGITUDE can use another public demonstration location. Do not upload personal location configuration. `FRONTEND_ORIGIN` permits one exact origin; localhost/127.0.0.1 on ports 5173 and 4173 remain allowed for local work. CORS is not authentication.

## Frontend Static Site

| Render setting | Exact value |
| --- | --- |
| Service type | Static Site |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |
| Start Command | **None** |
| Redirects/Rewrites | Source `/*`, Destination `/index.html`, Action **Rewrite** |

Set frontend environment variables:

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://YOUR-BACKEND.onrender.com` — actual backend HTTPS origin, without `/api` |
| `NODE_VERSION` | `24.19.0` |

Vite embeds VITE_API_BASE_URL during the build. Rebuild the Static Site after changing it. No separate frontend demo-mode variable is needed: GET /config on that backend supplies PUBLIC_DEMO_MODE. Rewrites preserve direct navigation to /dashboard, /analysis, /daily-health, /history and /log-symptoms. Do not run Vite's development or preview server on Render. See [Vite static deployment](https://vite.dev/guide/static-deploy#render), [Render rewrites](https://render.com/docs/redirects-rewrites), and version settings for [Python](https://render.com/docs/python-version) / [Node](https://render.com/docs/node-version).

Once service URLs are known, replace both YOUR-* placeholders with those actual origins. Before sharing the future URL, verify /config returns public_demo_mode=true, the banner appears, and all symptom and daily-health records are synthetic. Never expose a PUBLIC_DEMO_MODE=false deployment.

## Database isolation and lifecycle

- Local defaults are unchanged: PUBLIC_DEMO_MODE=false and no DATABASE_PATH use the existing repository data/private/allerwatch.sqlite3, without seeding.
- PUBLIC_DEMO_MODE=true defaults to a separate data/public_demo/allerwatch.sqlite3 if DATABASE_PATH is omitted. Relative DATABASE_PATH values resolve from the repository root, not the working directory.
- Public mode rejects the private directory, aliases of the known private DB, and existing files without the public-demo ownership marker. It does not migrate/import/relabel an unrecognized database. Use a new path; never bypass this check by copying or editing a private database. Interrupted first initialization can leave an unmarked file; select a fresh path rather than importing it or deleting private files.
- A fresh DB is created from the models. The existing offline generators use seed 42 for approximately 90 completed UTC days ending yesterday, plus matching synthetic daily summaries. Both sets are committed together only when **both health tables are empty**. A populated or partially populated demo is never silently reseeded. Normal restarts preserve its entries while its filesystem exists.
- Existing marked demo DBs containing real rows refuse service. The API forces new demo symptom/daily submissions to is_synthetic=true even when a caller sends false. Daily reads/updates address the synthetic summary in demo mode. Local real/synthetic behaviour stays unchanged.
- The UI displays **“Demo mode — do not enter real health information”** on every page. Saves are disabled until the backend mode is known. Demo Analysis initially selects synthetic data; all scientific methods and disclaimers remain unchanged. Visitor entries are demonstrations, not new clinical evidence. Synthetic labels do not anonymize text a visitor enters: use fictional entries only. This is a shared, unauthenticated demonstration; other visitors can see or change demo entries.
- The chosen /tmp database is disposable. Render's default filesystem loses runtime files on redeploy/restart, after which startup creates and seeds a new synthetic DB. It is not private health-record storage. A future explicitly chosen persistent disk would need its own DATABASE_PATH under the mount and a single instance; none is required or provisioned here. [Render filesystem behaviour](https://render.com/docs/disks).

There is no private DB download, database migration from the workstation, live historical exposure backfill or additional model feature. Ordinary exposure timing checks, missing-value rules and real/synthetic analysis separation are preserved.

## Windows verification and local fallback

Existing README local commands still work with these environment variables unset. The frontend falls back to /api, using the existing Vite proxy to http://127.0.0.1:8000. To test demo mode in a separate PowerShell terminal, from the repository root:

```powershell
$env:PUBLIC_DEMO_MODE = 'true'
$env:DATABASE_PATH = Join-Path $PWD 'data\public_demo\allerwatch.sqlite3'
$env:FRONTEND_ORIGIN = 'http://127.0.0.1:5173'
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Stop an existing process on that port yourself before switching modes, or use another port with a matching VITE_API_BASE_URL. To return to local real-data mode, stop the demo process and unset PUBLIC_DEMO_MODE, DATABASE_PATH and FRONTEND_ORIGIN in that terminal before starting the usual backend. Do not change a running database's mode.

Tests use isolated databases and mocked Open-Meteo. Windows verification is not a claim of a completed Render deployment or a fresh Linux dependency installation. No cloud resources or paid disk have been created.

## Preparation verification and changed files

2026-09-24: 461 backend tests and 81 frontend tests passed. Production builds passed with both the local proxy fallback and an explicit VITE_API_BASE_URL. Five source-only/cross-origin browser checks passed: clean startup/seeding, Dashboard/banner, symptom save, daily create/update, and existing analysis/model display. The source-only check used existing Windows dependencies, not a new Linux installation. Existing dependency deprecation and bundle-size warnings remain.

The original private SQLite file, all analysis calculations and both generator implementations are byte-for-byte unchanged. No cloud deployment, private-data copy or local real-data write occurred.

Application/documentation files changed (27):

```text
.gitignore
DEPLOYMENT.md
PROJECT_SPEC.md
README.md
backend/.env.example
backend/app/config.py
backend/app/database.py
backend/app/main.py
backend/app/public_demo.py
backend/app/routers/daily_health.py
backend/app/routers/symptoms.py
backend/tests/test_public_demo.py
frontend/.env.example
frontend/src/App.tsx
frontend/src/api/analysis.ts
frontend/src/api/base.ts
frontend/src/api/dailyHealth.ts
frontend/src/api/environment.ts
frontend/src/api/riskModel.ts
frontend/src/api/symptoms.ts
frontend/src/components/AppConfig.tsx
frontend/src/index.css
frontend/src/pages/Analysis.tsx
frontend/src/pages/DailyHealth.tsx
frontend/src/pages/LogSymptoms.tsx
frontend/src/types/symptoms.ts
frontend/tests/deployment.test.mjs
```

Ignored local verification artifacts are under work/ (render-before.json, render-files.json, render-verification.json, render-demo-check.mjs, render-demo-checks.json, render-demo-dist/, render-source-* and isolated pytest directories). frontend/dist was rebuilt for local preview. None of these files or test databases is needed for Render.
