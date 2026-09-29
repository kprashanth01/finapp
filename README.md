# FinApp

An educational research prototype for an RL-orchestrated, multi-agent financial advisory system. Create an account to save a private financial profile, goals, and rule-based advisory history in PostgreSQL. The Research view compares a trained experimental agent selector with rule-based and random baselines on your saved profile. Its findings are illustrative project outputs, not professional financial advice.

## How the current flow works

```text
Sign-in form → HttpOnly session cookie → FastAPI owner check
                                         ↓
React form → Axios request → FastAPI validation → SQLAlchemy → PostgreSQL
                                      ↓
                         saved financial inputs
                                      ↓
                    deterministic financial metrics
                                      ↓
                 financial state → rule-based orchestrator
                                      ↓
          budget / debt / emergency / goal / risk / investment agents
                                      ↓
                 evidence-backed findings → saved session
                                      ↓
                                  React view
```

The app creates no demo users or financial data. The browser keeps a host-only, HttpOnly session cookie; it no longer uses a local-storage user ID as identity. An expired or revoked session requires sign-in again.

## Requirements

- Git
- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ and npm
- PostgreSQL with a database and login for this project

The backend requirements include NumPy and Gymnasium for the research environment. Installing `backend/requirements.txt` installs both. Docker, API keys, LLM providers, PyTorch, and model downloads are not needed for this issue. No new environment variable or database migration is needed.

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

URL-encode special characters in the database password. The `.env` file is Git-ignored. Keep the password there; do not send or commit it. FastAPI and Alembic read this root file. The frontend defaults to port 8000 on the **same hostname as the page**: a page at `127.0.0.1:5173` calls `127.0.0.1:8000`, while a page at `localhost:5173` calls `localhost:8000`. This keeps the local session cookie on one host. Use `frontend/.env.example` only if the API is elsewhere.

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

Run migrations when a new database or a new migration is added, not for every app start. Alembic records applied migrations in the database. Revision `0006_private_accounts` adds nullable credential fields and session tables without changing existing financial rows.

### 5. Claim an earlier local profile once (existing installs only)

Earlier user records have no password. After applying migration 0006, generate a one-time code on the machine that runs the API:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.legacy_claim --email demo.finapp@example.com
Set-Location ..
```

Replace the email with the exact email on the earlier record. The command prints a code valid for 30 minutes; running it again replaces the prior code. Open **Claim an earlier profile** in the app, enter that email, the code, and a new password of at least 12 characters. The record keeps its user ID, profile, goals, and saved analyses. The app does not choose or display your password. No claim command is needed again after the account is claimed. Knowing an email or an old browser user ID alone cannot claim a record.

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

Open the URL printed by Vite, normally <http://localhost:5173>. Sign in, create an account, or claim an earlier local profile. New accounts first enter gross monthly income in **Profile → User details**, then save their financial profile. **Dashboard** shows current saved amounts, calculated metrics, and the latest advisory summary. **Goals** stores measurable targets. **Advisor** runs an analysis and lists saved sessions. **Research** compares agent-selection methods on the signed-in user's saved profile without saving an advisory session. The desktop sidebar becomes bottom navigation on narrow screens. Refreshing the page reloads the signed-in account. **Sign out** revokes its session. The API health endpoint remains at <http://localhost:8000/health>.

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

The Advisor uses the replaceable rule-based orchestrator and structured agent facts. Research has an experimental trained selector; neither the trained selector nor an LLM generates the saved Advisor plan.

### Research comparison and RL foundation

**Research → Compare methods** evaluates a trained selector, the current rule-based selection, and a seeded random selection on exactly the same saved planning state. Enter a random seed to repeat or vary that baseline; the same seed and saved profile reproduce the same choice. Expand a result to see the score components and the saved values behind them. The page also shows a separate held-out benchmark. None of these comparisons changes balances, creates goals, or saves an advisory session. The Advisor still uses its complete rule-based plan.

`backend/app/rl/` contains the versioned numerical observation, a stable nonempty subset action mapping for the six agents (`0` through `62`), a one-step Gymnasium environment, and an explicit proxy reward. The observation uses bounded ratios for income, expenses, savings contribution, debt, reserve coverage, goals, and horizon; it also includes risk preference and missing-input flags. Agent selection is the action. One step executes the selected agents and ends the episode. It returns the same financial observation because receiving advice cannot itself change someone's finances.

The default `agent-subset-v1` catalogue preserves the exact 63 action IDs expected by the committed model. An `ActionCatalog` can instead take an ordered set of registered agent IDs and a restricted list of allowed combinations; custom mappings receive a content-derived version. The environment can run repeatable episodes over caller-supplied states without adding those states to the database. **Research → Try your own agent selection** lets a signed-in user choose agents on their saved profile and inspect their actual findings. It reports whether the selection includes the facts required by the current Advisor plan: Budget, Emergency Fund, Risk, and Investment, plus Debt or Goal Planning when those are relevant. A valid research action can omit required agents; that means it cannot supply a complete Advisor plan. The experiment never generates or saves a recommendation.

The 16 observation features are documented in `FEATURE_NAMES` in their stable order. Expense, savings-contribution, and debt-payment ratios relate monthly flows to income. Reserve months divided by six and debt balance divided by annual income describe the available buffer and outstanding burden. Active-goal count divided by five, nearest goal's years remaining, and remaining goal amount divided by annual income describe target size and urgency. Horizon divided by 20 and three one-hot risk-preference values describe the recorded investment context. Three flags distinguish absent savings, debt-payment, and horizon inputs from real zeroes; an income flag marks a missing denominator. Values are clipped to bounded ranges so unusually large amounts cannot dominate the vector. Names and order must be versioned together with any future trained model.

The `selection-proxy-v1` reward is the sum of five visible components: +1 per relevant check, +2 per covered critical check, −3 per missed critical check, −0.75 per unneeded check, and −0.15 per agent call. Budget, Emergency Fund, Risk, and Investment Readiness are always counted as relevant; Debt is relevant when a saved debt balance or payment exists, and Goal Planning when an active goal exists. A critical reserve check means coverage is below **three months of expenses** (a balance threshold, not a deadline). A critical debt check means its monthly payment ratio is at least **20% of gross income**, or that ratio is unavailable when debt exists. An active goal with money still to save makes Goal Planning critical. Zero monthly expenses make reserve coverage unavailable and do not trigger its critical check. These are project assumptions, not observed financial outcomes.

The reward audit returned with each Research result lists the relevant and critical agents, missed critical checks, and actual values/thresholds for the reserve, debt, and goal conditions. The rule and seeded random baselines share the same action catalogue and selection interface in `backend/app/rl/baselines.py`; the held-out benchmark uses them too. The fitted model is still trained on this v1 proxy, so the v1 scores and version remain unchanged. The audit explains **why an action got points**, not why the model chose it. The rule baseline uses conditions that overlap the reward, which limits the comparison: a high proxy score cannot establish better financial advice. No financial health improvement, recommendation consistency, or real-world outcome is scored because this dataset has no observed outcome labels.

`python -m app.rl.train` from `backend/` rebuilds `backend/app/rl/model.json` using only NumPy. It generates 1,536 in-memory training scenarios and 384 separate test scenarios with fixed seeds. Scenarios vary income, expenses, debt, emergency reserve, contribution, risk, horizon, and goal timing. They are **generated coverage cases**, not household survey records, saved user profiles, or observed financial outcomes. The trainer calculates all 63 proxy rewards for each training case and fits a small neural network to predict them. The one-step environment makes this a **contextual bandit / one-step RL selection task**, not a long-term financial planning policy. The model artifact includes schema versions, a checksum, seeds, and aggregate benchmark metrics; a missing or incompatible artifact leaves the rule and random comparison available.

The current held-out proxy benchmark (384 generated cases) gives the trained selector **7.79**, the rule-based selector **7.88**, and seeded random selection **1.33** mean points. Critical checks were missed in **0%**, **0%**, and **61.2%** of cases respectively. The rule-based selector matches the proxy oracle here because its selection logic and the reward definition overlap. The learned model is slightly worse under that proxy and **has not demonstrated better financial advice**. A defensible next research step is independent household-data stress testing and an outcome or expert-labelled evaluation target; a survey of financial inputs alone does not provide an advice-quality reward or observed sequential effects.

## API available now

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check API availability |
| POST | `/users` | Create and sign in to an account |
| POST | `/auth/login` | Sign in |
| GET | `/auth/me` | Load the current account from its cookie |
| POST | `/auth/logout` | Revoke the current browser session |
| POST | `/auth/claim` | Claim an earlier local record with a one-time code |
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
| POST | `/users/{id}/research/comparison` | Compare trained, rule, and seeded random selection on the owner's saved profile without saving data; optional JSON `{ "seed": 42 }` |
| GET | `/users/{id}/research/actions` | List the owner's available agent IDs and the stable action-catalogue version |
| POST | `/users/{id}/research/manual-action` | Run selected agents on the owner's saved profile without persistence; JSON `{ "selected_agents": ["budget", "emergency"] }` |
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

These tests use a temporary SQLite database for API, auth, rule, persistence, history, research, and ownership checks. Apply Alembic migrations through `0006_private_accounts` and check signup/sign-in, profile/goals/advisor/research, reload, and sign-out against PostgreSQL. From `frontend/`, run `npm test` and `npm run build`.

## Current structure

```text
backend/app/             API, validation schemas, and database models
backend/app/services/    Deterministic financial analysis
backend/app/advisory/    State, agents, registry, orchestration, and findings
backend/app/rl/          Observation, agent actions, reward, environment, trained research selector, and comparison API
backend/alembic/         PostgreSQL schema migration
backend/tests/           Focused API behavior checks
frontend/src/components/ Entry forms, dashboard, and analysis/history views
frontend/src/services/   Axios requests
```

## Workflow and limitations

Each meaningful feature is tracked in a GitHub issue and built on a feature branch. Verify it, commit it, open a pull request, and merge only after review.

This remains a research prototype, not a financial advisory product. Passwords use Argon2id hashes, sessions are revocable and expire after seven days, and each user-scoped API route checks the signed-in owner. Mutating browser calls carry a custom request header; credentialed CORS is limited to explicit frontend origins. Local loopback HTTP uses a development cookie; non-loopback deployments require HTTPS and a Secure cookie. Set `FINAPP_ALLOWED_ORIGINS` to an explicit comma-separated list of your frontend origins when deploying. Serve only the authenticated API build; an older API process pointed at the same database would still expose its older routes.

Email verification, password recovery, MFA, and deployment-level rate limiting are not in this issue. Use practice values until those controls and a reviewed HTTPS deployment are in place. An independently evaluated RL orchestrator for complete Advisor plans, LLM reasoning, and broader experiments remain future milestones.
