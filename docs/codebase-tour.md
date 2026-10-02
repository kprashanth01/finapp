# Codebase tour

FinApp is one repository with a React frontend, FastAPI backend, PostgreSQL schema, and separate experiment code. This map is for someone looking for the right place to read or change a behavior.

## Request to recommendation

```text
frontend/src/Workspace.jsx
  → frontend/src/services/api.js
  → backend/app/main.py and route modules
  → backend/app/models.py / PostgreSQL
  → backend/app/services/financial_analysis.py
  → backend/app/services/financial_picture.py
  → backend/app/advisory/state.py
  → six agents through backend/app/advisory/registry.py
  → backend/app/advisory/orchestrator.py
  → saved result → Dashboard / Advisor components
```

The frontend does not decide how to allocate a saved monthly contribution. It collects and displays data; the backend validates inputs and performs the authoritative planning. Some frontend services calculate **read-only worksheet previews** to help the user choose an amount, while the backend still validates requests and creates the coordinated result.

## Frontend

| Path | Responsibility |
| --- | --- |
| `frontend/src/Workspace.jsx` | Loads the signed-in account, routes between views, coordinates saves and analysis runs. |
| `frontend/src/components/Dashboard.jsx`, `AdviceOverview.jsx`, and `UserRecommendations.jsx` | Dashboard layout, monthly snapshot, upcoming obligations and goals, and ranked current actions. |
| `frontend/src/components/CurrentChat.jsx` | Current-picture questions, temporary scenario comparisons, and expandable supporting evidence. |
| `frontend/src/components/ScenarioPreview.jsx` and `EventScenario.jsx` | Optional what-if previews for a hypothetical month or specific change. |
| `frontend/src/components/FinancialProfileForm.jsx` and `UserForm.jsx` | Profile fields and user details. |
| `frontend/src/components/FinancialDetails.jsx` | Optional income context, recurring expenses, loans, and upcoming one-time costs; entries describe the Profile totals. |
| `frontend/src/components/Goals.jsx` | Goal list, editing, and archive controls. |
| `frontend/src/components/AccountMonths.jsx`, `MonthlyPlanningSummary.jsx`, and `RecordedMonthPlan.jsx` | Recorded month entry, cash-flow interpretation, and read-only month plan preview. |
| `frontend/src/components/AdvisoryPlan.jsx`, `AdvisorySession.jsx`, and `AdvisoryHistory.jsx` | Coordinated plan, evidence, and saved runs. |
| `frontend/src/components/Research.jsx` | Entry to the experimental screens. |
| `frontend/src/services/api.js` | Axios client, session cookie use, and API methods. |
| `frontend/src/services/monthlyPlanning.js` | Local worksheet arithmetic for recorded-month previews. |
| `frontend/tests/` | Node tests for presentation and user-facing behavior. |

The frontend uses Vite and Tailwind CSS. `frontend/package.json` lists the available scripts. Its API URL defaults to the current page's hostname at port 8000, so the browser and API should be opened on the same local hostname.

## Backend

| Path | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI app, health endpoint, CORS and mutation checks, router registration. |
| `backend/app/auth_api.py` and `auth_core.py` | Account creation, login, session and password handling. |
| `backend/app/api.py` and `goal_api.py` | Financial profile, analysis, advisory, and goal endpoints. |
| `backend/app/financial_details_api.py`, `financial_detail_schemas.py`, and `services/financial_details.py` | Account-owned optional detail snapshot, validation, and reconciliation with aggregate totals. |
| `backend/app/models.py` | SQLAlchemy tables for accounts and saved financial data. |
| `backend/app/database.py` | Database engine and root `.env` loading. |
| `backend/app/services/financial_analysis.py` and `financial_picture.py` | Deterministic ratios and sourced financial facts. |
| `backend/app/services/user_recommendations.py` and `current_chat.py` | Ranked current actions and a read-only conversation grounded in those actions and the current picture. |
| `backend/app/services/conversational_scenarios.py` and `event_scenario.py` | Parse supported what-if questions conservatively and calculate temporary before/after event facts. |
| `backend/app/advisory/agents.py`, `goal_agent.py`, `risk_agent.py`, `investment_agent.py` | Six specialist checks that use the picture in saved runs and return structured findings. |
| `backend/app/advisory/state.py`, `registry.py`, `orchestrator.py`, `recommendations.py` | Planning state, available agents, selection, and coordinated actions. |
| `backend/app/advisory/service.py`, `scenario.py`, `month_plan.py` | Saved analysis and read-only scenario/month previews. |
| `backend/app/advisory/explain.py`, `reasoning.py`, `chat.py` | Structured evidence, optional narrative wording, and saved-run questions. |
| `backend/app/rl/` and `backend/app/rl/api.py` | Experimental selectors, synthetic environments, DQN artifacts, and research API. The existing account-month routes and recorded-month plan preview also live in this router. |
| `backend/alembic/versions/` | Ordered PostgreSQL schema migrations. |
| `backend/tests/` | API, planning, ownership, and research checks. |

FastAPI exposes its current endpoint schema at `/docs` while the API is running. The [detailed reference](implementation-reference.md#api-available-now) includes a route overview.

## Where to start for a change

- **A user-visible field or explanation:** locate the React component, then check its API method and backend schema or planning rule. Do not silently duplicate financial rules in the browser.
- **A calculation or allocation:** start in `backend/app/services/` or `backend/app/advisory/`, then update the visible explanation and focused tests.
- **Stored data:** inspect `backend/app/models.py` and add an Alembic migration; do not rely on `create_all` to update an existing database.
- **Research or DQN:** start in `backend/app/rl/` and the [research guide](research.md). Keep synthetic proxy results clearly separate from saved user plans.

See [Contributing](../CONTRIBUTING.md) for the development and pull request checks.
