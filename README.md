# FinApp

An educational research prototype for a future RL-orchestrated, multi-agent financial advisory system. This repository currently contains only the first full-stack foundation: a React page that checks a FastAPI health endpoint. It does not yet analyze finances or provide recommendations.

## How this first slice works

```text
Browser → React page → Axios GET /health → FastAPI → {"status": "ok", "service": "finapp-api"}
```

The status on the page comes from a real request. There is no demo user or seeded financial data.

## Requirements

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ and npm
- Git

PostgreSQL, Docker, API keys, and ML packages are not required yet.

## Run locally

Use two PowerShell terminals from the repository root.

**Terminal 1 — API**

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

The API runs at <http://localhost:8000>. Open <http://localhost:8000/health> to see its JSON response.

**Terminal 2 — frontend**

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally <http://localhost:5173>. The page should show **API connected**. To observe the failure state, stop the API and click **Retry connection**.

If the API runs at a different address, copy `.env.example` from the repository root to `frontend/.env` and edit `VITE_API_BASE_URL`, then restart Vite. Vite only reads variables prefixed with `VITE_` in frontend code. The backend currently allows browser requests from the default local Vite origins on port 5173.

## Current structure

```text
backend/app/main.py         FastAPI app and health endpoint
backend/requirements.txt    Python dependencies
frontend/src/App.jsx        Connection status view
frontend/src/services/api.js Axios request to the API
frontend/vite.config.js     React and Tailwind plugins
```

## Development workflow

Each meaningful feature is tracked in a GitHub issue and built on its own feature branch. Verify it, commit it, open a pull request, review it, and merge only after approval. This issue establishes the browser-to-API path; financial profiles and analysis will be separate issues.

## Limitations

This is a research prototype, not a financial advisory product. The current endpoint reports API availability only. No database, authentication, financial calculations, agents, RL policy, LLM, or experiment results exist yet.
