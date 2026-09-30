# FinApp

An educational research prototype for an RL-orchestrated, multi-agent financial advisory system. Create an account to save a private financial profile, goals, and rule-based advisory history in PostgreSQL. Advisor can run rule-based, seeded random, or trained DQN agent selection on your saved profile and trace each new result from agent choice to supporting findings. An optional LLM synthesizes the trace when you request it; the agents and calculations remain deterministic. Research shows a paired evaluation of those three methods on a fixed generated cohort, DQN training evidence, and the earlier fitted proxy comparison. Its findings are illustrative project outputs, not professional financial advice.

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
                  React view → optional evidence-bound LLM wording
```

The app creates no demo users or financial data. The browser keeps a host-only, HttpOnly session cookie; it no longer uses a local-storage user ID as identity. An expired or revoked session requires sign-in again.

## Requirements

- Git
- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ and npm
- PostgreSQL with a database and login for this project

The backend requirements include NumPy and Gymnasium for the research environment. Installing `backend/requirements.txt` installs both. Rule-based and random modes work with this base install; **running the trained RL mode requires `backend/requirements-rl.txt` in the Python environment used to start FastAPI**. This also supports rebuilding the DQN and requires Python 3.12 on Windows. The API reads training metadata without importing PyTorch on startup. No API key is needed for the deterministic app; an OpenAI API key is optional for generated explanations. No new database migration is needed.

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

Open the URL printed by Vite, normally <http://localhost:5173>. Sign in, create an account, or claim an earlier local profile. New accounts first enter gross monthly income in **Profile → User details**, then save their financial profile. **Dashboard** shows current saved amounts, calculated metrics, and the latest advisory summary. **Goals** stores measurable targets. **Advisor** saves a rule-based monthly plan, lists saved sessions, and offers experimental agent-selection runs. **Research** shows the fixed three-way evaluation, DQN training, and the earlier personal comparison. The desktop sidebar becomes bottom navigation on narrow screens. Refreshing the page reloads the signed-in account. **Sign out** revokes its session. The API health endpoint remains at <http://localhost:8000/health>.

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

The saved Advisor plan uses the rule-based orchestrator and structured agent facts. The separate experimental selector in Advisor can run the committed DQN or seeded random policy on your current profile; these runs do not enter saved history.

### Research comparison and RL foundation

**Advisor → Choose how agents are selected** runs the current rule-based policy, a seeded random policy, or the committed trained DQN on the same saved profile. Pick a method and click **Run selected method**. The result shows its action ID, agents that actually ran, their findings, the proxy score, and the score audit. **How this result was reached** connects the policy output to the selected agents, the first actionable finding, actual saved amounts, and reward components. Expand **Explore every selection, finding, and limit** for the full trace. If required agents were omitted, the page names them and withholds the complete monthly plan. If all required agents ran, expand **See coordinated plan from these agents**. These experimental runs are not saved; the usual **Run analysis** button above still creates the saved rule-based plan and history. If the trained model or its Python runtime is unavailable, the RL request reports an error and does not silently switch modes.

New saved rule-based analyses show the same evidence trail beneath **Your next step**. It is stored with each new session, so later profile edits do not rewrite historical explanations. Older sessions without an explanation remain readable; run a new analysis on current values to capture one. Each recommendation in the trace resolves to an actual finding returned by an agent that ran, including relevant numbers and limitations. A partial experimental selection can show individual priority findings but cannot produce a complete monthly plan. The trace records the DQN's action and the state it saw; it does **not** claim individual saved inputs caused the neural policy's choice. Random selection is likewise described as a seeded draw, not a financial inference.

**Research → Compare methods** continues to evaluate the earlier fitted proxy selector, the rule-based selection, and a seeded random selection on the saved planning state. Its older benchmark is separate from the trained DQN. **How the RL selector was trained** displays the DQN's offline evidence. None of these views changes balances or creates goals.

**Research → How the three selectors performed** is the Milestone 6 paired evaluation. It uses 256 generated cases from seed `20261002`, distinct from the DQN's training, validation, and initial test seeds. Rule based and the committed DQN each run once per case; random runs five seeded selections per case. Every selection executes the chosen agents through the same environment. The committed report records a cohort fingerprint, model checksum, schema versions, random seeds, metric definitions, scenario groups, and machine-specific execution timing. It does not read or write saved user profiles. The page shows averages and the paired DQN-versus-rule counts; expand **Coverage, scenario groups, and method** for risk and goal checks, four overlapping scenario groups, and reproduction details.

From `backend/`, run `python -m app.rl.evaluation` with the RL requirements installed to regenerate `backend/app/rl/evaluation_report.json`. The default fixed case count and seeds reproduce all selection and score metrics. Wall-clock execution times can vary by machine and load. The API rejects a report whose model checksum, versions, generated cohort, or basic metric structure no longer match; regenerate after changing the model or evaluation definitions. For custom runs, see `python -m app.rl.evaluation --help`. The report is a versioned experiment artifact, not a live score calculated from an account.

In this committed run, mean proxy scores were **1.3348** for random, **7.8781** for rule based, and **7.8250** for DQN. Critical-check miss rates were **60.47%**, **0%**, and **0%**. DQN chose the same agent set as the rule method in **240 of 256** paired cases and omitted agents needed for a full plan in **16**. These are measured selection results under the project's own reward. The reward shares criteria with the rule method, and the cases are generated rather than sampled from households. No observed financial outcomes, validated recommendation consistency, or recommendation-conflict labels are available, so these results cannot establish advice quality or a superior method.

`backend/app/rl/` contains the versioned numerical observation, a stable nonempty subset action mapping for the six agents (`0` through `62`), a one-step Gymnasium environment, and an explicit proxy reward. The observation uses bounded ratios for income, expenses, savings contribution, debt, reserve coverage, goals, and horizon; it also includes risk preference and missing-input flags. Agent selection is the action. One step executes the selected agents and ends the episode. It returns the same financial observation because receiving advice cannot itself change someone's finances.

The default `agent-subset-v1` catalogue preserves the exact 63 action IDs expected by the committed model. An `ActionCatalog` can instead take an ordered set of registered agent IDs and a restricted list of allowed combinations; custom mappings receive a content-derived version. The environment can run repeatable episodes over caller-supplied states without adding those states to the database. **Research → Try your own agent selection** lets a signed-in user choose agents on their saved profile and inspect their actual findings. It reports whether the selection includes the facts required by the current Advisor plan: Budget, Emergency Fund, Risk, and Investment, plus Debt or Goal Planning when those are relevant. A valid research action can omit required agents; that means it cannot supply a complete Advisor plan. The experiment never generates or saves a recommendation.

The 16 observation features are documented in `FEATURE_NAMES` in their stable order. Expense, savings-contribution, and debt-payment ratios relate monthly flows to income. Reserve months divided by six and debt balance divided by annual income describe the available buffer and outstanding burden. Active-goal count divided by five, nearest goal's years remaining, and remaining goal amount divided by annual income describe target size and urgency. Horizon divided by 20 and three one-hot risk-preference values describe the recorded investment context. Three flags distinguish absent savings, debt-payment, and horizon inputs from real zeroes; an income flag marks a missing denominator. Values are clipped to bounded ranges so unusually large amounts cannot dominate the vector. Names and order must be versioned together with any future trained model.

The `selection-proxy-v1` reward is the sum of five visible components: +1 per relevant check, +2 per covered critical check, −3 per missed critical check, −0.75 per unneeded check, and −0.15 per agent call. Budget, Emergency Fund, Risk, and Investment Readiness are always counted as relevant; Debt is relevant when a saved debt balance or payment exists, and Goal Planning when an active goal exists. A critical reserve check means coverage is below **three months of expenses** (a balance threshold, not a deadline). A critical debt check means its monthly payment ratio is at least **20% of gross income**, or that ratio is unavailable when debt exists. An active goal with money still to save makes Goal Planning critical. Zero monthly expenses make reserve coverage unavailable and do not trigger its critical check. These are project assumptions, not observed financial outcomes.

The reward audit returned with each Research result lists the relevant and critical agents, missed critical checks, and actual values/thresholds for the reserve, debt, and goal conditions. The rule and seeded random baselines share the same action catalogue and selection interface in `backend/app/rl/baselines.py`; the held-out benchmark uses them too. The fitted model is still trained on this v1 proxy, so the v1 scores and version remain unchanged. The audit explains **why an action got points**, not why the model chose it. The rule baseline uses conditions that overlap the reward, which limits the comparison: a high proxy score cannot establish better financial advice. No financial health improvement, recommendation consistency, or real-world outcome is scored because this dataset has no observed outcome labels.

`python -m app.rl.train` from `backend/` rebuilds `backend/app/rl/model.json` using only NumPy. It generates 1,536 in-memory training scenarios and 384 separate test scenarios with fixed seeds. Scenarios vary income, expenses, debt, emergency reserve, contribution, risk, horizon, and goal timing. They are **generated coverage cases**, not household survey records, saved user profiles, or observed financial outcomes. The trainer calculates all 63 proxy rewards for each training case and fits a small neural network to predict them. The one-step environment makes this a **contextual bandit / one-step RL selection task**, not a long-term financial planning policy. The model artifact includes schema versions, a checksum, seeds, and aggregate benchmark metrics; a missing or incompatible artifact leaves the rule and random comparison available.

The earlier fitted model's held-out proxy benchmark (384 generated cases) gives the fitted selector **7.79**, the rule-based selector **7.88**, and seeded random selection **1.33** mean points. Critical checks were missed in **0%**, **0%**, and **61.2%** of cases respectively. The rule-based selector matches the proxy oracle here because its selection logic and the reward definition overlap. The fitted model is slightly worse under that proxy and **has not demonstrated better financial advice**.

### Offline DQN training (Milestone 4)

`backend/app/rl/dqn_training.py` trains a separate Stable-Baselines3 DQN on one sampled action and observed proxy reward per Gymnasium episode. It does **not** train on the full 63-action reward table used by the earlier fitted model. An episode ends after that action, so this is a contextual bandit experiment: there are no simulated future balances or measured household outcomes. The 63-action catalogue, 16-value observation, six agents, and `selection-proxy-v1` reward stay unchanged.

On Windows, use the installed Python 3.12 interpreter to make an isolated training environment; the normal app environment can remain on Python 3.13. From the repository root:

```powershell
py -3.12 -m venv .venv-rl
& '.\.venv-rl\Scripts\python.exe' -m pip install -r backend/requirements-rl.txt
Set-Location backend
& '..\.venv-rl\Scripts\python.exe' -m app.rl.dqn_training
```

The default run uses 1,536 generated training cases, 384 validation cases, and 384 held-out test cases with distinct fixed seeds. It trains for 12,000 environment steps, checks validation at 3,000-step intervals, saves the checkpoint with the highest validation mean proxy score, then evaluates that saved checkpoint once on the test split. For a quick isolated smoke run from `backend/`, use `& '..\.venv-rl\Scripts\python.exe' -m app.rl.dqn_training --output-dir "$env:TEMP\finapp-dqn-smoke" --steps 64 --validation-every 32 --training-cases 24 --validation-cases 8 --test-cases 8`. Step counts must be multiples of four. The output is `dqn_policy.zip` and `dqn_metadata.json` in the chosen directory. The metadata records versions, split seeds and sizes, training settings, dependency versions, checkpoint measurements, the final test result, and the ZIP checksum. `load_dqn_artifact()` rejects incompatible or changed files. Training is CPU-only and does not read the application database. Exact neural weights may differ across library versions or platforms even with the same seeds.

The committed run selected the 12,000-step checkpoint. Its validation mean proxy scores at 3,000, 6,000, 9,000, and 12,000 steps were **7.635**, **7.447**, **7.706**, and **7.827**. On the untouched 384-case test split, the selected DQN scored **7.823** mean proxy points, missed critical checks in **0%** of cases, and selected **5.435** agents on average. These are measured against the project's rule-defined reward; they do not demonstrate better financial advice. A defensible later research step is independent household-data stress testing and an outcome or expert-labelled evaluation target. A survey of financial inputs alone does not provide an advice-quality reward or observed sequential effects.

From `backend/`, inspect the metadata without loading PyTorch using `python -c "from app.rl.dqn_artifact import read_training_evidence; import json; print(json.dumps(read_training_evidence(), indent=2))"`. To verify a saved policy can predict an action, use the research environment: `& '..\.venv-rl\Scripts\python.exe' -c "from app.rl.dqn_artifact import load_dqn_artifact; from app.rl.observation import encode_observation; from app.rl.scenarios import generate_scenarios; model=load_dqn_artifact(); print(model.predict(encode_observation(generate_scenarios(1, seed=91)[0]), deterministic=True)[0])"`.

To enable **Trained RL** on a fresh Windows setup, install `backend/requirements-rl.txt` into the same Python 3.12 environment that starts FastAPI, then restart the API. The committed ZIP and metadata are already included; you do not need to retrain. The selector loads and verifies that ZIP once per API process and predicts an action from the owner's current financial state. A training score is a rule-defined proxy, not an observed change in a person's finances.

## Optional explanation model

The Advisor's **Explain this run** panel appears below a saved plan and below a live selection result. The button sends a small evidence catalogue to the configured OpenAI model: saved financial values, selected agent findings, the selection action, recommendation summary, and recorded limitations. It excludes the account name, email, account ID, cookies, and password fields; user-entered goal names may still appear in recommendation evidence. This transmission occurs only after pressing **Generate explanation**. An older saved session without an explanation trace needs a new analysis run. The generated wording is temporary; it is not written into advisory history.

Set `OPENAI_API_KEY` in the root `.env` file and restart FastAPI to enable the provider. `FINAPP_LLM_MODEL` optionally changes the model; the default is `gpt-4o-mini`. The server calls OpenAI's Responses API with strict structured JSON and `store: false`. OpenAI may still retain abuse monitoring logs under its API data policy, so use practice financial values if you do not want to transmit real amounts. The browser never receives the key.

The response must cite evidence IDs belonging to that exact run. The server validates its structure and screens for unsupported numerical claims, product instructions, and return promises. These checks reduce errors but cannot verify every qualitative sentence or establish financial correctness. If the key is missing, the request fails, or validation fails, the panel labels and shows a deterministic explanation instead. The original calculations and decisions do not change in either path. For a live policy result, the API recomputes the saved state and selection and rejects a changed profile or action before generating text.

To try it: sign in, open **Advisor**, run an analysis, then press **Generate explanation** under the plan. Expand each section's linked evidence to see its source facts. For an RL example, choose **Trained RL**, press **Run selected method**, then use the same explanation button under that result. With no API key, expect **Deterministic explanation** and a configuration note; with a working key, expect **AI-written synthesis**. The exact educational guidance disclaimer appears below both.

## Synthetic financial population (Issue 2)

The research population generator creates **exactly 12,000 anonymous synthetic profiles** from one seed. It does not use the account database, create app users, change the existing `coverage-scenarios-v1` DQN cases, or retrain a model. Each row has a synthetic ID, persona, generation seed, age, base monthly income, aggregate monthly expenses, debt balance and payment, savings contribution, emergency fund, savings balance, risk preference, and investment horizon. Money is written as two-decimal strings in INR. There are no names or email addresses.

The persona mix is an experiment design assumption, not a demographic estimate:

| Persona | Profiles | Share | Assumed base monthly income range | Assumed debt prevalence |
| --- | ---: | ---: | ---: | ---: |
| Gig worker | 3,600 | 30% | ₹12,000–₹80,000 | 30% chance |
| Salaried with loan | 4,200 | 35% | ₹25,000–₹130,000 | 100% by definition |
| Student / fresh graduate | 2,400 | 20% | ₹5,000–₹40,000 | 20% chance |
| Near-retiree | 1,800 | 15% | ₹18,000–₹100,000 | 20% chance |

The code in `backend/app/rl/population.py` also records age ranges, expense fractions, and horizon ranges. These are configurable research assumptions in source, not estimates from household data. All amounts are baseline profile values. The summary's income standard deviation is **across different synthetic users**, not month-to-month income volatility.

From the repository root, using the existing backend environment:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.population --seed 20260930
Set-Location ..
Get-Content data\synthetic\population-v2.summary.json
Get-Content data\synthetic\population-v2.jsonl -TotalCount 2
```

The command prints and writes a validation summary with exact persona counts, average income and expenses, cross-user income variation, debt prevalence, average debt payment, and a SHA-256 digest of the JSONL file. Repeat it with the same seed for identical bytes; change `--seed` for a different population. Use `--output <path>` to write elsewhere. Generated JSONL and summary files under `data/synthetic/` are Git-ignored because they can be reproduced from the source and seed.

No PostgreSQL setup, API key, OpenAI call, new package, or migration is needed for this generator. Monthly trajectories, shocks, and user-level train/test splits are later issues. The current DQN metrics still refer to the earlier single-state coverage cases, not these 12,000 profiles.

### Offline research schema (Issue 3)

The generator now exports `synthetic-population-v2`. It keeps the Issue 2 identity and aggregate fields, then adds `dependents`, `income_volatility`, `fixed_monthly_expenses`, `variable_monthly_expenses`, `debts`, and nullable `dataset_split`. Every debt has a type, outstanding principal, annual interest rate (a fraction, so `0.12` means 12%), monthly EMI, and remaining months. One profile can hold zero, one, or two debts. The assumed volatility is a *relative monthly standard deviation* for a later trajectory generator; it is not the cross-user income spread in the summary and does not generate monthly states yet. The illustrative ranges are 25–55% for gig workers, 2–10% for salaried users, 10–30% for students/graduates, and 3–12% for near-retirees. These ranges are experimental assumptions, not calibrated survey estimates.

`monthly_expenses = fixed_monthly_expenses + variable_monthly_expenses + monthly_debt_payments`; fixed expenses exclude EMI. `existing_debt` and `monthly_debt_payments` equal the sums of debt principal and EMI respectively. The generator validates these equalities, nonnegative balances, debt terms, and feasible savings contributions before export. All `dataset_split` values are `null` in this issue; Issue 6 will assign whole users to train or test. Generated amounts use decimal strings and the same seed produces byte-identical JSONL and a SHA-256 summary. This v2 dataset is a new version; previously generated v1 files are not silently reinterpreted.

This schema is research-only: synthetic IDs do not refer to the private SQL `users.id`, and there is no new table or migration. The existing `User` and `FinancialProfile` tables already hold the live single-month account values. The research path is `SyntheticProfile → SyntheticDebt(s) → future monthly financial states → future orchestrator decisions → future agent results`. The existing six agents, orchestrators, DQN artifact, and saved user data are unchanged. No new installation, PostgreSQL setup, API key, service, or environment variable is required to generate or inspect the dataset.

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
| POST | `/users/{id}/advisory-sessions/{session_id}/reasoning` | Explain an owned captured run; provider is called only on this request |
| POST | `/users/{id}/research/orchestration-run` | Run `rule_based`, seeded `random`, or trained `rl` selection on the owner's saved profile without persistence; JSON `{ "mode": "rl", "seed": 42 }` |
| POST | `/users/{id}/research/orchestration-reasoning` | Explain a live run after verifying `{ "mode", "seed", "state_fingerprint", "action" }` against current state |
| POST | `/users/{id}/research/comparison` | Compare the earlier fitted proxy, rule, and seeded random selection on the owner's saved profile without saving data; optional JSON `{ "seed": 42 }` |
| GET | `/users/{id}/research/training-evidence` | Read verified offline DQN run metadata for the signed-in owner; never loads PyTorch or saved profile data |
| GET | `/users/{id}/research/evaluation` | Read the verified fixed-cohort evaluation report for the signed-in owner; no saved profile data or PyTorch load |
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

Email verification, password recovery, MFA, and deployment-level rate limiting are not in this issue. Use practice values until those controls and a reviewed HTTPS deployment are in place. The fixed synthetic evaluation and optional LLM wording do not establish real-world advice quality; independently labelled outcomes and broader experiments remain future work.
