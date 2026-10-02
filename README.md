# FinApp

FinApp is a local web application for exploring everyday financial decisions. Enter your income, spending, savings, debt, and goals; it shows what needs attention, how much of a **monthly amount you choose to save** could go toward each priority, and why. A separate Research area compares fixed rules with experimental agent-selection methods, including a trained DQN.

**Project status:** This is an educational prototype under active development. Use practice financial values. It does not connect to bank accounts, move money, choose investments, predict returns, or replace a financial professional. Research scores measure a project-defined simulation, not real-world financial outcomes.

## What you can do

| In the app | What it helps you answer |
| --- | --- |
| **Dashboard** | Is my month in gross shortfall or surplus, what needs attention first, and what can I ask about my current finances? |
| **Profile** | What income, expenses, balances, payments, and risk preferences is the plan using? Optional detail records describe recurring costs, individual loans, and upcoming one-time expenses. |
| **Months** | How did cash flow change across months? What if a lower-income month recurs? |
| **Goals** | Can my current monthly allocation support a target and date? |
| **Advisor** | How are emergency savings, debt, goals, and investment readiness coordinated? Why? |
| **Research** | How do the rule-based, random, and trained selectors behave in controlled experiments? |

The main saved plan is **rule based**. Six specialist agents check budget, debt, emergency savings, goals, risk, and investment readiness using the current financial picture. They return sourced findings for the coordinator and saved explanation. A gross cash shortfall holds the entered savings amount unassigned for review. Experimental selectors run separately; an incomplete selection does not become a complete saved plan.

## Get it running

You need **Python 3.10+**, **Node.js 20.19+ or 22.12+ with npm**, and **PostgreSQL**. Git is needed to clone the repository. The normal planning flow does **not** require PyTorch, Ollama, or an API key.

1. Clone the repository: `git clone https://github.com/kprashanth01/finapp.git`, then `cd finapp`.
2. Create a local PostgreSQL database and login, and put its connection URL in the repository-root `.env` file.
3. Create a Python virtual environment, install `backend/requirements.txt`, install frontend packages with `npm ci`, and run the database migrations.
4. Start the API and frontend in separate terminals. Open the URL printed by Vite and create an account.

Follow [the complete local setup guide](docs/setup.md) for copyable **Windows PowerShell** and **macOS/Linux** commands, database creation, verification, and common fixes. The API provides [interactive endpoint documentation](http://127.0.0.1:8000/docs) while it is running.

### First five minutes in the app

1. Create an account with practice details.
2. In **Profile → User details**, enter gross monthly income. Save your financial profile, including monthly expenses and the amount you can actually save per month.
3. On **Dashboard**, read the monthly snapshot, the first three ranked actions, and upcoming obligations and goals. Use **Ask about your current finances** to ask about the saved facts and actions without creating a plan. Run an analysis for the separate saved monthly allocation plan.
4. Add a goal in **Goals**, then return to Dashboard to see the current recommendation update. Run a new analysis to refresh the saved allocation plan.
5. Use **Months** to record different income or spending months, or open Dashboard's **Explore what-if changes** for one-month and specific-event previews. These previews do not edit the saved plan.

Profile also has an optional detail section for income context, recurring expense categories, loans, and upcoming one-time costs. Dashboard's current recommendation and new saved Advisor agent findings use those details and recorded months when available. The saved allocation amounts still use the aggregate Profile values; details do not add to those totals. Editing detail marks an older saved plan stale until you run a new one.

See [Using FinApp](docs/using-finapp.md) for a plain-language field guide and a worked example.

## How it fits together

```text
React + Vite browser app
       │ account, profile, goals, recorded months
       ▼
FastAPI + PostgreSQL
       │ validated inputs and deterministic calculations
       ▼
Six financial agents → rule-based coordinator → saved, explained plan
       │
       └── separate Research views: random/rule/DQN selection and synthetic evaluations
```

The browser signs in with a server-managed session cookie. The API checks account ownership and stores profiles, goals, recorded months, and saved plans in PostgreSQL. Analysis uses structured calculations and project rules; optional language models explain captured results rather than setting financial amounts. See [the codebase tour](docs/codebase-tour.md) for the main files and data flow.

## Repository guide

| Path | What is there |
| --- | --- |
| `frontend/src/` | React screens, forms, presentation, and API client |
| `frontend/tests/` | Frontend behavior tests |
| `backend/app/` | FastAPI routes, account and data models, financial services |
| `backend/app/advisory/` | Six agents, rules, planning, orchestration, explanations |
| `backend/app/rl/` | Experimental environments, DQN artifacts, evaluation code |
| `backend/alembic/versions/` | Database migrations |
| `backend/tests/` | API, planning, account, and research tests |
| `docs/` | Setup, usage, architecture, and research guides |
| `experiments/` and `data/` | Experiment settings and synthetic research artifacts |

## Documentation

- [Local setup and troubleshooting](docs/setup.md) — start from a fresh checkout.
- [Using FinApp](docs/using-finapp.md) — fields, screens, examples, and limitations.
- [Codebase tour](docs/codebase-tour.md) — where to change the product or research code.
- [Research guide](docs/research.md) — what the RL comparison measures and where to find experiment guides.
- [Detailed implementation reference](docs/implementation-reference.md) — the previous README's deeper behavior, API, and milestone history.
- [Contributing](CONTRIBUTING.md) — development checks and pull request workflow.

## Trust and limitations

Calculated facts, project rules, hypothetical previews, and experimental scores have different meanings. The app labels them separately. Its thresholds are illustrative and have not been validated as personal financial advice. A plan proposes uses for an entered monthly savings contribution; it does not create that money, forecast income, or make a transaction. The app currently lacks email verification, password recovery, MFA, and deployment-level rate limiting. Keep it local and use practice values unless you have reviewed the security and deployment requirements in the [setup guide](docs/setup.md).
