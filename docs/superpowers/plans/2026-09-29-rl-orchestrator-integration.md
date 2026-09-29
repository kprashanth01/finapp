# RL Orchestrator Integration Implementation Plan

> **For agentic workers:** Implement this plan task by task with test-first changes. This issue uses native execution in the current worktree.

**Goal:** Let an account owner run rule, seeded random, or trained DQN agent selection on the same saved profile and inspect a useful, honest result in Advisor.

**Architecture:** A common selection service maps a mode to a policy, executes the chosen action through the existing Gymnasium environment, and returns agent findings plus the proxy reward. The committed DQN artifact is verified and cached per process. A complete monthly plan is assembled only when the chosen agents supply all required facts. Experimental runs are read-only; existing saved rule-based sessions and history stay compatible.

**Tech Stack:** FastAPI, Pydantic, Gymnasium, Stable-Baselines3 DQN, React, Vite.

**Spec:** GitHub issue #23 and the eight-milestone master prompt.

## Global Constraints

- Owner-scoped saved-profile input only; no synthetic records in the user database.
- Mode values are `rule_based`, `random`, and `rl`; random seed is explicit and repeatable.
- A proxy reward does not measure financial outcomes; an incomplete agent set cannot generate a complete monthly plan.
- Existing persisted rule-based sessions remain readable and unchanged.

## Review Focus

- Missing or incompatible DQN artifact returns a useful unavailable response rather than silently selecting a different policy.
- Cross-account requests cannot run another user's data.
- Repeated RL requests reuse the loaded model.
- A partial selection exposes missing plan dependencies without fabricating allocations.
- A profile edit between runs produces a fresh result from current saved values.

## Tasks

### Task 1: Common policy selection and execution

**Files:** `backend/app/rl/orchestration.py`, `backend/app/rl/dqn_artifact.py`, `backend/tests/test_orchestration.py`

- [x] Write tests for all three modes, stable random seed, cached DQN prediction, partial and full plan readiness, and unavailable model.
- [x] Run the focused tests and confirm expected failures.
- [x] Implement mode factory and execution using the existing catalogue, environment, registry, and reward audit.
- [x] Run focused tests until green.

### Task 2: Authenticated API contract

**Files:** `backend/app/rl/api.py`, `backend/tests/test_advisory_api.py`

- [x] Write API tests for owner-only access, invalid mode/seed, no persistence, full and partial responses, and RL unavailable response.
- [x] Confirm red, implement the route, and confirm green.

### Task 3: Advisor UI

**Files:** `frontend/src/components/OrchestrationLab.jsx`, `frontend/src/Workspace.jsx`, `frontend/src/services/api.js`, `frontend/src/index.css`, `frontend/tests/orchestrationLab.test.js`

- [x] Write render tests for mode choice, action, findings, reward, missing checks, and limitations; confirm red.
- [x] Implement the UI in Advisor using the new endpoint, show complete plan only when returned, and keep saved history separate.
- [x] Run focused frontend tests and build.

### Task 4: Documentation and verification

**Files:** `README.md`, `frontend/src/components/Research.jsx`

- [x] Update stale DQN copy and add a precise website walkthrough and optional RL runtime setup.
- [x] Run complete backend and frontend tests, build, and inspect the local UI against a test account.
- [x] Review diff, commit, push, and open the issue-linked PR.
