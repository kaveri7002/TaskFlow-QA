# TaskFlow QA

TaskFlow QA is a small, full-stack project and task management app with a Trello-style board. Each account sees only its own tasks. It includes a Flask REST API, PostgreSQL support, a responsive HTML/CSS/JavaScript frontend, and pytest, Selenium, and Playwright tests.

> This is a new, separate project. It does not change the existing attendance app. Do not put real personal data in a learning/demo deployment.

## What is included

- Register and sign in; passwords are stored as secure hashes, never as plain text.
- Create, edit, delete, search, and filter tasks by priority.
- Move tasks among To do, In progress, and Completed, including by drag-and-drop.
- Set a priority and optional due date.
- REST API with validation, JSON errors, expiring signed bearer tokens, and per-user access checks.
- PostgreSQL support for deployment; SQLite is used by default for a simple local start.
- Pytest API tests, Selenium browser tests, Playwright browser/API tests, HTML reports, optional Allure results, and CI.

## Architecture

```mermaid
flowchart LR
    Browser[Browser: HTML, CSS, JavaScript] -->|HTTPS JSON + bearer token| API[Flask REST API]
    API --> ORM[SQLAlchemy ORM]
    ORM --> Local[(SQLite for local learning)]
    ORM --> Prod[(Railway PostgreSQL)]
    CI[Optional GitHub Actions] --> Tests[pytest + Selenium + Playwright]
    Tests --> API
    Frontend[Vercel static frontend] -->|TASKFLOW_API_URL| API
```

The Playwright board test captures a real browser screenshot in `screenshots/` when it runs. The shared pytest hook also saves a screenshot when a Selenium or Playwright test fails.

![TaskFlow QA project board](screenshots/taskflow-board.png)

## Project map

```text
TaskFlow-QA/
├── backend/                 Flask API, SQLAlchemy models, Railway start config
├── database/                Local SQLite database location
├── frontend/                Static HTML, CSS, and JavaScript
├── tests/
│   ├── selenium_tests/      Selenium end-to-end browser tests
│   ├── playwright_tests/    Playwright browser and API tests
│   ├── conftest.py          Shared test fixtures and test server
│   └── test_api.py          Flask API/database tests
├── reports/                 Generated pytest/Allure reports (not committed)
├── screenshots/             Sample board image and browser test screenshots
├── .github/workflows/       GitHub Actions checks
├── requirements.txt
└── README.md
```

## Install the tools

Install **Python 3.10+** and **Git**. The frontend is static HTML, CSS, and JavaScript; Node.js is not needed to run it. You do not need PostgreSQL for a first local run; SQLite is included with Python. You need Chrome for Selenium. Playwright downloads its own supported browser versions.

Open PowerShell in the `TaskFlow-QA` folder. For example:

```powershell
cd "$HOME\Downloads\zxing-master\TaskFlow-QA"
```

### 1. Set up Python

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell says script execution is disabled, use Command Prompt instead and activate with:

```bat
.venv\Scripts\activate.bat
```

Copy the example settings file. The defaults are enough for local development:

```powershell
Copy-Item .env.example .env
```

For a public deployment, replace `SECRET_KEY` with a long, random value. Production startup intentionally fails if the persistent secret is missing, preventing tokens from becoming invalid across server workers/restarts. Never commit `.env`.

### 2. Start the app

```powershell
cd "$HOME\Downloads\zxing-master\TaskFlow-QA"
python -m backend.app
```

The app and API listen at `http://localhost:5000`; the health check is `http://localhost:5000/api/health`. Open the app in a browser and register an account. There is no default shared login.

## Run automated tests

Keep Flask's dependencies installed in the active `.venv`. Browser tests start a temporary test server themselves, so the regular development server does not need to be running. Install Playwright Chromium once:

```powershell
cd "$HOME\Downloads\zxing-master\TaskFlow-QA"
python -m playwright install chromium
```

Run API, Selenium, and Playwright Chromium tests:

```powershell
pytest
```

Selenium uses Chrome and Selenium Manager to locate/download its driver if needed. To run just one group:

```powershell
pytest tests\test_api.py
pytest tests\selenium_tests
pytest tests\playwright_tests
```

To try all three Playwright browser engines, install their browsers and then run:

```powershell
python -m playwright install chromium firefox webkit
$env:TASKFLOW_BROWSERS = "chromium,firefox,webkit"
pytest tests\playwright_tests
Remove-Item Env:TASKFLOW_BROWSERS
```

Firefox and WebKit need their browser downloads. If WebKit's required operating-system libraries are missing, those browser tests are reported as skipped with a reason; the GitHub Actions workflow installs WebKit dependencies on Linux. Chromium is the default.

`pytest` writes an HTML report to `reports\pytest-report.html`. To create Allure result data:

```powershell
pytest --alluredir=allure-results
```

If the Allure command-line program is installed, open the report with:

```powershell
allure serve allure-results
```

## Database notes

The local database is created automatically at `database\taskflow-local.db`. To use PostgreSQL locally, create a database and set `DATABASE_URL` in `.env`, for example:

```text
DATABASE_URL=postgresql://taskflow_user:your_local_password@localhost:5432/taskflow
```

The app also accepts Railway's `postgres://`/`postgresql://` URL and adapts it to the Psycopg 3 driver. `db.create_all()` creates missing tables for this starter app. For a production system with existing data, add Alembic/Flask-Migrate migrations before changing database schemas.

## API reference

All JSON responses use `/api`. Authenticated requests send `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | Create account (`name`, `email`, `password`) |
| POST | `/api/auth/login` | Sign in (`email`, `password`) |
| GET | `/api/auth/me` | Current account |
| GET | `/api/tasks` | List/search/filter own tasks (`search`, `status`, `priority`) |
| POST | `/api/tasks` | Create task |
| PATCH / PUT | `/api/tasks/<id>` | Update task fields / task |
| DELETE | `/api/tasks/<id>` | Delete own task |

Task status values are `todo`, `in_progress`, and `completed`. Priority values are `low`, `medium`, and `high`. Due dates use `YYYY-MM-DD`.

## GitHub

Initialize a repository only if you have not already created one:

```powershell
git init
git add .
git status
git commit -m "Build TaskFlow QA project management app"
```

Create an empty repository in your GitHub account, then use its URL:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/TaskFlow-QA.git
git push -u origin main
```

Never commit `.env`, passwords, tokens, database files, or test screenshots containing private information. Review `git status` before every push.

## Deploy (after local tests)

Deployments need your Vercel, Railway, and GitHub accounts; this source setup does not grant those account permissions automatically.

### Railway API and PostgreSQL

1. Push the repository to GitHub and connect it to Railway.
2. Add a Railway PostgreSQL service.
3. Configure the web service to use the project root (where `requirements.txt` is) and `backend/railway.json`.
4. Set `DATABASE_URL` to Railway's PostgreSQL connection URL.
5. Set `SECRET_KEY` to a new, long random secret, `FRONTEND_ORIGINS` to the Vercel site URL, and `TOKEN_MAX_AGE_SECONDS` to `86400`.
6. Deploy and verify `https://YOUR-RAILWAY-DOMAIN/api/health` returns `{"status":"ok"}`.

### Vercel frontend

1. Import the same GitHub repository into Vercel.
2. Set the **Root Directory** to `frontend`.
3. Set the framework preset to **Other**, output directory to `.`, and leave the build command empty.
4. Before deployment, edit `TASKFLOW_API_URL` in `frontend/config.js` to `https://YOUR-RAILWAY-DOMAIN`.
5. In Railway, include the final Vercel domain in `FRONTEND_ORIGINS` and redeploy/restart the API.
6. Open the Vercel URL, register a test account, create a task, and verify it remains after refresh.

The repository includes a GitHub Actions workflow at `.github/workflows/tests.yml` that runs against PostgreSQL and Chromium, Firefox, and WebKit. GitHub requires an additional `workflow` authorization scope to push workflow files. If GitHub blocks that permission, the project can still be pushed without this one file; add it from a GitHub-authorized session later to enable CI.

## Local verification

The local command `python -m pytest --alluredir=allure-results -q` passed **12 tests**: 7 API/database tests, 2 Selenium browser tests, and 3 Playwright Chromium tests. A separate Playwright run passed Chromium and Firefox flows; WebKit was skipped because this Windows host is missing its required libraries. Local runs use SQLite. PostgreSQL-backed CI and Vercel/Railway deployment still need to run with your GitHub and hosting accounts; they are not claimed as deployed or verified.
