# FinApp

An educational research prototype for a future RL-orchestrated, multi-agent financial advisory system. The current app lets you create a user and save or edit a financial profile in PostgreSQL. It does not calculate financial health or provide advice yet.

## How the current flow works

```text
React form → Axios request → FastAPI validation → SQLAlchemy → PostgreSQL
                                      ↓
                          saved values returned to React
```

The app does not create demo users or financial data. A user ID is kept in this browser's local storage so the same record can be loaded after a refresh. This is a local development convenience, not authentication.

## Requirements

- Git
- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ and npm
- PostgreSQL with a database and login for this project

Docker, API keys, LLM providers, and ML packages are not needed for this issue.

## One-time setup

### 1. Create a PostgreSQL database and login

If you already have a dedicated PostgreSQL login and database, use them and skip these SQL commands. On Windows with PostgreSQL 18, connect with your existing administrator password:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -U postgres -d postgres
```

At the `postgres=#` prompt, run:

```text
CREATE ROLE finapp_dev LOGIN;
\password finapp_dev
CREATE DATABASE finapp OWNER finapp_dev;
\q
```

The `\password` command asks for the new password twice without displaying it. The role and database persist across restarts; do not recreate them each time.

Verify the login:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -U finapp_dev -d finapp -c "SELECT current_user, current_database();"
```

### 2. Configure the backend connection

From the repository root, copy the safe template:

```powershell
Copy-Item .env.example .env
```

Edit the root `.env` file and set:

```text
DATABASE_URL=postgresql+psycopg://finapp_dev:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:5432/finapp
```

URL-encode special characters in the password. The `.env` file is Git-ignored. Keep the password there; do not send or commit it. FastAPI and Alembic read this root file. The `frontend/.env.example` file is only for changing the frontend's API address; the default is `http://localhost:8000`.

### 3. Install packages

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

Run the install commands again only when dependency files change. For backend tests, also install:

```powershell
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

### 4. Apply the database migration

```powershell
Set-Location backend
..\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
Set-Location ..
```

Run migrations when a new database or a new migration is added, not for every app start. Alembic records applied migrations in the database.

## Start a development session

The PostgreSQL Windows service normally starts automatically. Open two PowerShell terminals in the repository root:

**Terminal 1 — API**

```powershell
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

**Terminal 2 — frontend**

```powershell
Set-Location frontend
npm run dev
```

Open the URL printed by Vite, normally <http://localhost:5173>. Enter a user, then enter a financial profile. Refresh the page to see the saved values. The API health endpoint remains at <http://localhost:8000/health>.

## API available now

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check API availability |
| POST | `/users` | Create a user |
| GET | `/users/{id}` | Load a user |
| PUT | `/users/{id}` | Update user details, including monthly income |
| PUT | `/users/{id}/financial-profile` | Create or update the user's profile |
| GET | `/users/{id}/financial-profile` | Load the user's profile |

FastAPI also provides interactive API documentation at <http://localhost:8000/docs>.

## Verification

After installing development requirements, run the focused API checks:

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
```

These tests use a temporary local SQLite database for a fast API behavior check. The migration and browser save/reload flow must also be verified against PostgreSQL. The frontend build check is `npm run build` from `frontend/`.

## Current structure

```text
backend/app/             API, validation schemas, and database models
backend/alembic/         PostgreSQL schema migration
backend/tests/           Focused API behavior checks
frontend/src/components/ Entry forms
frontend/src/services/   Axios requests
```

## Workflow and limitations

Each meaningful feature is tracked in a GitHub issue and built on a feature branch. Verify it, commit it, open a pull request, and merge only after review.

This is a research prototype, not a financial advisory product. There is no login or access control, so use practice values rather than sensitive real-world information. Clearing browser storage loses the local link to a saved user. Financial calculations, goals, agents, orchestration, RL, LLM reasoning, and experiment results are not implemented yet.
