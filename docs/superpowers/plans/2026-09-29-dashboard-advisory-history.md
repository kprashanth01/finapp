# Dashboard and Advisory History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show current saved financial data in a dashboard and let the user reopen prior advisory sessions.

**Architecture:** Keep the existing one-user local-storage flow. Add paged read-only session endpoints over the immutable `analysis_sessions` rows. Add client-side Dashboard/Profile/Advisor views; Advisor uses the same result renderer for latest and selected historical runs.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL, React, Axios, Vite, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-29-dashboard-advisory-history-design.md`

## Global Constraints

- All dashboard and history values come from saved PostgreSQL records; no seeded profiles or generated financial data.
- No new financial formulas or rules, auth claim, database migration, package, or external service.
- History displays only the six financial inputs captured in `result.state`; it does not reconstruct older savings balance, risk tolerance, goal, or horizon.
- The session key is labeled **session ID**, never a user's run count.
- Existing latest endpoint and immutable session results remain intact.
- Browser verification uses temporary QA records and removes them afterward.

## Review Focus

1. A user with no profile sees a dashboard action to create one, not broken metric cards (Task 2 manual check).
2. No saved runs yields `items: []`, `next_before_id: null`, and a clear history empty state (Tasks 1 and 3).
3. Pagination at the final boundary returns no duplicate or phantom next page (Task 1 API test).
4. A session from another user or a missing user cannot be read via detail/list (Task 1 API test).
5. A history request failure leaves the current advisory result visible and offers retry (Task 3 browser check).

## File Map

- `backend/app/advisory/types.py`: summary and page response models.
- `backend/app/api.py`: paged list and owned detail reads, reusing existing fingerprint/session parsing.
- `backend/tests/test_advisory_api.py`: focused list/detail contract tests using its existing fixture.
- `frontend/src/components/Dashboard.jsx`: current saved overview and navigation actions.
- `frontend/src/components/AdvisoryHistory.jsx`: paged list, selection, empty/error/retry states.
- `frontend/src/components/AdvisorySession.jsx`: render selected historical session with accurate session-ID label.
- `frontend/src/App.jsx`: client-side views, save/run refresh, historical selection.
- `frontend/src/services/api.js`: list/detail calls.
- `README.md`: current workflow, history behavior, API documentation.

### Task 0: Track the feature and confirm the baseline

**Files:** No product files.

- [ ] Create one GitHub issue describing this cohesive feature, the expected visible result, existing PostgreSQL dependency, and verification. Use the existing `feature/dashboard-advisory-history` branch for product work.
- [ ] Confirm the branch starts from merged `main`. Run the existing backend tests; install only already declared dependencies needed to run them. If the baseline fails, identify the cause before changing code.

### Task 1: Read-only advisory history API

**Files:** Modify `backend/app/advisory/types.py`, `backend/app/api.py`, `backend/tests/test_advisory_api.py`.

**Interfaces:** Produce `AdvisorySessionSummary` (`id`, `user_id`, `created_at`, `method`, `rule_version`, `is_stale`, `priority_titles: list[str]`, `priority_count: int`), `AdvisoryHistoryPage` (`items`, `next_before_id: int | None`), `GET /users/{user_id}/advisory-sessions?limit=10&before_id=`, and `GET /users/{user_id}/advisory-sessions/{session_id}` returning `AdvisorySessionRead`.

- [ ] **Step 1: Write failing API tests.** Add `test_history_empty_and_missing_user`, `test_history_orders_pages_and_reports_stale_summaries`, and `test_history_detail_is_owned_and_immutable`. Assert `items=[]/next_before_id=null` for users with no runs, including one with no profile; 404 for missing user and cross-user detail; descending IDs for three runs with `limit=2`, second page containing the third only, then no cursor; `limit=0` and `limit=51` return 422; summary priority count/title and stale status reflect saved-input edits; detail result equals its original POST result after a later edit.
- [ ] **Step 2: Run tests and observe endpoint-not-found failures.** From `backend/`, run `..\.venv\Scripts\python -m pytest -q tests/test_advisory_api.py` using the repository's configured Python if present.
- [ ] **Step 3: Implement models and routes.** Validate `limit` with FastAPI `Query(ge=1, le=50)` and positive `before_id`; check user existence, returning an empty page when there is no profile. Filter `AnalysisSession.user_id`, apply `id < before_id`, order by descending ID, fetch `limit + 1` to establish the cursor. Calculate `is_stale` with the existing current fingerprint, parse stored JSON through `AdvisoryResult`, and extract priority titles. Detail filters by both user ID and session ID, then uses `_session_read`; register it after `/latest`.
- [ ] **Step 4: Run the API tests, then the full backend suite.** Both must pass; inspect the response shape for exact field names.
- [ ] **Step 5: Commit.** `feat: expose advisory session history`.

### Task 2: Saved-data dashboard and view navigation

**Files:** Create `frontend/src/components/Dashboard.jsx`; modify `frontend/src/App.jsx`.

**Interfaces:** `Dashboard({ user, profile, analysis, advisorySession, onOpenProfile, onOpenAdvisor })`. `App` owns `activeView: 'dashboard' | 'profile' | 'advisor'`; it passes the already loaded saved objects, not form draft values.

- [ ] **Step 1: Record the current UI baseline.** Open the running app against the existing saved user and confirm there is one long form and no dashboard navigation; capture the visible values for comparison. Use the actual saved profile; do not seed data.
- [ ] **Step 2: Implement `Dashboard` and view controls.** Display saved income, expenses, savings balance, outstanding debt, emergency fund, risk tolerance, optional goal, existing snapshot metrics with unavailable states, and latest-run date/staleness/priority titles. Add obvious actions to create/edit a profile and open Advisor. Use simple buttons for three views; do not add a router or recalculate ratios in React.
- [ ] **Step 3: Verify in browser.** Current values match the saved API data; a user without a profile sees a profile action; no latest run shows a run-analysis action; Profile still edits both forms; dashboard updates after a save. Check narrow layout and console errors.
- [ ] **Step 4: Run `npm test` and `npm run build` from `frontend/`; commit.** `feat: add saved financial dashboard`.

### Task 3: Historical run browsing and refresh behavior

**Files:** Create `frontend/src/components/AdvisoryHistory.jsx`; modify `frontend/src/components/AdvisorySession.jsx`, `frontend/src/App.jsx`, `frontend/src/services/api.js`, `README.md`.

**Interfaces:** `getAdvisorySessionHistory(userId, { limit, beforeId }) -> { items, next_before_id }`; `getAdvisorySession(userId, sessionId) -> AdvisorySessionRead`. `AdvisoryHistory({ userId, refreshKey, selectedId, onSelect })` requests pages of ten and emits selected IDs; `App` fetches detail, retains the current result until success, and resets selection to latest after a save or run. `AdvisorySession` renders whichever immutable result is selected plus the six recorded financial inputs.

- [ ] **Step 1: Record the current Advisor baseline.** Confirm only the latest run is visible and the label says `Saved run #<database id>`.
- [ ] **Step 2: Add API calls and history list.** Implement descending list, Load more via `next_before_id`, date/method/stale/priority summary, empty state, retry on failure, and selection. Avoid duplicate rows when refresh or pagination follows a new run.
- [ ] **Step 3: Wire selected detail and refresh.** A failed detail request must keep the prior result visible with an error. A successful selection shows stored findings and the six captured inputs; label the key `Session ID`. After a save or run, return to latest, refresh summaries, and preserve correct stale status. Do not show unsaved edits as historical data.
- [ ] **Step 4: Browser walkthrough against PostgreSQL.** Open a previous run, compare its stored inputs and findings to its original result, edit and save a financial input, confirm old summary becomes stale, rerun, see newest first, load more, reload page, and confirm missing/failed history is recoverable. Remove any temporary QA records created for this check.
- [ ] **Step 5: Update README and verify.** Document the views, list/detail endpoints, session-ID meaning, captured-input limitation, and run/reload flow. Run full backend suite, frontend tests/build, `git diff --check`, and ensure no secret or generated data was added. Commit `feat: browse saved advisory sessions`.

### Task 4: PR and review handoff

**Files:** No product files.

- [ ] Push `feature/dashboard-advisory-history`, open a PR into `main` linked to the issue, attach it to the Codex task, and summarize changed files, checks, and a short user walkthrough. Leave the PR unmerged for user review.
