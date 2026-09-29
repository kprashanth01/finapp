# FinApp

An educational research prototype for a future RL-orchestrated, multi-agent financial advisory system. The current app lets you save a financial profile in PostgreSQL, review a dashboard of saved values and deterministic metrics, and revisit explainable rule-based advisory sessions. Its findings are illustrative project outputs, not professional financial advice.

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

Open the URL printed by Vite, normally <http://localhost:5173>. Enter a user, then use **Profile** to save the financial inputs. **Dashboard** shows the current saved amounts, calculated snapshot, and latest advisory summary. **Advisor** runs an analysis and lists saved sessions; open a past run to see its stored inputs and findings. Refreshing the page loads the current dashboard and latest run again. The API health endpoint remains at <http://localhost:8000/health>.

The income field means **gross monthly income before tax** for the ratios below. Monthly expenses should include monthly debt payments; the separate debt-payment input identifies the portion used for DTI and cannot exceed total expenses. Savings and outstanding debt are balances, while monthly savings contributions and debt payments are flows. Existing profiles keep working because the two new flow inputs are optional.

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

## Goals and the monthly advisory plan

Use **Goals** to create a measurable target: a name, target amount, amount already earmarked, target date, and priority. Edit progress as you save; archive a goal to exclude it from new plans and restore it whenever needed. Completed and overdue goals are supported. No goals are seeded. An earlier free-text goal note stays available under **Earlier goal note**; converting it requires filling and saving a goal form.

Click **Run analysis with saved goals** or run from **Advisor**. The result shows the next step, a monthly savings plan, goal funding gaps, and investment readiness. It uses saved inputs; proposed allocations do not transfer money or change balances. Editing a profile or goal does not automatically run analysis.

### Six independent agents, one shared budget

| Agent | When selected | Output |
| --- | --- | --- |
| Budget | Every saved profile | Expense/savings ratios and recorded monthly savings capacity; expense priority at 80% of gross income |
| Debt | Debt balance or positive payments present | Payment burden; review at 20% DTI or when burden is unknown |
| Emergency fund | Every saved profile | Coverage and gap to three months of expenses |
| Goal planning | Active goals present | Remaining target and required monthly contribution per goal |
| Risk assessment | Every saved profile | Stated preference capped by horizon, with explicit readiness factors |
| Investment | Every saved profile | Prerequisites for investment consideration; coordinator also checks goal funding |

The coordinator allocates **only the recorded monthly savings contribution**, once:

1. Cover the emergency reserve gap up to the available budget. Three months means the reserve should cover three months of expenses; it is not a deadline.
2. Hold the remainder unassigned if debt burden needs review. No extra debt payoff amount is invented. Unknown reserve needs (zero expenses) also hold capacity unassigned.
3. Allocate to future goals in high/medium/low priority order, then earliest deadline, then stable ID. Each receives at most its monthly requirement, remaining target, and available budget.
4. Show remaining money as unassigned. Allocations plus unassigned money always equal the known savings contribution. Missing contribution is unknown; zero is a known zero budget.

A future goal's approximate months are rounded up from days remaining divided by 30. Its required monthly amount is the remaining target divided by those months, rounded up to cents. Completed goals require zero; incomplete goals due today or earlier need a revised deadline and receive no automatic allocation. Goal earmarks do not increase the savings balance; avoid counting emergency money again as goal savings.

For example, with a 500 monthly contribution and a 5,000 reserve gap, the plan allocates 500 to the reserve. If the reserve is already met and two goals need 400 each, the higher-priority goal gets 400 and the second gets 100, leaving a 300 monthly gap. Adjusting a goal, date, or contribution and rerunning produces a new saved plan.

Investment readiness requires positive income and contribution, the reserve target met, no high/unknown debt burden, a positive horizon, and no underfunded or overdue goals. Known blockers yield **Address priorities first**; otherwise missing prerequisites yield **More information needed**. A category appears only when ready: horizons under 3 years cap preference at conservative, 3 to under 7 at moderate, and 7 or more allow the stated preference. These are illustrative project rules, not suitability claims, investment selections, or predictions. No growth or interest is assumed.

### Saved history and reproducibility

Every run stores immutable inputs, goal snapshots, one UTC planning date, agent selection reasons, numerical findings, source references, and the coordinated result. The API separately reports changes to financial inputs, planning date, and rule version. An old run remains visible with its original values; run again explicitly to update it. Name/email edits alone do not mark financial inputs stale. Archived goal edits do not affect active planning inputs.

Earlier v1 sessions retain their original three-agent payload and six captured financial amounts. They are labeled as an earlier format, with no newly reconstructed historical goals or risk fields. History loads newest first in pages of ten. Expand **Why this plan** for the allocation policy and **Research details** for agents, evidence, and version information.

The pipeline uses a replaceable orchestrator interface and structured agent facts as the baseline for future RL work. No trained RL policy or LLM is used yet.

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
| GET | `/users/{id}/goals?include_archived=false` | List active goals (optionally include archived) |
| POST | `/users/{id}/goals` | Create a goal |
| PUT | `/users/{id}/goals/{goal_id}` | Update a goal, preserving archive state |
| PATCH | `/users/{id}/goals/{goal_id}` | Archive/restore with `{ "archived": true/false }` |
| POST | `/users/{id}/advisory-sessions` | Run and save a rule-based advisory session |
| GET | `/users/{id}/advisory-sessions/latest` | Load the latest run and its stale status |
| GET | `/users/{id}/advisory-sessions?limit=10&before_id=<id>` | List newest session summaries with a cursor for older pages |
| GET | `/users/{id}/advisory-sessions/{session_id}` | Load one owned historical run and its stale status |

FastAPI also provides interactive API documentation at <http://localhost:8000/docs>.

## Verification

After installing development requirements, run the focused API checks:

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
```

These tests use a temporary local SQLite database for fast API, rule, persistence, history-order, and ownership checks. Apply Alembic migrations through `0005_financial_goals` and check the browser dashboard/save/run/history/edit/rerun/reload flow against PostgreSQL. From `frontend/`, run `npm test` for the freshness rules and `npm run build` for the production build.

## Current structure

```text
backend/app/             API, validation schemas, and database models
backend/app/services/    Deterministic financial analysis
backend/app/advisory/    State, agents, registry, orchestration, and findings
backend/alembic/         PostgreSQL schema migration
backend/tests/           Focused API behavior checks
frontend/src/components/ Entry forms, dashboard, and analysis/history views
frontend/src/services/   Axios requests
```

## Workflow and limitations

Each meaningful feature is tracked in a GitHub issue and built on a feature branch. Verify it, commit it, open a pull request, and merge only after review.

This is a research prototype, not a financial advisory product. There is no login or access control, so use practice values rather than sensitive real-world information. The database supports multiple user records, but this browser remembers only one user ID and has no profile switcher. Clearing browser storage loses that local link. Authentication and ownership enforcement, trained RL policies, LLM reasoning, and experiment comparisons are future milestones. User-ID scoping keeps routes consistent but is not authentication.
