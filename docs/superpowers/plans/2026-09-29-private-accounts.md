# Private Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Issue #13 gives each FinApp account private, persistent access to its saved profile, goals, and advisory history while preserving legacy records through a one-time claim.

**Architecture:** Add Argon2id credentials and opaque database-backed cookie sessions to FastAPI. Enforce a session-owner dependency on every user-scoped route. Replace browser user-ID persistence with an auth boundary that mounts the existing workspace only for the authenticated account.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, pwdlib Argon2, React/Vite/Axios, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-29-private-accounts-design.md`

## Global Constraints

- Preserve all existing user/profile/goal/session rows and API financial response shapes.
- New signup asks for name, email, password; financial details follow in Profile.
- Login and claim errors do not reveal whether an email exists.
- Session tokens never enter localStorage or URLs. Legacy records require a one-time local claim code.
- No seeded demo account, email delivery, password reset, MFA, or public deployment in this issue.

## Review Focus

1. A request with a valid cookie but someone else's user ID must return 404 for reads and writes, including nested sessions and goals.
2. A revoked or expired cookie must fail after a page reload and must not reveal the previous workspace.
3. A code generated twice must invalidate the first; a claimed record cannot be claimed again.
4. A case variant of an existing or legacy email cannot create another account.
5. A slow response for account A after logout/sign-in to B must not populate B's UI.

---

### Task 1: Persistent credentials, sessions, and legacy claim primitive

**Files:** `backend/app/models.py`, `backend/alembic/versions/0006_private_accounts.py`, `backend/app/auth_core.py`, `backend/app/legacy_claim.py`, `backend/requirements.txt`, `backend/tests/test_auth_core.py`.

**Interfaces:** Produce `hash_password`, `verify_password`, `new_session`, `resolve_session`, `revoke_session`, `issue_legacy_claim`, and `consume_legacy_claim` for Task 2. Use nullable `User.password_hash` and account/claim session tables.

- [ ] Write tests for Argon2 hashing and verification; random opaque tokens stored only as SHA-256 digests; expiry/revocation; legacy claim rotation, expiry, and one-use preservation of user ID.
- [ ] Run targeted tests RED. Implement models, additive migration, dependency, and claim CLI. Run targeted tests GREEN.
- [ ] Run backend suite and inspect migration upgrade SQL or apply to a disposable database. Commit.

### Task 2: Authentication routes and browser request protection

**Files:** `backend/app/auth_api.py`, `backend/app/auth_dependencies.py`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/tests/test_auth_api.py`.

**Interfaces:** Produce `require_current_user(request, session) -> User`, `require_owner(user_id, current_user) -> User`, signup/login/me/logout/claim endpoints. Task 3 consumes `require_owner`; Task 4 consumes auth routes and cookie behavior.

- [ ] Write failing API tests for signup returning a cookie without password hash, sign-in and reload, wrong credentials, generic legacy rejection, logout, expiry, rate limit, Origin/header checks, and email case collision.
- [ ] Implement routes, exact-origin credentialed CORS, fixed custom mutation header, no-store responses, loopback HTTP cookie exception, and database-backed failed-login window. Run targeted tests GREEN.
- [ ] Run backend suite and commit.

### Task 3: Close every user-scoped API path

**Files:** `backend/app/api.py`, `backend/app/goal_api.py`, `backend/tests/test_profiles.py`, `backend/tests/test_goals.py`, `backend/tests/test_advisory_api.py`, `backend/tests/test_private_data.py`.

**Interfaces:** Consume `require_owner`. Existing routes retain shapes but reject missing session or different user ID before any row lookup/mutation.

- [ ] Write failing tests for anonymous access, cross-account profile/analysis/goal/advisory history reads and writes, nested session IDs, and preserved correct-owner behavior.
- [ ] Apply owner dependency to all routes and update old tests to create authenticated accounts. Run targeted tests GREEN.
- [ ] Run full backend suite, verify no unprotected `/users/{user_id}` route in route inventory, commit.

### Task 4: Signed-in frontend workflow

**Files:** `frontend/src/App.jsx`, `frontend/src/components/AuthScreen.jsx`, `frontend/src/services/api.js`, `frontend/src/hooks/useGoals.js` if needed, `frontend/tests/authFlow.test.js`.

**Interfaces:** Consume `/auth/me`, `/auth/login`, `/auth/logout`, `/auth/claim`, `POST /users` signup. Workspace receives authenticated `User` and remounts when identity changes.

- [ ] Write failing tests for API credentials/header setup, auth boot resolution, logout and account-switch state isolation, signup/claim form validation and errors.
- [ ] Implement auth wrapper and forms; remove `finapp.userId` as authority and remove passwordless user creation. Add explicit signed-in identity and Sign out, profile setup cue, expired-session handling. Run targeted tests GREEN.
- [ ] Run all frontend tests and production build; commit.

### Task 5: Local integration, data preservation, and handoff

**Files:** `README.md`, `.env.example` if needed, `frontend/.env.example` if needed, supplementary tests for defects found.

**Interfaces:** No new product API. Finish end-to-end contract and documentation.

- [ ] Run migration on local PostgreSQL and verify legacy user/profile/session counts unchanged. Exercise account signup, profile save, goal save, run/history, logout, login, and owner isolation with disposable data; remove only the disposable data afterward.
- [ ] Verify browser desktop and narrow viewport with native browser. Keep the existing issue #11 preview intact; use separate preview ports for issue #13.
- [ ] Document one-time claim command, local cookie behavior, login flow, and production limits. Run backend/frontend full suites, build, and `git diff --check`. Commit.
- [ ] Request one final independent review, fix Important findings with tests, create a PR that closes #13 and builds on #12, and leave merge to the user.
