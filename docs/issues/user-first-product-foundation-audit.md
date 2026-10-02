# Issue 1 — User-first product foundation audit

Audited 2026-10-02 against the current working tree. This issue records the existing system and the smallest coherent path toward a personal financial assistant. It changes no application behavior. The earlier [research architecture audit](../research-architecture-audit.md) describes an older state of the project; this audit reflects the later recorded-month and local-chat work.

## Current application and data flow

```text
React/Vite views → API client → FastAPI routes and account ownership checks
  → PostgreSQL models (via SQLAlchemy and Alembic)
  → deterministic financial analysis → immutable planning state
  → six structured agents → rule-based orchestrator → coordinated plan
  → saved analysis session → Dashboard, Advisor, and saved-run chat

Separate Research path: synthetic cases/months → Gymnasium environments
  → rule/random/DQN agent selection → proxy rewards and paired evaluations
```

| Area | Reusable implementation | Boundary for the product goal |
| --- | --- | --- |
| Frontend | `frontend/src/Workspace.jsx` loads account data and coordinates Dashboard, Profile, Months, Goals, Advisor, and Research. `frontend/src/services/api.js` contains the API client. Dashboard shows a first priority, supporting fact, monthly allocation, and read-only scenario preview. | The core path still asks for a fairly complete profile before a funded plan. Chat is inside a saved Advisor run. Months and its variable-income interpretation are a separate view, with research-oriented results. |
| Backend and accounts | `backend/app/main.py` mounts FastAPI routes; `auth_api.py` and `auth_dependencies.py` manage cookie sessions and account ownership. `api.py`, `goal_api.py`, and `rl/api.py` handle current finances, goals, saved plans, recorded months, and research. | User-facing monthly data is currently routed from `rl/api.py`; product planning does not read that history. |
| Database | `backend/app/models.py` and migrations `0001`–`0008` define users, profiles, goals, recorded financial months, saved analysis sessions, account sessions, and research experiment tables. Saved plans keep a result payload and input fingerprint. | No separate expense item, loan, obligation, or planned-expense entity exists. A recorded month is an entered snapshot, not a categorized ledger or future plan. |
| Profile | `User.monthly_income` is one gross monthly amount. `FinancialProfile` stores aggregate expenses, savings, emergency fund, debt balance, optional debt payment and savings contribution, risk tolerance, and horizon. | No distinction among guaranteed, expected, and observed income. Aggregate debt lacks interest rate, payment due date, and principal per loan. Aggregate expenses cannot distinguish essential from discretionary spending. |
| Income history | `FinancialMonth` stores income, total and fixed expenses, scheduled/paid EMI, balances, and other month-level values. `rl/account_months.py` calculates recent change and up-to-12-month income volatility for a selected recorded month. | History does not feed the saved Advisor state or its planning income. The month view does not calculate a conservative planning income for the live plan, and zero recorded volatility with one month should not be interpreted as stable income. |
| Goals | `FinancialGoal` has name, target, saved amount, date, priority, and archive state. The Goal agent calculates requirements and the plan proposes monthly allocations. | The plan can compare goals with the entered savings budget, but cannot account for upcoming non-goal obligations or loan-level deadlines. |
| Financial analysis | `FinancialAnalysisService` calculates savings, debt-payment, and expense ratios plus emergency coverage and an illustrative health score. `PlanningState` snapshots these values and active goals. | The core analysis lacks an explicit monthly cash-flow amount, essential/discretionary split, income uncertainty, upcoming obligations, and available discretionary amount. Emergency coverage uses total expenses because essential expenses are unknown. Ratios use gross income. |
| Six agents | `AgentRegistry` provides Budget, Debt, Emergency, Goal, Risk, and Investment agents. They return structured findings, evidence, limitations, and planning facts. Dynamic versions can consume monthly research state. | Core agents mostly consume the single profile snapshot. Existing structured contracts should be extended when richer product facts exist, not replaced. |
| Saved decisions | `RuleBasedOrchestrator` selects the agents and `RecommendationEngine` conserves the user-entered monthly savings contribution across reserve and goals, with a debt-review hold. The output has actions and evidence links. | Priority order is fixed in `advisory/rules.py`; reserve is allocated before goals. Mandatory payment timing, high-cost debt, planned expenses, and income uncertainty cannot yet participate in priority decisions. A savings contribution is an entered intention, not inferred disposable cash. |
| Scenarios | `advisory/scenario.py` runs the same saved rule path with temporary income, total expenses, and savings contribution; the Dashboard compares baseline and hypothetical results. | No scenario-specific events, item changes, one-time costs, loan payments, or plan dates. The comparison is read-only and does not persist the hypothetical values. |
| Conversation and explanations | `advisory/chat.py` answers from one saved run. Optional local Ollama wording in `chat_model.py` receives an evidence catalog, validates cited IDs and numbers, and falls back to deterministic text. `AdvisorChat.jsx` displays the answer and evidence. Separately, `advisory/reasoning.py` can request a structured qualitative explanation from OpenAI, with a deterministic fallback. | The assistant cannot run a new analysis, ask for missing structured details, or execute a scenario from natural language. Its context is one saved snapshot, which may be stale. Output checks reduce invention risk but do not prove every qualitative claim is supported. |
| RL/DQN | `backend/app/rl/` keeps the original one-step selector and newer dynamic monthly environment, versioned observations/actions/rewards, synthetic trajectories, training, model artifacts, and comparison reports. `Research.jsx` separates these from the normal plan. | DQN selects agents; it does not produce financial advice or improve observed balances. The saved Advisor still uses rules. Recorded-month comparison is informative but does not make the DQN the product decision maker. Synthetic proxy reward is not a household outcome. |

## Existing API surface relevant to this direction

- Account and profile: `/auth/*`, `/users/{user_id}`, `/users/{user_id}/financial-profile`, `/users/{user_id}/financial-analysis`.
- Goals: `/users/{user_id}/goals` and goal update/archive routes.
- Saved advice: `/users/{user_id}/advisory-sessions`, latest/history/detail, plus saved-run reasoning and chat.
- Temporary preview: `POST /users/{user_id}/advisory-scenario`.
- Recorded history: `/users/{user_id}/financial-months`, per-month advice, plan preview, and per-month questions.
- Research: `/users/{user_id}/research/*` for selector runs, comparisons, evaluation, and model evidence.

All account-scoped routes should continue enforcing ownership. Adding data in Issue 2 should preserve existing profile and goal endpoints or version their contracts deliberately.

## Product foundation decisions for the next issues

1. **One canonical financial picture for advice.** Preserve existing profile, goals, and months. Add user-facing detail without creating a second independent truth for the same amount. Recorded months are observations; the current profile is an editable planning snapshot. The analysis layer must say which source each value came from.
2. **Income semantics before forecasting.** Represent observed history, a user-entered expectation, and any genuinely guaranteed amount separately. A conservative planning figure should be a labeled calculation with insufficient-history behavior, never a claim that the lowest observed month will recur.
3. **Expense and loan detail remain optional.** Keep aggregate values usable for a quick first plan. When itemized details are supplied, validate that totals and mandatory obligations reconcile, and avoid counting EMI twice. Missing breakdown means unknown essential/discretionary shares, not zero.
4. **Deterministic facts and decisions.** Extend the analysis state first, then scenarios and priorities. The chat may explain or request missing inputs, but it should only quote application-computed amounts and decisions.
5. **Protect the research boundary.** Keep original and dynamic DQN artifacts, training, rewards, evaluations, and their versioned contracts. Product data changes should not silently rewrite synthetic experiment meanings. Normal advice remains rule-based until its richer financial state and decision path are verified.
6. **Preserve historical meaning.** Saved runs contain snapshots and fingerprints. New model fields need migration/backfill rules and versioned state or result handling so older sessions remain readable and clearly identified as earlier analyses.

## Issue 2 implementation boundary

Add the real-user financial data model and minimal entry/edit flow for income history and planning assumptions, expense items and categories, loan obligations, and upcoming one-time expenses. Keep goals and emergency savings in their existing tables/fields where they already fit. Reuse recorded months rather than inventing a second income-history table unless a migration need is demonstrated. Provide source/meaning labels in the UI and API. Do not yet turn these inputs into a new recommendation algorithm, chat workflow, or DQN policy.

Issue 2 is ready when a user can save and retrieve each new optional detail under their own account, existing profile/goals/months and old saved analyses remain accessible, validation prevents duplicate or inconsistent monetary totals, and focused persistence/API tests pass. Issue 3 can then build the canonical deterministic analysis over those inputs.

## Verification scope

This is a code audit, not a live account or browser trial. Existing automated checks were run separately; their results belong in the completion report. A live PostgreSQL migration, an actual Ollama reply, and an actual OpenAI explanation were not exercised by this document.
