# Issue 1 — Repository and research architecture audit

Audited 2026-09-30 from merged `main` at `9dbf342` (PR #30, optional LLM reasoning). This is an evidence-based status report for the requested research direction. It changes no application behavior.

## Architectural stage

The project is a working, single-snapshot advisory application with six deterministic agents, a saved rule-based plan, and a separate research path that compares agent-selection policies. Its trained DQN solves a **one-step agent-selection problem** with a rule-defined proxy reward. The app has not yet modeled one person's finances changing over multiple months, so the current experiments cannot answer whether RL adapts better than the rule policy under volatile income.

The existing system is a strong starting point for temporal research. The next work should extend its state, generator, environment, and evaluation contracts while preserving the current Advisor path and versioned evidence.

## What exists and how it connects

| Area | Current implementation and evidence | Status for the research question |
| --- | --- | --- |
| Application | React/Vite frontend, FastAPI backend, SQLAlchemy/PostgreSQL models, Alembic migrations `0001`–`0006`; account, profile, goal, Advisor, and Research flows. See `frontend/src/Workspace.jsx`, `backend/app/main.py`, `backend/app/models.py`, `backend/alembic/versions/`. | Functional application foundation; a live PostgreSQL run was not part of this audit. |
| Financial data | `User` has one gross monthly income. `FinancialProfile` has one expense, savings, debt, emergency-fund, contribution, debt-payment, risk, and horizon snapshot. `FinancialGoal` is a separate table; `AnalysisSession` stores immutable rule-plan JSON. | No persona, per-user monthly trajectory, income shock, debt instrument, synthetic-population, or train/test-assignment model. Reuse existing tables where appropriate; keep research data distinct from private accounts. |
| State and analysis | `FinancialAnalysisService` computes ratios; `FinancialState` and `PlanningState` capture saved inputs, goals, planning date, and a fingerprint. See `backend/app/services/financial_analysis.py` and `backend/app/advisory/state.py`. | State has no month index, recent-income change, volatility, or financial transition. |
| Agents | `AgentRegistry.default()` registers Budget, Debt, Emergency Fund, Goal Planning, Risk Assessment, and Investment. All return structured findings through the common `analyze` interface. See `backend/app/advisory/registry.py`, `agents.py`, `goal_agent.py`, `risk_agent.py`, and `investment_agent.py`. | Real deterministic checks, not placeholders. They evaluate the current snapshot; none uses a monthly history. |
| Saved orchestration | `RuleBasedOrchestrator` always selects Budget, Emergency, Risk, and Investment; adds Debt when debt is recorded and Goal Planning when goals exist. `RecommendationEngine` allocates the recorded monthly savings contribution to reserve then goals, with a debt-review hold. `run_advisory()` saves this path. See `backend/app/advisory/orchestrator.py`, `recommendations.py`, `service.py`, and `backend/app/api.py`. | Working baseline and explainable plan. No policy switch for the saved Advisor plan. |
| Experimental orchestration | `run_orchestration()` offers `rule_based`, seeded `random`, or `rl`; all map an action to registered agents, execute them, score the choice, and return a trace. A complete plan is built only when the selected set covers the required agents. DQN loading is cached per API process. See `backend/app/rl/orchestration.py`, `environment.py`, `selection.py`, and `backend/app/rl/api.py`. | Integrated research selector, but experimental runs are not stored as advisory history. The mode is request-selected, not an `ORCHESTRATOR_MODE` deployment setting. |
| Action space | `ActionCatalog` maps all 63 nonempty subsets of six agents to stable IDs; callers may supply a restricted catalogue. See `backend/app/rl/selection.py`. | Agent activation only. The master prompt's ten actions are examples, not an existing mapping; changing IDs would invalidate the committed model. |
| Observation | 16 bounded features encode ratios, reserve coverage, debt balance, goal count/gap/timing, horizon, risk preference, and missing-input flags. See `backend/app/rl/observation.py`. | No temporal signal or explicit income shock. Features and order are versioned. |
| Reward | `selection-proxy-v1` adds relevant coverage (+1), critical coverage (+2), missed-critical penalties (−3), unneeded-agent penalties (−0.75), and agent-call penalties (−0.15); an audit exposes components and thresholds. See `backend/app/rl/reward.py`. | Interpretable selection proxy. It does not score financial outcomes, recommendation consistency, conflict resolution, or improvement over months. Its relevance rules overlap the rule baseline. |
| Environment | `AgentSelectionEnv` implements Gymnasium `reset`, `step`, `observation_space`, and `action_space`; one selection executes the agents, returns the same state, and terminates. See `backend/app/rl/environment.py`. | Genuine Gymnasium interface; one-step contextual bandit, not a sequential financial trajectory. |
| Synthetic cases | `generate_scenarios()` makes seeded, in-memory coverage cases. `build_splits()` uses distinct seeds and checks fingerprint overlap. See `backend/app/rl/scenarios.py`. | No persistent population, four personas, user-level 80/20 split, or multiple months per user. Scenario counts are **cases**, not synthetic users. |
| Learned policies | An older NumPy network in `policy.py` fits the complete 63-action proxy-reward table and writes `model.json`. The newer Stable-Baselines3 DQN in `dqn_training.py` learns from sampled one-step transitions; its ZIP and metadata are committed. See `backend/app/rl/train.py` and `dqn_artifact.py`. | Two intentionally distinct research methods. The fitted full-information model must not be called the trained DQN. The DQN is trained for the existing one-step task. |
| Evaluation and UI | `evaluation.py` runs random, rule, and DQN on the same fixed generated cohort; it reports reward, coverage, calls, full-plan rate, timing, segments, and paired rule/DQN results. Research shows this report and model evidence; Advisor exposes read-only experimental selection. See `frontend/src/components/Research.jsx`, `OrchestrationLab.jsx`, and `backend/app/rl/evaluation.py`. | Useful paired selection evaluation. There is no longitudinal volatile-income comparison, evaluated conflict ontology, per-person trajectory inspection, or evaluation database/dashboard. |
| Explanation | Structured traces connect selections, executed findings, input context, reward, and recommendations. DQN explanations explicitly avoid claiming feature-level causation. PR #30 adds an optional, on-demand OpenAI narrative over the captured evidence, strict structured output checks, and a deterministic fallback. The wording is not saved in advisory history. See `backend/app/advisory/explain.py`, `reasoning.py`, and `frontend/src/components/ReasoningPanel.jsx`. | LLM reasoning now exists as an optional explanation layer. It does not choose agents or calculate financial amounts. There is no advisor chat or evidence that its prose improves recommendation quality. |

The older NumPy fitted model and DQN are separate by design. Likewise, the persisted rule-based Advisor plan and read-only Research runs have different roles. Their names and UI must continue to distinguish them so an experimental partial selection is not mistaken for a saved complete plan.

## Existing measured evidence and its limits

The committed `dqn_metadata.json` records **12,000 environment/training steps**, using **1,536 training**, **384 validation**, and **384 held-out test scenarios**. Its selected 12,000-step checkpoint scored **7.823 mean proxy points** on its 384-case test split, with a **0** critical-miss rate under the project's own labels. These values come from committed metadata, not a training rerun in this audit.

The separate committed `evaluation_report.json` uses a further **256 generated cases** for all methods (five random seeds, one rule run, one DQN run). Mean proxy rewards are **1.3348** for random, **7.8781** for rule, and **7.8250** for DQN. DQN matched the rule selection in **240** cases and scored lower in **16**; it scored higher in **0**. Full-plan rates are **2.5%**, **100%**, and **93.75%**, respectively. The report records no measured recommendation-consistency or conflict metric. This evidence supports neither RL superiority nor real financial benefit. Reward points are not currency or observed household outcomes.

The full-information fitted model has its own generated-case benchmark in `model.json` and `backend/app/rl/train.py`. Keep it separate from the DQN evidence and from the 256-case paired DQN evaluation.

## Gaps to address in later issues

1. **Population and temporal data:** Define reproducible synthetic user identities, personas, assumptions, and month-by-month states. The existing generator produces independent coverage cases and has no persistent user grouping. When introducing user-level splits, all months for a user must stay together.
2. **Transition meaning:** Specify which state variables change exogenously (income and shocks) and which, if any, can change because an advisory action was selected. The current action is advice selection and does not change balances. A multi-step environment should not manufacture financial improvement simply from issuing advice.
3. **Evaluation validity:** Preserve the fixed cohort and versioned reward contract, then add paired temporal tests, volatile-income strata, and honest uncertainty reporting. Reward overlap with the rule policy is a central validity limit; a new reward needs a documented rationale and ideally independent expert or outcome labels.
4. **Agent context:** The six existing agents can be extended with monthly/current/recent-income context. Aggregate debt data lacks interest rate, EMI schedule, and debt type. Do not create duplicate live-user models solely for synthetic research.
5. **Research presentation:** The current UI clearly labels proxy evidence and offers the optional explanation panel, but there is no per-month trajectory view, conflict-case review, or advisor chat. LLM wording is not an evaluation metric or a substitute for the deterministic agent results.

## Verification performed

From the repository root after a fast-forward check against `origin/main`:

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
# 129 passed

Set-Location ..\frontend
npm test
# 27 passed; the runner also printed intermittent Vite WebSocket port-in-use messages
npm run build
# Vite production build succeeded
```

These checks verify the local code and tests. They do not verify a live PostgreSQL database, browser end-to-end flow, a real OpenAI response, or a fresh DQN training run. No new package, API key, service, migration, or environment variable is required to review this audit. Running the app later needs the existing PostgreSQL setup in `README.md`; running trained RL requires the pinned `backend/requirements-rl.txt` environment described there. The optional LLM narrative needs `OPENAI_API_KEY` in the root `.env` and an API restart; without it, the explanation endpoint returns the deterministic fallback. `FINAPP_LLM_MODEL` may override the default model.

## Next issue: reproducible synthetic financial population

Build Issue 2 around exactly 12,000 **synthetic profiles** in the specified 30% gig, 35% salaried-with-loan, 20% student/fresh-graduate, and 15% near-retiree proportions. First agree on a versioned persona definition and constraints based on the existing profile/goal/state contracts. Implement a seeded generator and a compact validation report with exact counts, distribution summaries, and same-seed reproducibility. Treat these proportions as experiment design assumptions. Keep monthly trajectories and user-level train/test splitting as later, separately reviewable milestones. No application or database changes are proposed as part of this audit.
