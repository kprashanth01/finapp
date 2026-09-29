# DQN Agent Selection Training Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Train, save, inspect, and reproduce a one-step DQN agent selector without changing the active Advisor policy.

**Architecture:** Stable-Baselines3 DQN trains from sampled transitions in the existing Gymnasium environment. A separate metadata file records split provenance, checkpoint results, model compatibility, and artifact integrity. The API serves only this metadata to a read-only Research card.

**Tech Stack:** Python 3.12, Gymnasium, Stable-Baselines3, PyTorch, FastAPI, React.

**Spec:** [GitHub issue #21](https://github.com/kprashanth01/finapp/issues/21)

## Global Constraints

- Keep `selection-proxy-v1`, `planning-observation-v1`, and `agent-subset-v1` stable.
- Use generated scenarios only; do not read saved user data for training.
- The Advisor stays rule based. The new DQN is an offline research artifact in this milestone.
- Make the normal web app usable without PyTorch installed.
- Choose a checkpoint with validation cases, then evaluate the held-out test split once.

## Review Focus

- The random episode sampler must draw only from its assigned split.
- Loading must reject an artifact whose checksum or schema disagrees with metadata.
- The web app must show a clear unavailable state if the DQN artifact is missing.
- A selected policy action must be within the default 63-action catalogue.
- Small training runs must be usable for a smoke test without overwriting the committed artifact.

---

### Task 1: Split and environment contract

**Files:** `backend/app/rl/scenarios.py`, `backend/app/rl/environment.py`, `backend/tests/test_rl_training.py`

- [ ] Write a failing test for deterministic, disjoint train/validation/test splits and sampled reward/termination.
- [ ] Run the targeted test and observe the expected failure.
- [ ] Add split construction and any minimal environment correction, then pass Gymnasium and SB3 checks.
- [ ] Run the targeted and existing RL tests.

### Task 2: Train, choose, and save DQN

**Files:** `backend/app/rl/dqn_training.py`, `backend/app/rl/dqn_artifact.py`, `backend/requirements-rl.txt`, `backend/tests/test_dqn_training.py`

- [ ] Write failing tests for bounded training, valid prediction after reload, split isolation, and incompatible/tampered artifact rejection.
- [ ] Run the targeted tests and observe the expected failures.
- [ ] Implement the CPU DQN CLI and metadata/checkpoint contract; keep training imports outside normal API startup.
- [ ] Run smoke training, select by validation, perform the final test pass, and record the measured results.

### Task 3: Read-only Research evidence

**Files:** `backend/app/rl/api.py`, `frontend/src/services/api.js`, `frontend/src/components/Research.jsx`, `frontend/src/index.css`, backend/frontend tests.

- [ ] Write failing API and frontend tests for available/unavailable evidence and accurate limitations.
- [ ] Implement a read-only metadata endpoint and concise Research card.
- [ ] Verify the card in a browser without saving a profile or advisory session.

### Task 4: Reproducibility and final review

**Files:** `README.md`, `backend/app/rl/dqn_model.zip`, `backend/app/rl/dqn_metadata.json`

- [ ] Document Python setup, training and inspection commands, seeds, splits, caveats, and artifact versions.
- [ ] Run complete backend and frontend suites, production build, artifact load/predict, and diff checks.
- [ ] Commit, push, and open a PR that closes issue #21.
