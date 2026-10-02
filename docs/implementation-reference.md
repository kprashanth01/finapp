# Detailed implementation reference

This is the detailed implementation and experiment history previously kept in the root README. For a first run, start with [the project overview](../README.md) and [local setup](setup.md). Product and research behavior described here reflects the individual milestones; the guides linked from the root README are the entry points for current use.

## Earlier overview

An educational financial planning application with a separate orchestration research area. Create an account to save a private financial profile and goals in PostgreSQL. The Dashboard leads with the latest monthly priority, supporting fact, and proposed use of your recorded savings contribution; Advisor shows the full coordinated rule-based plan and its reasons. Research compares rule-based, seeded random, and trained DQN agent selection on generated cases. The agents and calculations remain deterministic, and experimental results do not establish real-world financial outcomes or professional financial advice.

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

The backend requirements include NumPy and Gymnasium for the research environment. Installing `backend/requirements.txt` installs both. Rule-based and random modes work with this base install; **running the trained RL mode requires `backend/requirements-rl.txt` in the Python environment used to start FastAPI**. This also supports rebuilding the DQN and requires Python 3.12 on Windows. The API reads training metadata without importing PyTorch on startup. No API key is needed for the deterministic app; an OpenAI API key is optional for generated explanations. Apply migration `0007_research_evaluation` before importing research results.

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

Run migrations when a new database or a new migration is added, not for every app start. Alembic records applied migrations in the database. Revision `0007_research_evaluation` adds three research-only tables without changing account or financial rows.

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

Open the URL printed by Vite, normally <http://localhost:5173>. Sign in, create an account, or claim an earlier local profile. New accounts first enter gross monthly income in **Profile → User details**, then save their financial profile. Run analysis from **Dashboard** to get a monthly priority and proposed savings allocation. When inputs change, Dashboard asks for an updated run before presenting allocations as current. **Goals** stores measurable targets. **Advisor** shows the full coordinated plan, saved sessions, and experimental agent-selection runs. **Research** contains the evaluation and DQN evidence. The desktop sidebar becomes bottom navigation on narrow screens. Refreshing the page reloads the signed-in account. **Sign out** revokes its session. The API health endpoint remains at <http://localhost:8000/health>.

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

For an underfunded goal, **Advisor → Can your goals fit?** now shows two choices: the additional monthly amount that goal would need to keep its deadline, and an approximate completion month if its current allocation repeated. A zero allocation has no projected completion date. These are alternatives to consider, not extra available cash or a forecast; the estimate uses 30-day months from that saved run, with no growth or change to reserve, debt, or other goal priorities. Review the goal or the monthly savings contribution, then run a new plan after saving a change.

### Six independent agents, one shared budget

| Agent | When selected | Output |
| --- | --- | --- |
| Budget | Every saved profile | Expense/savings ratios and recorded monthly savings capacity; expense priority at 80% of gross income |
| Debt | Debt balance or positive payments present | Payment burden; review at 20% DTI or when burden is unknown |
| Emergency fund | Every saved profile | Coverage and gap to three months of expenses |
| Goal planning | Active goals present | Remaining target and required monthly contribution per goal |
| Risk assessment | Every saved profile | Stated preference capped by horizon, with explicit readiness factors |
| Investment | Every saved profile | Prerequisites for investment consideration; coordinator also checks goal funding |

New saved runs include each selected agent's finding, supporting figures, why it matters, and a bounded next step. **Advisor** presents these checks after the coordinated plan; **Dashboard** shows this guidance for the current first priority. The agent steps do not assign additional money: only the coordinator's monthly plan proposes allocations. Earlier saved runs without these fields remain readable. The thresholds and wording are educational project rules, not individualized advice.

**Dashboard → What if my income or expenses change?** previews one hypothetical month without editing the saved profile or creating a saved advisory session. Enter gross monthly income, total monthly expenses, and the amount you plan to save in that month, or use **Try 20% less income** as a starting point. The comparison recalculates priorities, reserve coverage, goal funding, and the coordinated monthly allocation using the same rule-based planner and current saved balances, debt payments, and goals. It rejects expenses below required recorded debt payments and a planned savings contribution above gross income minus expenses. This gross remainder is only an upper bound: taxes, timing, and unrecorded costs may reduce spendable cash. A preview is not a forecast and does not move money. Save real changes in Profile and run a new plan when they occur.

The scenario result leads with **What this means this month**: the first priority, any cash shortfall, changes to planned savings and reserve funding, the largest change to a goal's monthly gap, and a suggested next step. Open **Detailed comparison** for every calculated amount. A blank savings contribution produces no funded allocation; the result does not treat it as zero.

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

**Advisor → Ask about this saved run** appears after a newly saved analysis. Choose a suggested question or type one, then expand **Evidence from this run** under its answer to inspect the captured recommendation, amounts, findings, or selection decision used. Follow-up questions such as “Why?” retain the prior topic within the open page. Answers come from that selected session's stored state and explanation even if the profile has since changed; the page flags a stale run. Unsupported questions receive a scope limit rather than invented values or predictions. The question endpoint requires the session owner, never changes the financial profile or plan, and does not save chat messages. This deterministic chat needs no API key, migration, or new service. It is separate from the optional OpenAI narrative panel below it.

**Research → Compare methods** continues to evaluate the earlier fitted proxy selector, the rule-based selection, and a seeded random selection on the saved planning state. Its older benchmark is separate from the trained DQN. **How the RL selector was trained** displays the DQN's offline evidence. None of these views changes balances or creates goals.

**Research → How the three selectors performed** is the Milestone 6 paired evaluation. It uses 256 generated cases from seed `20261002`, distinct from the DQN's training, validation, and initial test seeds. Rule based and the committed DQN each run once per case; random runs five seeded selections per case. Every selection executes the chosen agents through the same environment. The committed report records a cohort fingerprint, model checksum, schema versions, random seeds, metric definitions, scenario groups, and machine-specific execution timing. It does not read or write saved user profiles. The page shows averages and the paired DQN-versus-rule counts; expand **Coverage, scenario groups, and method** for risk and goal checks, four overlapping scenario groups, and reproduction details.

From `backend/`, run `python -m app.rl.evaluation` with the RL requirements installed to regenerate `backend/app/rl/evaluation_report.json`. The default fixed case count and seeds reproduce all selection and score metrics. Wall-clock execution times can vary by machine and load. The API rejects a report whose model checksum, versions, generated cohort, or basic metric structure no longer match; regenerate after changing the model or evaluation definitions. For custom runs, see `python -m app.rl.evaluation --help`. The report is a versioned experiment artifact, not a live score calculated from an account.

**Research evaluation database (Issue 23):** After applying migration `0007_research_evaluation`, import the verified committed report from `backend/`:

```powershell
..\.venv\Scripts\python -m app.rl.evaluation_store
```

The importer rejects a report that no longer matches the installed model/cohort and is safe to rerun: the report digest identifies one experiment. `experiments` records the report, scenario and model versions, synthetic cohort checksum, definitions, and limitations. `experiment_runs` keeps the method, scenario, scope (`aggregate` or individual random `seed`), unique case count, selection sample count, and import timestamp. `experiment_metrics` stores each measured numeric value by name. Missing measurements are absent, never represented as zero. Segment totals pool all seeds for random; they are not individual seeded runs. The timestamp means **when the report was imported**, since the source report does not record measurement time. This data is separate from private `analysis_sessions` and does not copy saved user profiles. No extra package, API key, or model service is needed; an existing PostgreSQL connection is required.

**Research → Explore measured results (Issue 24)** reads the latest imported experiment from those tables. By default it shows aggregate mean proxy reward across all generated cases for Random, Rule-Based, and DQN. Change **Method**, **Scenario**, and **Metric** to inspect recorded values for reward, risk coverage, goal alignment, average agents, execution time, reward variance, and other measured checks. **Result set → Individual random seeds** shows the five separate Random runs on the overall cohort. The table distinguishes unique cases from selection samples; scenario groups overlap and Random aggregates pool five seeds. Recommendation consistency and conflicts appear as **not measured** because this experiment has no validated recommendation comparison. The page never selects a winning method automatically. If the panel says no experiment is imported, apply migration `0007_research_evaluation` and run the import command above. The older summary still reads the verified report file. This dashboard adds no new migration, package, API key, or service beyond Issue 23's PostgreSQL setup.

**Controlled variable-income experiment (Issue 25):** From `backend/`, run `..\.venv\Scripts\python -m app.rl.variable_income_experiment` to compare Random, Rule-Based, and the committed monthly DQN on five editable synthetic financial scenarios. Inspect `data/synthetic/variable-income-experiment-v1/summary.json` and the per-scenario raw traces. The runner keeps held-out users and months paired, guarantees the named income shocks, and reports how many actions change from stable-income scenario A. See [the experiment guide](./variable-income-experiments.md) and [editable settings](../experiments/variable-income-scenarios.json). This offline run adds no website screen, database migration, API key, or service. It uses the already installed RL requirements and makes no financial-outcome claim.

**Agent-priority conflict cases (Issue 26):** From `backend/`, run `..\.venv\Scripts\python -m app.rl.conflict_experiment` and open `data/synthetic/conflict-scenarios-v1/summary.json`. Three controlled cases record actual selected-agent findings, supported conflicts, each method's action and reward, and the complete or withheld recommendation. The rule policy exposes a reserve-first allocation, debt-review hold, and goal-before-investment deferral. The committed DQN omits Goal in these cases, so its results stay partial; the report does not label them resolved. See [the conflict guide](./conflict-scenarios.md). This is an offline research artifact with no new website screen or setup dependency beyond the existing RL environment.

**Ablation experiments (Issue 27):** From `backend/`, run `..\.venv\Scripts\python -m app.rl.ablation_experiment` and inspect `data/synthetic/monthly-ablations-v1/summary.json`. On the same held-out Scenario B users, the runner compares the original state with zero income volatility and no simulator shocks. It can also suppress a chosen agent after policy selection and recompute the synthetic selection reward without relabeling the policy action or retraining it. Use `--ablations` and `--agent` to select interventions. [The ablation guide](./ablation-experiments.md) explains the paired comparisons, existing no-RL and no-LLM controls, and limits. This offline research run adds no website screen or setup requirement beyond the existing RL Python environment.

**Monthly DQN website demo (Issue 29):** On the signed-in Research page, expand **View the prepared research example**, then press **Run monthly DQN demo** to replay one held-out synthetic salaried worker's income drop. Month buttons show the same financial states to the trained monthly DQN and rule baseline, including actual selected-agent findings and an auditable selection-proxy comparison. This read-only example is separate from the account profile. See [the demo walkthrough and limits](./monthly-dqn-website-demo.md). It needs the existing local backend and RL dependencies, but no API key or database migration.

**Your own monthly financial history:** Apply migration `0008_financial_months`, then open **Months** from the primary navigation. A new record starts blank; you may explicitly copy current Profile figures as a starting point. Enter total spending once, essential bills, and the loan payment due; other spending is calculated. Review actual payments and balances in the visible section before saving. Enter an ordinary month, then a later month with changed income or expenses. The Months view compares the latest entered income less spending with the planned monthly savings contribution in Profile, and illustrates whether the lowest income among up to 12 entered months would cover the latest essential bills and scheduled loan payment. You can select an entered month and use an optional worksheet to subtract unrecorded costs and cash you want to keep available from that month's income less spending, then use the resulting amount to preview the existing rule-based coordinated plan with current goals. The preview does not save a new plan or update your Profile. Its gross cash remainder is only an upper bound; a recorded missed loan payment or unfunded bill blocks a new funded allocation. It does not forecast income. **Research → Build your own month-by-month situation** still lets you select a month to run the committed monthly DQN and rule baseline on *your entered values*, request a specialist, and ask a question grounded in that month's evidence using the existing local Ollama model. See [the month-entry walkthrough and limits](./account-monthly-advice.md). The DQN is not retrained on your account and can miss critical checks; the research page marks those misses and shows the rule baseline.

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

## Local Advisor chat

The **Ask about this saved run** panel below an Advisor session now uses a local Ollama chat model for open-ended questions and short follow-ups. [Install Ollama](https://ollama.com/download) if needed, run `ollama pull qwen3.5:4b`, then restart FastAPI. No API key or cloud model is needed for this chat. The default model is `qwen3.5:4b`; `FINAPP_CHAT_MODEL` can select another locally installed Ollama model. The model download is about 3.4 GB. Its responses may be slower on a CPU.

The browser sends the question and up to six earlier question/answer pairs to the API. The API sends those and a catalogue of the **selected saved run's** financial values, agent findings, decision, recommendation, plan and limitations to Ollama at `127.0.0.1:11434`. Broad overview questions receive a compact catalogue of the run's sections. Account name, email, and authentication data are excluded. Messages and generated answers are not saved to advisory history. The server checks the model's evidence IDs and rejects numbers absent from the cited facts, assumed currencies, and certain unsupported instructions or promises. These checks reduce errors, but cannot prove every sentence correct; the evidence cards remain available to inspect. If Ollama is absent or its answer fails validation, the UI labels the answer as a saved-run fallback.

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

No PostgreSQL setup, API key, OpenAI call, new package, or migration is needed for this generator. Monthly trajectories, shocks, and user-level train/test splits are described below. The current DQN metrics still refer to the earlier single-state coverage cases, not these 12,000 profiles.

### Offline research schema (Issue 3)

The generator now exports `synthetic-population-v2`. It keeps the Issue 2 identity and aggregate fields, then adds `dependents`, `income_volatility`, `fixed_monthly_expenses`, `variable_monthly_expenses`, `debts`, and nullable `dataset_split`. Every debt has a type, outstanding principal, annual interest rate (a fraction, so `0.12` means 12%), monthly EMI, and remaining months. One profile can hold zero, one, or two debts. The assumed volatility is a *relative monthly standard deviation* for a later trajectory generator; it is not the cross-user income spread in the summary and does not generate monthly states yet. The illustrative ranges are 25–55% for gig workers, 2–10% for salaried users, 10–30% for students/graduates, and 3–12% for near-retirees. These ranges are experimental assumptions, not calibrated survey estimates.

`monthly_expenses = fixed_monthly_expenses + variable_monthly_expenses + monthly_debt_payments`; fixed expenses exclude EMI. `existing_debt` and `monthly_debt_payments` equal the sums of debt principal and EMI respectively. The generator validates these equalities, nonnegative balances, debt terms, and feasible savings contributions before export. All `dataset_split` values remain `null` in this population export; the Issue 6 workflow below assigns whole users to train or test. Generated amounts use decimal strings and the same seed produces byte-identical JSONL and a SHA-256 summary. This v2 dataset is a new version; previously generated v1 files are not silently reinterpreted.

This schema is research-only: synthetic IDs do not refer to the private SQL `users.id`, and there is no new table or migration. The existing `User` and `FinancialProfile` tables already hold the live single-month account values. The research path is `SyntheticProfile → SyntheticDebt(s) → future monthly financial states → future orchestrator decisions → future agent results`. The existing six agents, orchestrators, DQN artifact, and saved user data are unchanged. No new installation, PostgreSQL setup, API key, service, or environment variable is required to generate or inspect the dataset.

### Volatile monthly trajectories (Issue 4)

`backend/app/rl/trajectories.py` generates 12 monthly states per synthetic user by default: **144,000 rows for 12,000 users**. Every row carries the synthetic ID, persona, month, seeds, income, fixed and variable expenses, scheduled and paid EMI, cash flow, liquid savings, emergency reserve, investment value, debt balance, missed-payment flag, and ratios. Each user's random stream is derived from their identity and the trajectory seed, so exporting one user produces the same months as exporting the full population. The current `synthetic-trajectories-v1` data is separate from the app's `FinancialState`/DQN observation and does not change the committed DQN evaluation.

Income is independently sampled each month around base income using the profile's assumed relative monthly volatility and is floored at zero. Variable expenses receive an independent 8% relative standard deviation by default; fixed expenses stay fixed. These are illustrative simulation assumptions, not calibrated forecasts. The generator pays fixed expenses, then scheduled debt obligations, then variable expenses from income plus liquid savings. Other savings are used before the earmarked emergency reserve. If available money is insufficient, it records unfunded non-debt expenses and/or a missed EMI; unpaid loan interest remains in outstanding debt. Positive cash remaining after expenses is held as liquid savings. Advisory agent selection does not change any balance, and the investment value stays zero because no portfolio or return process exists. The default `synthetic-trajectories-v1` export has no discrete shock events; Issue 5 adds a separate opt-in event version below. The month ratios are descriptive values, not the versioned RL observation that Issue 7 will define.

From the repository root, preview all 12 months for one user without writing the full cohort:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.trajectories --synthetic-id 1
Set-Location ..
Get-Content data\synthetic\trajectories-v1.summary.json
Get-Content data\synthetic\trajectories-v1.jsonl -TotalCount 12
```

Omit `--synthetic-id 1` to export the full 12,000-user cohort; use `--population-seed`, `--trajectory-seed`, `--months`, `--expense-volatility`, and `--output` to configure a run. The summary records row counts, per-persona within-user income variation, shortfall counts, and the JSONL SHA-256. Use `--output` to keep a one-user preview separate from a full export. Generated files are ignored by Git. No new package, migration, PostgreSQL connection, API key, or external service is needed for this command.

**Website check:** Start the API and frontend using the instructions above and open [FinApp](http://127.0.0.1:5173/). Sign-in and the existing Research view should still work, but this offline dataset has no website visualization yet. Research continues to show the earlier fixed-cohort DQN experiment; it must not be read as a result on these monthly trajectories. A trajectory viewer is a later milestone.

### Configurable financial shocks (Issue 5)

Pass `--shocks` to export `synthetic-trajectories-v2`; omitting shock options keeps the exact v1 dataset and its seed behavior. In v2, a separate per-user random stream selects a new event with a default **10% chance in each month without an ongoing income loss**. The event types are low income (income multiplied by `1 - magnitude`), temporary income loss (zero income for two months by default), high income (`1 + magnitude`), unexpected expense (added to variable spending), emergency expense (added to fixed essential spending), and debt pressure (extra scheduled EMI, capped at balance plus interest). Debt pressure is eligible only while the user has outstanding debt. One event starts at most per month; a temporary loss can continue into following months. Normal baseline income and expense draws stay paired with the v1 seed, so the difference between runs comes from the configured event layer.

The defaults are event probability `0.10`, magnitude `0.50`, unexpected expense ₹20,000, emergency expense ₹30,000, and two income-loss months. `--income-volatility` can override each persona's baseline relative volatility for a stress test. These are **experimental stress settings**, not forecasts or demographic estimates. Every v2 monthly row records its event type, whether it started that month, whether income was shocked, and the event's added expense, EMI, or income change. The summary records event starts and affected months separately, all settings, the JSONL checksum, and the usual cohort counts. Shocks can deplete savings or leave expenses/EMIs unpaid under the same Issue 4 cash-flow rules; selecting advisory agents still causes no simulated household action.

Preview one user's changing states with the example settings:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.trajectories --synthetic-id 1 --shock-probability 0.40 --shock-magnitude 0.50 --unexpected-expense 20000 --income-volatility 0.40 --output ..\data\synthetic\user-1-shocks.jsonl
Set-Location ..
Get-Content data\synthetic\user-1-shocks.summary.json
Get-Content data\synthetic\user-1-shocks.jsonl | ConvertFrom-Json | Select-Object month_index,event_type,income,scheduled_expenses,paid_emi,savings,emergency_fund,missed_payment | Format-Table
```

Omit `--synthetic-id 1` and use `--shocks` for the full v2 cohort. Use `--event-types low_income emergency_expense` to restrict the event catalogue, `--emergency-expense` to change that amount, or `--income-loss-months` to change the duration. Changing the seed or settings changes the generated trajectory; the same inputs reproduce it. No package, migration, PostgreSQL connection, API key, or external service is needed for the offline export. User-level train/test assignment is described below; dynamic RL evaluation remains a later milestone.

**Website check:** The locally running app at [FinApp](http://127.0.0.1:5173/) still shows its existing pages. This research-only v2 dataset is not yet displayed by the website, and the Research page's existing DQN numbers are not measured on shocked trajectories. Inspect the JSONL preview above to see this issue's changed states; the later trajectory viewer will provide a browser view.

### User-level train/test split (Issue 6)

`backend/app/rl/splits.py` assigns each synthetic user once, using a separate seed and an **80% train / 20% test split inside each persona**. It sorts user IDs before seeded shuffling, so input row order does not change membership. The default 12,000-user population produces **9,600 train and 2,400 test users**: gig 2,880/720, salaried 3,360/840, student/fresh graduate 1,920/480, and near-retiree 1,440/360. These are experimental partitions, not demographic estimates. The original population and v1/v2 trajectory exports remain unassigned and byte-compatible; the new `synthetic-user-split-v1` manifest records one assignment per user.

Pass `--split-seed` to the trajectory exporter to assign the complete population **before** applying any user or train/test filter. Every month inherits its user's assignment. Unshocked split exports use `synthetic-trajectories-v3`; shock-enabled split exports use v4. `--selected-split train` and `--selected-split test` create separate files without overlapping synthetic IDs. For 12 months, they contain 115,200 train rows and 28,800 test rows. A one-user preview gets the same assignment as the full export with the same population and split seeds. No monthly row is independently randomized.

From the repository root, generate and inspect the manifest and both shock-enabled datasets:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.splits --split-seed 20261002
..\.venv\Scripts\python -m app.rl.trajectories --shocks --split-seed 20261002 --selected-split train
..\.venv\Scripts\python -m app.rl.trajectories --shocks --split-seed 20261002 --selected-split test
Set-Location ..
Get-Content data\synthetic\user-splits-v1.summary.json
Get-Content data\synthetic\trajectories-v4-train.summary.json
Get-Content data\synthetic\trajectories-v4-test.summary.json
```

All generated JSONL and summaries remain Git-ignored and can be reproduced from their seeds. The summaries carry user and row counts, versions, filters, and SHA-256 digests. No new package, migration, PostgreSQL connection, API key, or external service is needed. These split datasets have **not** trained or evaluated the committed DQN; later issues will define the dynamic observation and run controlled experiments.

**Website check:** Open the running [FinApp](http://127.0.0.1:5173/) to confirm sign-in and existing Research still load. This issue changes offline dataset assignment and adds no visible page; the existing Research scores do not use these split trajectories. Inspect the three summaries above to see the new result now.

### Dynamic financial state and normalized observation (Issue 7)

`backend/app/rl/dynamic_state.py` joins one synthetic profile with one of its monthly records into `dynamic-financial-state-v1`. It records current income and obligations, savings and emergency reserve, outstanding debt, the currently zero modeled investment value, expense/debt/reserve ratios, risk preference, investment horizon, effective income volatility, recent income change, missed payment, observed low income, and liquidity pressure. Identity, persona, train/test assignment, month, and the simulator's event label remain available as inspection metadata. The builder rejects a mismatched user/split or inconsistent monthly totals. When a trajectory uses `--income-volatility`, pass that override to the builder; the preview command below does this automatically.

The separate `dynamic-observation-v1` encoder produces **19 finite features in [−1, 1]**. Each feature name and its reason are listed by the preview command and in `DYNAMIC_FEATURE_RATIONALE` beside the encoder. The groups are:

| Features | Scale | Why included |
| --- | --- | --- |
| Current income | `log1p(income) / log1p(₹200,000)`, capped at 1 | Retains absolute earning capacity without letting large amounts dominate. |
| Total expenses, fixed expenses, scheduled EMI | Ratios to income, capped at 2/2/1 and mapped to 0–1 | Separates overall cost, essential cost, and debt-service pressure. |
| Total savings, emergency fund | Months of scheduled expenses, capped at 12 and mapped to 0–1 | Separates total liquidity from earmarked reserves. |
| Outstanding debt | Debt / annualized current income, capped at 5 and mapped to 0–1 | Represents balance burden beyond one month's EMI. |
| Income volatility, recent change | Volatility capped at 1; recent change clipped to −1…1 | Exposes uncertainty and the direction of the latest income movement. |
| Scheduled cash flow, unfunded expenses, missed EMI, observed low income | Cash flow / income clipped to −1…1; unfunded share 0–1; binary flags | Shows immediate liquidity pressure and unmet obligations. The low-income flag is derived from observed income ≤60% of base, never from the simulator's event label. |
| Horizon and risk preference | Horizon / 40 years capped at 1; three one-hot flags | Preserves the user's stated long-term context. |
| Zero-income and missing-recent-change flags | Binary | Disambiguates a zero ratio from an undefined denominator. |

The encoder deliberately excludes synthetic ID, persona, train/test assignment, and the simulator's event name to avoid giving a future policy privileged experiment labels. Its fixed scaling limits are set from documented synthetic ranges, not fitted on held-out test users. Month 1's recent income change compares with base income; later months compare with the preceding generated month. The encoder also omits goal gap/priority, health score, and a claimed realized savings rate: the current synthetic trajectory has no goals, validated outcome score, or tracked savings-contribution decision. Volatility is an experiment setting here; a live system would need to estimate it from observed history. The existing `FinancialState`, `PlanningState`, `planning-observation-v1`, and committed 16-feature DQN remain unchanged. No dynamic DQN has been trained or evaluated yet.

Preview a split-assigned user's monthly state and feature vector from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_state --synthetic-id 1 --split-seed 20261002 --shocks --months 3
```

Expect the state and observation version strings, feature names and rationales, and three month rows. Compare income, cash flow, reserves, and observation values across rows. The dataset remains offline; no new package, migration, PostgreSQL connection, API key, or external service is needed. **Website check:** The running [FinApp](http://127.0.0.1:5173/) should still load, but Issue 7 adds no visible page. Research still shows the earlier 16-feature DQN evidence, not a result from this dynamic encoder.

### Existing agents on changing monthly finances (Issue 8)

`backend/app/advisory/dynamic.py` adapts each `dynamic-financial-state-v1` synthetic month to the six existing agents' `analyze(state)` interface. The adapter carries current income, fixed and variable costs, scheduled EMI, liquid balances, recent income change, expected volatility, current surplus, missed payments, and the highest contractual debt APR. **Current surplus is income minus scheduled expenses, not an observed savings contribution.** Synthetic profiles have no financial goals; the preview can add a clearly labeled example goal supplied by the caller. Saved-profile advice keeps its existing contract and behavior. The rule-based and trained DQN selectors are not yet using these monthly agent results.

The Budget Agent now checks current cash pressure and recent income decline. Debt checks scheduled EMI, missed payments, liquidity, and a contractual rate of at least 12%. Emergency uses an illustrative three-month target for stable conditions and six months when volatility is at least 25% or current income is at most 60% of base income. Investment checks current surplus, that month's reserve target, debt pressure, income stability, risk preference, and horizon; it never names a security. Goal Planning compares each supplied goal's monthly need with current surplus and competing reserve/debt needs without pretending money was actually allocated. Risk Assessment caps its illustrative category when a month has severe income or liquidity stress. These thresholds are experimental assumptions for comparing orchestration, not calibrated household advice. Every agent returns its existing structured result with evidence and limitations.

From the repository root, preview three seeded months and all six results:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.advisory.dynamic --synthetic-id 1 --months 3 --shocks --shock-probability 0.5 --goal-target 12000 --goal-months 6
```

The JSON contains each month's income and cash flow, plus `budget`, `debt`, `emergency`, `goal`, `risk`, and `investment` findings. Compare `priority`, reserve `gap`, investment `status`, and risk `category` as the income changes. Omit both `--goal-target` and `--goal-months` to see the real no-goal synthetic case. There is no new package, migration, PostgreSQL connection, API key, external service, or environment variable. **Website check:** The existing [FinApp](http://127.0.0.1:5173/) should load, but Issue 8 adds no visible website change. The Research page still reports the earlier 16-feature DQN experiment; it does not show these new monthly agent findings yet.

### Agent action space review (Issue 9)

The current `agent-subset-v1` action catalogue has **63 IDs**: all nonempty subsets of the six registered agents. This is one agent-selection decision on one financial state. Every selected agent reads that same state; the action does not encode an ordered advisory sequence, simulate a later financial state, or execute a transaction. For example, action `0` is Budget, `1` is Debt, `2` is Budget + Debt, and `62` selects all six. The default mapping and version stay fixed because the committed DQN expects them. The existing `ActionCatalog.from_agents(...)` supports a restricted set or different registered agents in research code, assigning a separate content-derived version. A model trained on `agent-subset-v1` cannot be assumed compatible with such a custom catalogue.

Inspect the full mapping without signing in:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.selection
```

The JSON lists `selection_semantics`, action version/count, registered agents, and every `id` → `agents` mapping. For the visible website change, sign in, open **Research → Explore your saved profile → Try your own agent selection**, and choose one or more agents. The page previews the exact action ID and has an expandable **All 63 action mappings** table. Running a choice still executes only those agents and reports the project's experimental score; the review did not retrain the DQN or change any reward, agent, or saved profile. No new package, migration, PostgreSQL connection, API key, external service, or environment variable is required.

### Dynamic monthly reward (Issue 10)

The separately versioned `dynamic-selection-proxy-v1` scores agent selection against one observed synthetic month. Its five reported components cover relevant and critical checks, missed checks, unnecessary agents, and call cost. Current cash flow, reserve coverage, volatility, missed payments, debt burden, and unfinished goals can change those checks from month to month. The exact rules, weights, assumptions, and limitations are in [docs/dynamic-reward.md](./dynamic-reward.md).

Run the read-only example from `backend/`:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_reward --synthetic-id 1 --months 3 --seed 4 --shocks --shock-probability 0.5 --selected budget investment
```

Inspect each month's `components`, `critical_agents`, and `checks`; `total_reward` is their component sum in project points. No PostgreSQL connection, API key, external model, migration, new package, or environment variable is needed. The existing website and trained DQN still use the earlier `selection-proxy-v1`; **this issue adds no new website screen** or measured financial-outcome score.

### Multi-month Gymnasium environment (Issue 11)

`DynamicAgentSelectionEnv` runs one selection per generated month. Gymnasium `reset()` returns the first 19-feature monthly observation; `step(action)` runs the selected agents, reports their actual priority findings and dynamic reward audit, then returns the next precomputed month. The final month terminates the episode. The next financial state is independent of the action, so this is a temporal **selection** experiment, not a simulation of financial improvement from advice. The old one-step environment and committed DQN are unchanged. See [docs/dynamic-environment.md](./dynamic-environment.md) for the full contract and a three-month trace.

Run the read-only example from `backend/`:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_environment --synthetic-id 1 --months 3 --seed 4 --shocks --shock-probability 0.5 --selected budget investment
```

The JSON shows one action, its agent findings and priority actions, reward components, and next-month index at each step. The existing website has no new screen for this backend milestone. No new package, PostgreSQL connection, migration, API key, external model, or environment variable is required.

### DQN training on monthly episodes (Issue 12)

`backend/app/rl/dynamic_training.py` fits a separate 19-feature DQN on generated monthly episodes. It separates whole synthetic users into training, validation, and held-out test cohorts, selects the best checkpoint on validation proxy reward, and records the one-time test result and model checksum in a versioned artifact. The earlier one-step DQN remains the website's Research model. See [docs/dynamic-dqn-training.md](./dynamic-dqn-training.md) for the reproducible command, split design, and interpretation limits.

Run the offline experiment from `backend/` after installing `requirements-rl.txt`:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_training --steps 12000 --validation-every 3000 --training-users 256 --validation-users 64 --test-users 64 --months 12
```

The CLI prints the saved artifact path, chosen step, and held-out test proxy metrics. This issue adds no new website screen and does not use saved account data. Its score does not measure financial improvement.

### Monthly RL model management (Issue 13)

The monthly DQN has `save_model()`, `load_model()`, `model_exists()`, and `get_model_metadata()` helpers with explicit name, version, UTC training date, checkpoint steps, environment, seed, dataset, and checksum checks. Repeated loads of a valid artifact reuse the in-process model. The older website selector keeps its existing cache. See [docs/rl-model-management.md](./rl-model-management.md) for the contract and inspection command.

From `backend/`, run `..\.venv\Scripts\python -m app.rl.dynamic_model_management` to inspect the committed model provenance. This backend milestone adds no new website screen or account-data use.

### Configured Advisor selector (Issue 14)

Set `ORCHESTRATOR_MODE=rule_based`, `random`, or `trained_rl` in the root `.env` and restart the backend. On the signed-in **Advisor** page, scroll below the saved plan to **Choose how agents are selected → Server default**. This experimental selector runs the configured method and shows which one ran. Explicit selections on the same page still run the chosen method, and the old `rl` API value remains an alias for trained RL. The default when unset is `rule_based`. The separate **Research → Try your own agent selection** panel is for manual agent choices. See [docs/orchestrator-mode-switching.md](./orchestrator-mode-switching.md) for the API contract, website check, and scope.

This switch controls read-only experimental runs on saved snapshot profiles. Saved **Advisor** sessions remain complete rule-based plans; the new monthly DQN remains offline until its separate integration work.

### Trained monthly DQN and existing agents (Issue 15)

The offline monthly policy now has an end-to-end trace: synthetic financial state → 19-feature observation → saved DQN action → 63-subset action mapping → only the selected existing agents → their actual findings and gated recommendation → dynamic reward → JSONL log. A coordinated plan is built only when the selected agents cover the required checks. The generated next month remains independent of the selection. See [docs/dynamic-dqn-agent-integration.md](./dynamic-dqn-agent-integration.md) for the trace contract and a worked example.

From `backend/`, run `..\.venv\Scripts\python -m app.rl.dynamic_integration --months 3` and inspect `..\data\synthetic\dynamic-dqn-agent-trace-v1.jsonl`. This synthetic-only path adds no website screen; the signed-in Advisor selector still uses the earlier snapshot DQN.

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
| POST | `/users/{id}/advisory-scenario` | Compare current saved inputs with one read-only hypothetical month; JSON `monthly_income`, `monthly_expenses`, `monthly_savings_contribution` |
| POST | `/users/{id}/advisory-sessions/{session_id}/reasoning` | Explain an owned captured run; provider is called only on this request |
| POST | `/users/{id}/research/orchestration-run` | Run `rule_based`, seeded `random`, or trained `rl` selection on the owner's saved profile without persistence; JSON `{ "mode": "rl", "seed": 42 }` |
| POST | `/users/{id}/research/orchestration-reasoning` | Explain a live run after verifying `{ "mode", "seed", "state_fingerprint", "action" }` against current state |
| POST | `/users/{id}/research/comparison` | Compare the earlier fitted proxy, rule, and seeded random selection on the owner's saved profile without saving data; optional JSON `{ "seed": 42 }` |
| GET | `/users/{id}/research/training-evidence` | Read verified offline DQN run metadata for the signed-in owner; never loads PyTorch or saved profile data |
| GET | `/users/{id}/research/evaluation` | Read the verified fixed-cohort evaluation report for the signed-in owner; no saved profile data or PyTorch load |
| GET | `/users/{id}/research/experiments/latest/metrics` | Read stored aggregate or seeded measurements; optional `method`, `scenario`, `metric`, and `scope` filters |
| GET | `/users/{id}/research/actions` | List the owner's available agent IDs and the stable action-catalogue version |
| POST | `/users/{id}/research/manual-action` | Run selected agents on the owner's saved profile without persistence; JSON `{ "selected_agents": ["budget", "emergency"] }` |
| GET | `/users/{id}/advisory-sessions/latest` | Load the latest run and its stale status |
| GET | `/users/{id}/advisory-sessions?limit=10&before_id=<id>` | List newest session summaries with a cursor for older pages |
| GET | `/users/{id}/advisory-sessions/{session_id}` | Load one owned historical run and its stale status |

FastAPI also provides interactive API documentation at <http://localhost:8000/docs>.

## Verification

For the paired synthetic monthly experiment (Random, Rule-Based, trained DQN), see [the experiment runner and raw output instructions](./paired-monthly-experiment.md). It uses the committed held-out cohort and runs offline; no new website screen is added by this experiment.

For the paired cohort's measured risk coverage, agent calls, reward, timing, and explicitly unavailable goal and recommendation metrics, see [research metrics](./research-metrics.md).

To inspect one held-out user-month across Random, Rule-Based, and trained RL with recorded agent outputs, recommendations, and constraints, see [monthly case analysis](./monthly-case-analysis.md).

For validated six-section reasoning over one synthetic monthly case, with an optional provider request and deterministic fallback, see [monthly LLM reasoning](./monthly-llm-reasoning.md).

For each recommendation's recorded what, why, evidence, agents, orchestration basis, and limitations in Advisor and the offline monthly case, see [recommendation explainability](./recommendation-explainability.md).

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
