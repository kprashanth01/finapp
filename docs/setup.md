# Run FinApp locally

This guide starts from a fresh clone. The normal app uses a local PostgreSQL database, a Python FastAPI server, and a React/Vite frontend. The commands below use `127.0.0.1` for both services so browser session cookies and API calls use the same hostname.

## 1. Install prerequisites

- Git
- Python **3.10 or newer** and `pip`
- Node.js **20.19+ or 22.12+** and npm
- PostgreSQL, running locally, with an administrator login that can create a role and database

Check what is available:

| Windows PowerShell | macOS/Linux shell |
| --- | --- |
| `git --version`; `py --version`; `node --version`; `npm --version`; `psql --version` | `git --version`; `python3 --version`; `node --version`; `npm --version`; `psql --version` |

Install missing programs from their official distributions or your operating system's package manager. If `psql` was installed but is not on `PATH`, use its full path (for example, `C:\Program Files\PostgreSQL\18\bin\psql.exe` on a Windows PostgreSQL 18 installation). Python 3.12 is recommended if you later install the optional RL dependencies on Windows.

## 2. Clone and make a local database

```sh
git clone https://github.com/kprashanth01/finapp.git
cd finapp
```

Start the PostgreSQL service if it is not running. Connect with an administrator role; substitute its name if yours is not `postgres`:

```sh
psql -h 127.0.0.1 -U postgres -d postgres
```

At the `psql` prompt, enter the following one line at a time:

```text
CREATE ROLE finapp_dev LOGIN;
\password finapp_dev
CREATE DATABASE finapp OWNER finapp_dev;
\q
```

The `\password` command prompts for a password without putting it in shell history. If you already have a suitable database and login, use them instead of creating these again. Test the new login:

```sh
psql -h 127.0.0.1 -U finapp_dev -d finapp -c "SELECT current_user, current_database();"
```

## 3. Configure the API

Copy the repository's environment template:

```powershell
# Windows PowerShell, from the repository root
Copy-Item .env.example .env
```

```sh
# macOS/Linux, from the repository root
cp .env.example .env
```

Edit **the root `.env`** and set its database URL, for example:

```dotenv
DATABASE_URL=postgresql+psycopg://finapp_dev:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:5432/finapp
```

Replace the placeholder with the password from step 2. URL-encode special characters in a password placed in a URL (for example, `@` becomes `%40`). The root `.env` is ignored by Git. Do not commit it or paste real credentials into an issue. The optional `OPENAI_API_KEY`, `FINAPP_LLM_MODEL`, and `FINAPP_CHAT_MODEL` values can stay unset. `frontend/.env.example` is only needed when the API is on a different host or port.

## 4. Install dependencies

Run the commands for your operating system from the repository root.

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

**macOS/Linux**

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

The base Python requirements include NumPy and Gymnasium, but **do not install PyTorch**. This is enough for account, planning, rule-based, and random-mode use. See [Research](research.md) for optional trained-DQN setup. `npm ci` uses the committed `frontend/package-lock.json`.

## 5. Create the database tables

From `backend/`, run all migrations to the current head. Use this for a new database and whenever a later checkout adds migrations. Do not try to create tables manually.

**Windows PowerShell**

```powershell
Set-Location backend
..\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
Set-Location ..
```

**macOS/Linux**

```sh
cd backend
../.venv/bin/python -m alembic -c alembic.ini upgrade head
cd ..
```

Alembic reads the root `.env` through `backend/app/database.py`. It records applied revisions in PostgreSQL, so rerunning `upgrade head` is safe.

## 6. Start both services

Open **two terminals** in the repository root. Keep both running while using the app.

**Terminal A — API (Windows PowerShell)**

```powershell
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal A — API (macOS/Linux)**

```sh
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — frontend (Windows PowerShell)**

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

**Terminal B — frontend (macOS/Linux)**

```sh
cd frontend
npm run dev -- --host 127.0.0.1
```

Open **<http://127.0.0.1:5173/>** (or the address Vite prints). The API health endpoint is **<http://127.0.0.1:8000/health>** and interactive API documentation is **<http://127.0.0.1:8000/docs>**. The browser chooses its API hostname from the frontend page's hostname and uses port 8000 by default.

Create an account using practice details; a new password must contain at least 12 characters. Sign in, complete **Profile**, then run analysis on **Dashboard**. [Using FinApp](using-finapp.md) explains the fields and first plan. A new database has no demo account or sample financial history.

## Verify development changes

Install backend test requirements once:

**Windows PowerShell:** `.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt`

**macOS/Linux:** `./.venv/bin/python -m pip install -r backend/requirements-dev.txt`

Then run from `backend/`:

| Windows PowerShell | macOS/Linux shell |
| --- | --- |
| `..\.venv\Scripts\python -m pytest -q` | `../.venv/bin/python -m pytest -q` |

From `frontend/`, run `npm test` and `npm run build`. Backend tests use temporary test databases; they do not require you to run the web app. The frontend build writes ignored files under `frontend/dist/`.

## Common fixes

| Symptom | Check |
| --- | --- |
| `DATABASE_URL is missing` | Put `DATABASE_URL=` in the **root** `.env`, not only `frontend/.env`. Restart the API. |
| PostgreSQL authentication or connection error | Confirm PostgreSQL is running, host/port and database name match the URL, and the `psql` login test above succeeds. URL-encode password characters that have special meaning in a URL. |
| API is up but the page says disconnected | Open both services through `127.0.0.1`, check `/health`, and confirm the frontend is calling port 8000. If you intentionally change hosts or ports, set `VITE_API_BASE_URL` in `frontend/.env` and review `FINAPP_ALLOWED_ORIGINS` on the API. |
| A table or column is missing | Run `alembic upgrade head` from `backend/` against the same database URL used by the API. |
| `npm ci` cannot find a lockfile | Run it from `frontend/`, which contains `package-lock.json`. |
| An optional DQN or chat action fails | Start with the normal app first; trained DQN needs additional Python packages and local chat needs Ollama. See [Research](research.md). |

## Existing installations and deployment

If you have an older local account without a password, see [claiming an earlier profile](implementation-reference.md#5-claim-an-earlier-local-profile-once-existing-installs-only). New installations do not need this step.

This guide is for local development. A non-loopback deployment needs reviewed HTTPS, secure cookie and origin settings, and further operational controls. FinApp does not yet provide email verification, password recovery, MFA, or deployment-level rate limiting. Use practice values on an unreviewed deployment. More implementation details are in the [detailed reference](implementation-reference.md#workflow-and-limitations).
