# Goal-Based Six-Agent Advisory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user selected native execution; preserve that choice. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user manage measurable goals and receive an understandable six-agent advisory plan that assigns one monthly savings budget without counting it twice.

**Architecture:** Keep the existing profile, calculations, and session storage. Add goal persistence, a versioned planning state, independent Goal/Risk/Investment agents, and an evidence-based recommendation coordinator. Present the coordinated result before expandable agent diagnostics, with explicit support for earlier sessions.

**Tech Stack:** Existing React/Vite/Tailwind/Axios, FastAPI/Pydantic/SQLAlchemy, PostgreSQL/Alembic, pytest and Node test runner. No additional package or service.

**Spec:** `docs/superpowers/specs/2026-09-29-goal-based-advisory-design.md` (approved).

**Issue:** https://github.com/kprashanth01/finapp/issues/11

## Global Constraints

- Use Decimal for amounts and ratios.
- The monthly planning budget is the recorded `monthly_savings_contribution`. Null means unknown; zero is a known zero.
- Approximate months = ceiling(days until target date / 30), at least one for a future date.
- Required monthly amount = remaining amount / approximate months, rounded upward to cents.
- Allocations and unassigned capacity must be nonnegative and sum exactly to the known contribution.
- Keep rule constants together and bump the rule version. Preserve the existing illustrative expense threshold of 80%, debt-payment threshold of 20%, and reserve target of three months.
- Investment horizon caps: less than three years conservative; three to under seven at most moderate; seven or more any stated preference. Categories are illustrative, not suitability claims.
- Read existing v1 sessions without modifying their stored JSON or filling missing historical fields from current profile data.
- Do not lead the screen with database IDs, rule versions, six equal agent cards, or repeated disclaimers.
- Goal and profile saves do not silently run an analysis. Proposed allocations never update balances.
- No demo seeds. Preserve the user's browser profile pointer during QA and remove only test-created records.
- Work on `feature/goal-based-advisory` in the existing clean worktree. Main and its running servers remain usable until the feature preview is deliberately started.
- The shared Python interpreter is `C:/Users/kpras/OneDrive/Documents/fin-app/.venv/Scripts/python.exe`. Commands below abbreviated as `python` must use that executable explicitly in PowerShell; execute backend commands from `backend/` and npm commands from `frontend/`.

## Review Focus

1. Two rapid goal operations or navigation during a pending analysis: the UI must not associate results with the wrong inputs (Task 4 browser checks).
2. A run crossing UTC midnight: one captured planning date must be used throughout the run; later reads report date staleness distinctly (Tasks 2–3 tests).
3. A legacy note longer than the new goal name limit: prefill must preserve the note and give editable validation rather than truncate or create a goal silently (Task 4 browser checks).
4. Several individually valid maximum-size goal amounts: aggregate demands must not overflow a field limited to one currency input (Tasks 2–3 tests).
5. An archived goal is edited/restored after a run: only active goal changes affect planning inputs, while saved history stays unchanged (Tasks 1 and 3 tests).

## Files and contracts

Persistence: extend `backend/app/models.py`; create `backend/app/goal_schemas.py`, `backend/app/goal_api.py`, and `backend/alembic/versions/0005_financial_goals.py`. Register the router and PATCH CORS support in `backend/app/main.py`.

Planning: retain `advisory/state.py` and `types.py` for v1 read contracts. State.py owns both state versions and GoalSnapshot; `planning_types.py` imports shared legacy types and state, while new `session_types.py` owns the session/history envelopes importing both result versions. Types.py must not import those modules back. Create `advisory/goal_agent.py`, `risk_agent.py`, and `investment_agent.py`; extend existing `agents.py`, `registry.py`, `rules.py`, `orchestrator.py`, `service.py`, `recommendations.py`, and `api.py` at integration. Update session-envelope import sites when moving them out of types.py.

UI: extend `services/api.js`, `services/advisoryFreshness.js`, `App.jsx`, `Dashboard.jsx`, `AdvisorySession.jsx`, `AdvisoryHistory.jsx`, `FinancialProfileForm.jsx`, and `UserForm.jsx`. Create `components/Goals.jsx`, `components/GoalForm.jsx`, `components/AdvisoryPlan.jsx`, `hooks/useGoals.js`, and `utils/format.js`. Each new component has one visible responsibility; avoid splitting every card into another file.

Tests: `backend/tests/test_goals.py`, `test_planning_agents.py`, `test_recommendations.py`, existing `test_advisory.py` and `test_advisory_api.py`, plus a single fixed `backend/tests/fixtures/advisory_v1.json`. Existing frontend tests remain and are extended only for meaningful save/run coordination changes.

### Shared data contract

- `GoalWrite`: name, target_amount, saved_amount, target_date, priority (`high|medium|low`). `GoalRead` adds id, user_id, archived, created_at, updated_at. `GoalArchiveWrite` contains only archived.
- `GoalSnapshot`: frozen id, name, target_amount, saved_amount, target_date, priority. Archived goals never enter planning state.
- `PlanningState`: frozen `schema_version='financial-state-v2'`, existing v1 amounts/ratios, savings, risk_tolerance, investment_horizon_years, legacy financial_goal note, `goals: tuple[GoalSnapshot, ...]`, `as_of_date: date`, input_fingerprint. Use a separate v2 builder; retain the legacy state model for reading v1 data.
- `GoalRequirement`: goal snapshot plus remaining_amount, approximate_months (nullable), required_monthly (nullable), status (`future|completed|overdue`). Aggregate money fields have unrestricted Decimal precision; only individual input fields use the currency size limit.
- `PlanningAgentResult`: extends existing AgentResult with `facts`, a discriminated union using `kind`: budget (capacity), debt (review_required and reason_code), emergency (gap and coverage), goal (requirements), risk (category and factor codes), investment (prerequisite status, category, factor codes). Store human explanations and numeric evidence in findings; the coordinator reads facts, never prose.
- `EvidenceRef`: agent_id and finding_code. `PlanAction`: code, title, reason, source_refs, limitations, next_action (view plus optional field/goal_id).
- `GoalAllocation`: requirement, allocated_monthly and funding_gap (nullable), status (`completed|overdue|budget_covered|underfunded|missing_budget`), source_refs.
- `MonthlyPlan`: capacity, emergency_allocation, goal_allocations, unassigned, hold_reason. Unknown budget-dependent amounts are null.
- `InvestmentAssessment`: status (`ready_to_consider|deferred|insufficient_information`), category (nullable), reasons, source_refs. Known blocking conditions take precedence and produce deferred; otherwise missing required information produces insufficient_information; otherwise ready_to_consider. Null horizon is missing, zero horizon is a known blocker. Explain missing inputs alongside known blockers. Category is only shown when ready_to_consider.
- `CoordinatedAdvice`: summary (title, text, next_action), monthly_plan, investment, priority_actions. `AdvisoryResultV2` contains state, decision, planning agent_results, advice. Do not duplicate the advice at another JSON path.
- `AdvisorySessionRead.result` accepts the existing AdvisoryResult (v1) or AdvisoryResultV2, distinguished by state.schema_version. Add `stale_reasons: list['inputs'|'planning_date'|'rule_version']` to session reads and history summaries. Existing `is_stale` remains its boolean equivalent. `get_priority_actions(result)` supplies history titles for either result version.

---

### Task 1: Persist and manage goals

**Files:** persistence files above; `backend/tests/test_goals.py`.

**Interfaces:** Produce `GET /users/{user_id}/goals?include_archived=false -> list[GoalRead]`, `POST` on that collection -> GoalRead (201), `PUT /users/{user_id}/goals/{goal_id}` with GoalWrite -> GoalRead, and `PATCH` on that resource with GoalArchiveWrite -> GoalRead. Produce `load_active_goals(session: Session, user_id: int) -> list[FinancialGoal]` in `goal_api.py` for advisory endpoint callers; query by user, archived=false, stable ID order. The pure advisory service receives these rows as arguments and never imports an API router.

- [ ] Write `test_goal_lifecycle_and_owner_scope` and `test_goal_validation` using an isolated SQLite TestClient fixture matching existing API tests. Assert:
  ```python
  assert created.status_code == 201
  assert created.json()['name'] == 'Course fees'
  assert other_user_edit.status_code == 404
  assert archived_list == []
  assert restored.json()['archived'] is False
  assert invalid_zero_target.status_code == 422
  assert invalid_priority.status_code == 422
  assert overfunded_goal.status_code == 201
  ```
  Also pin blank/101-character names, negative or overprecision amounts, invalid date, overdue date accepted, repeated archive idempotence, missing-user 404, and editing an archived goal without implicitly restoring it.
- [ ] Run `python -m pytest tests/test_goals.py -q`; expect failures because goal routes/models are absent.
- [ ] Implement FinancialGoal with user cascade, numeric/date/priority constraints and user/archive index; matching Alembic revision follows `0004_analysis_sessions`. Enforce the approved validation in schemas and user scoping in all routes. Register PATCH with CORS. Updates use UTC timestamps and return the persisted record; validation failures perform no write.
- [ ] Run the goal tests and existing API regression tests. Check migration SQL and apply `python -m alembic upgrade head` to configured local PostgreSQL after verifying the current revision; confirm new table/constraints and preservation of existing user/session records. Do not downgrade the user's database for a test.
- [ ] Commit `feat: persist financial goals with edit and archive flows`.

### Task 2: Reproducible planning state and independent agents

**Files:** `planning_types.py`, `state.py`, `rules.py`, three new agent modules, `backend/tests/test_planning_agents.py`, v1 fixture.

**Interfaces:** Produce `build_planning_state(user: User, profile: FinancialProfile, analysis: AnalysisRead, goals: Sequence[FinancialGoal], as_of_date: date) -> PlanningState` in state.py; `GoalPlanningAgent.analyze(state: PlanningState)`, `RiskAssessmentAgent.analyze(state: PlanningState)`, and `InvestmentAgent.analyze(state: PlanningState) -> PlanningAgentResult`. Agent IDs are `goal`, `risk`, and `investment`.

- [ ] Before changing active output, capture one synthetic v1 result from the committed baseline into `fixtures/advisory_v1.json`. Include no real user data. This remains a fixed historical fixture, never regenerated from v2 code.
- [ ] Write pure tests with one local state factory and fixed date `2026-09-29`. Pin exact results:
  ```python
  assert requirement(remaining='6000', days=360).required_monthly == Decimal('500.00')
  assert requirement(remaining='1', days=90).required_monthly == Decimal('0.34')
  assert requirement(remaining='6000', days=0).status == 'overdue'
  assert requirement(remaining='0', days=-1).status == 'completed'
  assert requirement(remaining='6000', days=31).approximate_months == 2
  assert category(preference='aggressive', horizon=2) == 'conservative'
  assert category(preference='aggressive', horizon=3) == 'moderate'
  assert category(preference='aggressive', horizon=7) == 'aggressive'
  ```
  Cover days 1/30/31, overfunding, unknown/zero contribution, horizon null/zero, missing debt payment, multiple maximum-size goals, and no mutation of state/goals. Assert equivalent goal order yields the same fingerprint; changed active goal inputs change it. Store the analysis date but compare it separately from the input fingerprint.
- [ ] Run `python -m pytest tests/test_planning_agents.py -q`; expect missing new contracts/agents.
- [ ] Implement the shared data contract, canonical Decimal/date serialization, goal requirements and all three agents. Use `ROUND_CEILING` for positive required monthly amounts. Define horizon caps and the 30-day month convention in rules.py. Risk factors are explicit reserve/debt/contribution/horizon constraints; no fabricated numeric confidence.
- [ ] Run the new tests and existing deterministic tests; the active registry/orchestrator remains v1 until Task 3 integrates the complete pipeline.
- [ ] Commit `feat: add goal risk and investment planning agents`.

### Task 3: Coordinate six agents and persist the resulting plan

**Files:** existing advisory integration files, api.py, types.py, new session_types.py, `test_recommendations.py`, `test_advisory.py`, `test_advisory_api.py`.

**Interfaces:** Produce `RecommendationEngine.build(state: PlanningState, decision: OrchestratorDecision, results: list[PlanningAgentResult]) -> CoordinatedAdvice`; `Orchestrator` protocol with `run(state: PlanningState, registry: AgentRegistry) -> AdvisoryResultV2`; `RuleBasedOrchestrator` implements it. Service signatures become `financial_state(user, profile, goals, as_of_date) -> PlanningState` and `run_advisory(user, profile, goals, as_of_date) -> AdvisoryResultV2`. `planning_date() -> date` uses UTC and is injected once per API request. `_session_read(row, current_state) -> AdvisorySessionRead` calculates freshness without rewriting history.

- [ ] Write allocation tests around the public engine and real agent outputs:
  ```python
  assert reserve_first.monthly_plan.emergency_allocation == Decimal('500.00')
  assert reserve_first.monthly_plan.goal_allocations[0].allocated_monthly == Decimal('0.00')
  assert reserve_first.monthly_plan.goal_allocations[0].funding_gap == Decimal('500.00')
  assert competing_goals.monthly_plan.goal_allocations[0].allocated_monthly == Decimal('400.00')
  assert competing_goals.monthly_plan.goal_allocations[1].allocated_monthly == Decimal('100.00')
  assert debt_hold.monthly_plan.unassigned == Decimal('500.00')
  assert unknown_budget.monthly_plan.unassigned is None
  assert zero_budget.monthly_plan.unassigned == Decimal('0.00')
  assert sum_allocations(plan) + plan.unassigned == plan.capacity
  ```
  Fixture conditions: capacity 500; reserve-first gap 5,000 and goal demand 500; competing goals have no reserve/debt blocker and demands 400 each with different priorities; debt-hold reserve met and DTI 20%. Include insufficient expenses, goal ordering ties, all completed/archived goals, unknown debt burden, large aggregate demands, exact cents, and an investment prerequisite pass deferred by an underfunded/overdue goal. Every source_ref must resolve to a finding from a selected agent.
- [ ] Run `python -m pytest tests/test_recommendations.py -q`; expect missing engine/v2 integration.
- [ ] Implement the exact reserve → debt review → ordered goals → unassigned policy from the spec. Extend existing Budget/Debt/Emergency results with typed facts while retaining their original formulas/evidence. Add all six to the default registry, record selected/skipped reasons, and use `rule-based-v2`. Order recommendations using configured priorities and stable unique action codes; attach missing-input links to their relevant blockers.
- [ ] Update advisory endpoints to load active goals and capture the date once. Store the complete v2 result. Use an explicit union for legacy/current reads and `get_priority_actions(result)` for summaries. A v1 result has `rule_version` staleness and retains its original data; v2 distinguishes changed input hash, date, and rule version. Do not label a date-only change as an input edit.
- [ ] Add API tests: run a v2 session, mutate/edit/archive/restore goals, compare old payload unchanged, edit archived goal without changing current fingerprint, advance the injected date by a day, and read the fixed v1 fixture through latest/history/detail. Assert date-only reasons `['planning_date']`; assert legacy has no invented advice or goals. Update existing tests for the new result path/selected agent set while preserving their original financial boundary assertions.
- [ ] Run `python -m pytest -q`; all applicable API and financial tests must pass. Start the API and verify one persisted v2 result in PostgreSQL using only task-created data.
- [ ] Commit `feat: coordinate six agents into a saved monthly advisory plan`.

### Task 4: Deliver the goal-to-insight user flow

**Files:** frontend files listed above; README usage notes. No new UI framework or chart dependency.

**Interfaces:** api.js exports `getGoals(userId, {includeArchived=false}={})`, `createGoal(userId, values)`, `updateGoal(userId, goalId, values)`, `setGoalArchived(userId, goalId, archived)`. `useGoals(userId)` returns goals/loading/error/pending/reload/create/update/setArchived and guards obsolete responses. `Goals({goals, loading, error, pending, disabled, onCreate, onUpdate, onArchive, onRetry, legacyNote, onClearLegacyNote, onRunAnalysis})`; `GoalForm({goal, initialName, pending, onSave, onCancel})`; `AdvisoryPlan({result, onOpenProfile, onOpenGoal})` consumes only v2 result.advice/state. `formatAmount(value)` is display-only; null is not zero.

- [ ] Before editing, inspect the existing running flow and record the selected browser user without changing it. Use a separate disposable browser storage context/origin for QA. If the tooling cannot isolate storage, explicitly capture and restore the original pointer through supported browser controls; do not leave a task user's pointer behind or inject it into committed app code.
- [ ] Implement goal API functions and hook, preserving server validation details by field. Add Goals navigation, labeled short forms, saved/remaining amounts, edit, archive/undo/restore, useful empty/error/retry states, and the collapsed legacy note. Show a complete-profile link if analysis cannot run yet. Keep archived edits separate from active planning. Entered values survive failed saves; overlength legacy prefill remains editable with validation.
- [ ] Implement the specified Advisor reading order. Monthly plan rows show planned allocations, not payments. Each goal shows requirement/allocation/gap with explicit status text. Use factual summary and contextual edit links; evidence/formulas and research details are collapsed. A legacy result uses its original renderer plus the earlier-format notice. Current and old runs never mix their goals or inputs.
- [ ] Integrate Dashboard's compact goal summary and leading insight, with real actions to Goals/Advisor. Remove numbered steps after initial setup, preserve the legacy note in profile payloads, and remove the obsolete take-home correction copy. Editing a relevant profile input or goal refreshes session freshness without running an analysis. Keep the last result visible but clearly dated/stale; block overlapping saves/runs and protect against outdated request responses. A successful mutation followed by a failed refresh must still be reported as saved, with a retry for refresh.
- [ ] Manually verify on the feature preview: no sample goals; create two goals; run analysis; understand the leading priority and both funding gaps with diagnostics closed; adjust contribution/date and rerun; reopen earlier run; archive/restore; reload; navigate by keyboard; force one API failure and retry. Verify a pending save/run cannot use the wrong goal/profile, long legacy note handling, overdue/completed statuses, and null versus zero amounts. Inspect desktop and actual sub-640px layouts; document a tooling block accurately if one remains.
- [ ] Run `npm test` and `npm run build`; add a focused coordination regression test only if needed for new pure request/save guards. Check browser runtime errors during the tested flow. Keep QA minimal and restore the user's remembered profile before removing task data.
- [ ] Commit `feat: present goals and coordinated advisory insights`.

### Task 5: Verify, document, and open the reviewable PR

**Files:** README.md and any fixes justified by final verification; no unrelated refactors.

**Interfaces:** Produces a clean pushed feature branch and draft PR linked with `Closes #11`, ready for the native execution skill's final branch review. Main is not merged automatically.

- [ ] Update README with goal entry and the 30-day convention, actual versus proposed amounts, current six-agent flow, priority rules, migration command, old-run compatibility, and next authentication milestone. Document incomplete capabilities honestly.
- [ ] Run `python -m pytest -q`, `npm test`, `npm run build`, and `git diff --check` on the final tree. Confirm Alembic is at `0005_financial_goals` and at least one complete PostgreSQL-backed goal → analysis → history flow succeeded.
- [ ] Remove only QA-created records after checking their exact identities, restore the user's browser pointer, and leave a working preview of the reviewed branch with the existing user. Report the preview branch and URL clearly. Preserve the worktree for PR feedback.
- [ ] Commit any verified finishing fixes, push `feature/goal-based-advisory` with its own upstream, create the draft PR, and attach it in Codex. The PR description leads with the concrete new workflow, one example, the actual verification, and material limitations.

## Final review and handoff

After the tasks, native execution requires one fresh whole-branch review under executing-plans. Review arithmetic, budget conservation, source evidence, old payload reads, save/run races, and insight clarity. Resolve required findings with proportionate verification and push the fixes; record scope rulings. Mark the PR ready when required findings are resolved and checks pass, then stop for the user's review and merge. This is the skill's single final review, not an additional reviewer loop inside Task 5.
