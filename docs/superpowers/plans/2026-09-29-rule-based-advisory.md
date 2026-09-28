# First Advisory Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn one saved financial profile into an explainable, persisted, rule-based advisory session visible in the app.

**Architecture:** Build a typed state from saved values and existing deterministic metrics. A registry supplies three independent agents; a rule-based orchestrator chooses and orders their findings; a service persists each immutable result and reports whether it is stale. React runs and reloads the latest session.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, React, Vite.

**Spec:** `docs/superpowers/specs/2026-09-29-rule-based-advisory-design.md`

## Global Constraints

- Use existing dependencies only; no LLM, RL, external API, or generated production demo profiles.
- Do not add take-home income. Do not describe gross income minus expenses as spendable money.
- All thresholds are illustrative and centralized: high expense ratio 80%, high DTI 20%, emergency coverage target 3 months.
- Keep prior sessions immutable and make current saved-input changes visible as staleness.
- No authentication yet; continue to use practice values.

## Review Focus

- Existing profile with missing monthly savings contribution: budget result identifies unavailable savings rate, without inventing zero.
- Debt balance with missing monthly debt payment: debt agent runs but does not present a DTI value.
- Zero income or expenses: ratios with zero denominators are unavailable and analysis still completes.
- Profile edited after a run: latest session remains unchanged and is flagged stale.
- Duplicate clicks and API failure: UI disables run while pending and preserves the last saved result with an error message.

---

### Task 1: Typed state and three agents

**Files:**
- Create: `backend/app/advisory/state.py`, `backend/app/advisory/types.py`, `backend/app/advisory/rules.py`
- Create: `backend/app/advisory/agents.py`, `backend/app/advisory/registry.py`
- Test: `backend/tests/test_advisory.py`

**Interfaces:**
- `FinancialState.from_saved(user: User, profile: FinancialProfile, analysis: AnalysisRead) -> FinancialState`
- `FinancialState.fingerprint() -> str` hashes all saved financial inputs, excluding name and email.
- `Agent.analyze(state: FinancialState) -> AgentResult`; registry maps `budget`, `debt`, `emergency` to agents.
- `AgentResult` includes agent ID, status (`ok` or `limited`), findings, and limitations. Each finding has stable code, priority flag, title, reason, evidence with values/units, and limitations.

- [ ] Write focused tests for the current demo profile values, missing savings/payment, and zero denominators. Assert numeric evidence and no claim of spendable cash.
- [ ] Run `..\.venv\Scripts\python -m pytest -q tests/test_advisory.py` from `backend`; verify the feature is missing.
- [ ] Implement state, rules, interface, registry, and agents. Budget always reports expense ratio and optional savings rate; debt reports DTI only if available; emergency reports coverage and a 3-month gap only with positive expenses.
- [ ] Run the focused tests, then all backend tests.
- [ ] Commit this independently testable slice.

### Task 2: Orchestrator and evidence-backed output

**Files:**
- Create: `backend/app/advisory/orchestrator.py`, `backend/app/advisory/recommendations.py`
- Test: `backend/tests/test_advisory.py`

**Interfaces:**
- `RuleBasedOrchestrator.run(state: FinancialState, registry: AgentRegistry) -> AdvisoryResult`
- `AdvisoryResult` contains `decision`, `agent_results`, and `priority_actions`; every priority action cites one actual finding code and agent ID.

- [ ] Add tests for selected/skipped agents, selection reasons, emergency→debt→budget ordering, no-priority case, and evidence ownership.
- [ ] Run the focused tests; verify expected failures.
- [ ] Implement orchestration and recommendation composition with centralized priority/rule identifiers.
- [ ] Run focused and full backend tests.
- [ ] Commit this slice.

### Task 3: Saved sessions and API

**Files:**
- Modify: `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/api.py`
- Create: `backend/app/advisory/service.py`, `backend/alembic/versions/0004_analysis_sessions.py`
- Test: `backend/tests/test_advisory_api.py`

**Interfaces:**
- `POST /users/{user_id}/advisory-sessions` creates a complete session from saved values.
- `GET /users/{user_id}/advisory-sessions/latest` returns the latest session and `is_stale`, or 404 if none.
- Response includes `id`, `created_at`, `method`, `rule_version`, `is_stale`, and structured `result`.

- [ ] Write API tests for create/reload, missing user/profile, immutable result after editing, latest selection, stale change for income/profile, and no staleness for name/email-only changes.
- [ ] Run focused tests; verify expected failures.
- [ ] Implement one JSON result row per analysis session, transaction boundary, serialization, and current-input fingerprint comparison.
- [ ] Run focused and full backend tests; apply and check migration against local PostgreSQL without modifying existing profile data.
- [ ] Commit this slice.

### Task 4: App results view and documentation

**Files:**
- Modify: `frontend/src/App.jsx`, `frontend/src/services/api.js`, `README.md`
- Create: `frontend/src/components/AdvisorySession.jsx`

**Interfaces:**
- `runAdvisorySession(userId)` and `getLatestAdvisorySession(userId)` call the new API.
- `AdvisorySession` shows run action, timestamp, stale warning, priority actions, selected/skipped agents, evidence, and limitations.

- [ ] Add the API helpers and a user-facing component with pending/error/empty/saved states. Keep prior result visible when rerun fails.
- [ ] Wire initial load, run, and post-edit stale refresh in `App.jsx`.
- [ ] Build with `npm run build`; manually verify save→run→refresh→edit→stale→rerun in the browser against PostgreSQL and check console errors.
- [ ] Document the rules, inputs, workflow, and limitations in `README.md`.
- [ ] Commit this slice.

### Task 5: Final verification and PR

**Files:** Changes from Tasks 1–4.

- [ ] Run full backend suite, frontend build, Alembic check, and inspect `git diff` for accidental secrets or generated records.
- [ ] Push the feature branch, create a PR closing issue #7, and attach the PR to this task.
- [ ] Explain changed files, user walkthrough, tests, and limitations; stop for user review without merging.
