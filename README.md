# FinApp

An educational research prototype for a future RL-orchestrated, multi-agent financial advisory system. The current app lets you save a financial profile in PostgreSQL, see deterministic metrics, and run a small explainable rule-based advisory session. Its findings are illustrative project outputs, not professional financial advice.

## How the current flow works

```text
React form → Axios request → FastAPI validation → SQLAlchemy → PostgreSQL
                                      ↓
                         saved financial inputs
                                      ↓
                    deterministic financial metrics
                                      ↓
                 financial state → rule-based orchestrator
                                      ↓
                  budget / debt / emergency agents
                                      ↓
                 evidence-backed findings → saved session
                                      ↓
                                  React view
```

The app does not create demo users or financial data. A user ID is kept in this browser's local storage so the same record can be loaded after a refresh. This is a local development convenience, not authentication.

## Requirements

- Git
- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ and npm
- PostgreSQL with a database and login for this project

Docker, API keys, LLM providers, and ML packages are not needed for this issue.

## One-time setup

### 1. Create a PostgreSQL database and login

If you already have a dedicated PostgreSQL login and database, use them and skip these SQL commands. On Windows with PostgreSQL 18, connect with your existing administrator password:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -U postgres -d postgres
```

At the `postgres=#` prompt, run:

```text
CREATE ROLE finapp_dev LOGIN;
\password finapp_dev
CREATE DATABASE finapp OWNER finapp_dev;
\q
```

The `\password` command asks for the new password twice without displaying it. The role and database persist across restarts; do not recreate them each time.

Verify the login:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -U finapp_dev -d finapp -c "SELECT current_user, current_database();"
```

### 2. Configure the backend connection

From the repository root, copy the safe template:

```powershell
Copy-Item .env.example .env
```

Edit the root `.env` file and set:

```text
DATABASE_URL=postgresql+psycopg://finapp_dev:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:5432/finapp
```

URL-encode special characters in the password. The `.env` file is Git-ignored. Keep the password there; do not send or commit it. FastAPI and Alembic read this root file. The `frontend/.env.example` file is only for changing the frontend's API address; the default is `http://localhost:8000`.

### 3. Install packages

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

Run the install commands again only when dependency files change. For backend tests, also install:

```powershell
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

### 4. Apply the database migration

```powershell
Set-Location backend
..\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
Set-Location ..
```

Run migrations when a new database or a new migration is added, not for every app start. Alembic records applied migrations in the database.

## Start a development session

The PostgreSQL Windows service normally starts automatically. Open two PowerShell terminals in the repository root:

**Terminal 1 — API**

```powershell
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

**Terminal 2 — frontend**

```powershell
Set-Location frontend
npm run dev
```

Open the URL printed by Vite, normally <http://localhost:5173>. Enter a user, then enter a financial profile. The snapshot updates from saved inputs. Click **Run analysis** to create a saved advisory session; refresh to load it again. The API health endpoint remains at <http://localhost:8000/health>.

The income field means **gross monthly income before tax** for the ratios below. If you entered take-home pay in an earlier version, edit it. Monthly expenses should include monthly debt payments; the separate debt-payment input identifies the portion used for DTI and cannot exceed total expenses. Savings and outstanding debt are balances, while monthly savings contributions and debt payments are flows. Existing profiles keep working because the two new flow inputs are optional.

## Financial snapshot

The API calculates these values from the current saved profile; it does not store a separate analysis record:

| Metric | Calculation | When unavailable |
| --- | --- | --- |
| Savings rate | Monthly savings contribution ÷ gross monthly income × 100 | Contribution missing or income is zero |
| Debt-to-income ratio | Monthly debt payments ÷ gross monthly income × 100 | Payments missing or income is zero |
| Expense-to-income ratio | Monthly expenses ÷ gross monthly income × 100 | Income is zero |
| Emergency fund coverage | Emergency fund balance ÷ monthly expenses | Expenses are zero |

The **educational health score** is a fixed project heuristic from 0 to 100. It awards up to 30 points for savings rate (full points at 20%), 30 for lower DTI (zero points at 50% or above), and 40 for emergency coverage (full points at 6 months). Each component is clamped to its range and the total is rounded to the nearest whole number. The score is unavailable if any of its inputs are missing or have a zero denominator. These weights and thresholds are illustrative, not calibrated or validated financial guidance. No recommendation is produced from the score.

The DTI input and formula follow the [Consumer Financial Protection Bureau definition](https://www.consumerfinance.gov/ask-cfpb/what-is-a-debt-to-income-ratio-en-1791/): monthly debt payments divided by gross monthly income.

## Advisory session

The advisory session is an explicit run on the **saved** user and profile. It does not read unsaved form values. Three agents return structured findings:

| Agent | When it runs | Illustrative priority rule |
| --- | --- | --- |
| Budget | Every saved profile | Expense-to-gross-income ratio is at least 80% |
| Debt | Outstanding debt or a positive monthly debt payment is recorded | DTI is at least 20% |
| Emergency fund | Every saved profile | Reserve covers less than 3 months of expenses |

Priority findings appear in emergency, debt, then budget order. Open **How agents were selected and what they found** to see every selection reason, the supporting numbers, and any unavailable inputs. If no threshold is crossed, the app says so rather than generating a generic recommendation. The rules compare unrounded saved amounts, although displayed ratios are rounded to two decimal places. They are centralized in `backend/app/advisory/rules.py` and are research examples, not validated advice. In particular, a gross-income ratio cannot establish how much cash is available after tax. The health score does not drive agent selection.

Each run is saved as an immutable `analysis_sessions` row with a rule version, input fingerprint, and structured result. Editing saved financial inputs marks the latest run as stale; it does not rewrite that historical result. Click **Run analysis again** to create a new run. Name and email edits do not mark financial findings stale. Sessions currently show the latest run; a trends view is left for later when there are more types of results to compare.

## API available now

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check API availability |
| POST | `/users` | Create a user |
| GET | `/users/{id}` | Load a user |
| PUT | `/users/{id}` | Update user details, including monthly income |
| PUT | `/users/{id}/financial-profile` | Create or update the user's profile |
| GET | `/users/{id}/financial-profile` | Load the user's profile |
| GET | `/users/{id}/financial-analysis` | Calculate a snapshot from saved inputs |
| POST | `/users/{id}/advisory-sessions` | Run and save a rule-based advisory session |
| GET | `/users/{id}/advisory-sessions/latest` | Load the latest run and its stale status |

FastAPI also provides interactive API documentation at <http://localhost:8000/docs>.

## Verification

After installing development requirements, run the focused API checks:

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
```

These tests use a temporary local SQLite database for fast API, rule, and persistence checks. Apply Alembic migration `0004_analysis_sessions` and check the browser save/run/reload/edit/rerun flow against PostgreSQL. The frontend build check is `npm run build` from `frontend/`.

## Current structure

```text
backend/app/             API, validation schemas, and database models
backend/app/services/    Deterministic financial analysis
backend/app/advisory/    State, agents, registry, orchestration, and findings
backend/alembic/         PostgreSQL schema migration
backend/tests/           Focused API behavior checks
frontend/src/components/ Entry forms and analysis views
frontend/src/services/   Axios requests
```

## Workflow and limitations

Each meaningful feature is tracked in a GitHub issue and built on a feature branch. Verify it, commit it, open a pull request, and merge only after review.

This is a research prototype, not a financial advisory product. There is no login or access control, so use practice values rather than sensitive real-world information. The database supports multiple user records, but this browser remembers only one user ID and has no profile switcher. Clearing browser storage loses that local link. Goal planning, investment and risk agents, RL, LLM reasoning, and experiment results are not implemented yet.
