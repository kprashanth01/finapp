# First explainable rule-based advisory session

GitHub issue: https://github.com/kprashanth01/finapp/issues/7

## Purpose

A user with one saved practice profile can run an analysis and see a small, understandable set of educational findings. Each finding states its supporting values, the rule that produced it, and its limitations. The run is saved so refresh does not silently recompute or alter its historical result.

This is the first complete path from persisted profile through independent agents and an orchestrator to a visible result. It establishes the contract that a later RL orchestrator can use without changing the agents.

## User flow

1. Create or open an existing user and save a financial profile as today.
2. See the existing financial snapshot. Click **Run analysis** to create one advisory session.
3. Read a short priority list, followed by the selected agents' findings and the reasons for their selection. Every finding shows concrete supporting numbers or says which input is unavailable.
4. Refresh to load the latest saved session. Editing saved financial inputs marks that session as based on earlier inputs; clicking **Run analysis** creates a new session. Prior sessions remain immutable in PostgreSQL.

The UI continues to remember one user ID in browser storage. Profile switching and authentication are separate work. No sample users or profiles are inserted by this feature.

## Data flow and boundaries

```text
Saved user + profile
        |
        v
FinancialAnalysisService (existing deterministic ratios)
        |
        v
FinancialState (typed, immutable input for one run)
        |
        v
RuleBasedOrchestrator -> AgentRegistry -> selected agents
        |                                  |
        +----------- AgentResult <---------+
                    |
                    v
       Recommendation/Explanation builder
                    |
                    v
          immutable AnalysisSession -> API -> React view
```

The state contains only fields needed by these agents: gross income, expenses, savings contribution if entered, outstanding debt, debt payment if entered, emergency balance, and existing calculated ratios. It excludes name and email. Decimal arithmetic and explicit `null` values preserve precision and missingness. The state and rule set carry version identifiers so a stored session can be interpreted after rules change.

The agent interface accepts `FinancialState` and returns a typed `AgentResult` with a stable agent ID, status, findings, evidence, and limitations. Agents do not access the database, call other agents, or know which orchestrator selected them. A registry maps stable IDs to implementations. A rule-based orchestrator selects agents by IDs, records selection reasons, runs them, and orders findings. Thresholds and priority rules live in one configuration module rather than being repeated across agents and UI.

The recommendation builder uses only returned agent findings and the orchestrator decision. It cannot introduce a new metric or recommendation unsupported by a finding. The output includes what to review, why, supporting metrics and units, contributing agents, selection reason, and limits. It does not claim a validated risk score, prediction, or personalized financial advice.

## Initial deterministic rules

- **Budget agent:** Always runs for a saved profile. Reports expense-to-gross-income and savings-rate observations when their inputs are available. It can flag a high expense ratio using a documented illustrative threshold of 80%. It never calls gross income minus expenses take-home pay, spare cash, or savings capacity.
- **Debt agent:** Runs when outstanding debt or a positive monthly debt payment is present. Reports DTI only when monthly payment and positive gross income are available. A missing payment produces a limited finding, not a zero DTI. An illustrative DTI threshold of 20% can raise a review priority. No debt means the orchestrator records why this agent was skipped.
- **Emergency-fund agent:** Runs for every saved profile. Reports coverage when monthly expenses are positive. Coverage below an illustrative three-month target produces a priority finding and a transparent gap calculated from expenses and fund balance. Zero expenses produce an unavailable coverage finding.

Priority order for findings above their thresholds: emergency coverage, debt burden, then expense ratio. Informational and limited findings remain visible but do not become action items. The UI labels thresholds as educational project rules. The health score remains a separate snapshot metric and does not secretly drive these decisions.

## Persistence and API

Add an `analysis_sessions` table with user ID, creation time, method (`rule_based`), rule version, a canonical input fingerprint, and a structured JSON result. The fingerprint covers saved financial inputs, including optional profile fields, but excludes identity fields such as name and email. The result contains the input state, orchestrator decision, agent results, and evidence-backed findings. A single versioned document per run keeps the first pipeline understandable; later research work can add indexed child tables if queries require them.

- `POST /users/{id}/advisory-sessions` builds and saves a new session from the *current saved* user and profile. It returns the completed session. No unsaved browser form values enter the run.
- `GET /users/{id}/advisory-sessions/latest` returns the newest saved session or 404 when none exists. It compares the session fingerprint to current saved inputs and returns `is_stale` without changing the stored result.

Both endpoints return 404 for a missing user or profile as appropriate. A session is committed only after the full deterministic pipeline succeeds. No external service or LLM call is involved. No raw contact information enters the stored result.

## Frontend

Place an advisory panel after the financial snapshot. Initially it offers **Run analysis**. After a run it shows the run time, whether saved inputs have changed, all priority findings from the three initial agents (at most one per agent), and a concise expandable list of selected and skipped agents with reasons. If no threshold is crossed, say that no priority finding was produced by the current rules. Missing-input messages remain visible in the related agent result. After saving financial inputs, reload the latest-session status to detect staleness; editing never rewrites the prior session. Running again is explicit.

The existing profile and snapshot flow remains intact. The view uses current styling and no chart library is required for one run. A broader trends dashboard should follow when goal progress and multiple runs provide useful comparisons.

## Files and dependencies

Expected backend areas: `app/advisory/` for state, interface, registry, three agents, orchestration, and recommendation composition; `app/models.py`, `app/schemas.py`, `app/api.py`, and one Alembic migration for sessions; focused `backend/tests/` checks. Expected frontend areas: a new advisory component plus `App.jsx` and `services/api.js`. Update `README.md` with the user flow and rule limits.

Use the installed FastAPI, SQLAlchemy, Pydantic, React, and PostgreSQL stack. No new package, Docker service, API key, LLM, RL library, or generated production demo data is required.

## Verification and completion

- Automated: agent behavior for high, low, missing, and zero inputs; orchestrator selection and ordering; evidence ownership; API session persistence and stale detection.
- Database: apply the Alembic migration to the existing local PostgreSQL database, confirm a saved run can be read back, and confirm the user's existing profile stays intact.
- Frontend: production build and a browser walkthrough of saved profile -> run -> result -> refresh -> edit -> stale notice -> rerun. Check for runtime errors.

The feature is complete when one existing saved practice profile produces a session that the user can understand and reload, without needing to inspect database rows or enter a large set of demo records.
