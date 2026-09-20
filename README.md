# Student Management System

A student administration platform built three ways over one shared business-logic core: a **PyQt6 desktop application**, a **React web application**, and a **FastAPI REST API** — all backed by **MySQL**. It manages students, teachers, courses, enrollments, grades and authenticated users through a layered architecture (UI → services → repositories → database) that keeps authorization and validation out of the UI and in one enforceable place.

## Features

- Authentication with bcrypt-hashed passwords, active/inactive accounts, JWT sessions on the API
- JWT validation re-checks account state on every request: deactivating a user revokes their existing token immediately
- Role-based access control: `ADMIN` manages everything; `TEACHER` sees and grades only assigned courses — enforced in service logic, not by hiding buttons
- Student, teacher and course CRUD with database-side search/filtering and server-side pagination (page/page_size/total metadata, capped at 100 per page)
- Enrollment with duplicate prevention; grade entry with range/format validation
- Student profiles (course history + average grade) and course analytics (count, avg/high/low, distribution)
- Database-driven dashboard: totals, recent enrollments, grade distribution (teacher dashboard is scoped to their data)
- User management: creation (with optional teacher linkage) and activation/deactivation
- Audit trail: administrative changes and logins are recorded transactionally in `audit_logs`, viewable in an admin-only screen with filtering and pagination
- CSV bulk import (all-or-nothing with per-row validation errors) and CSV export for students
- Windows executable packaging (PyInstaller) and a GitHub Actions workflow that builds it on every push to `main`

## Architecture

```text
  PyQt6 Desktop App          React Web App (sms-web/)
          │                          │
          │ (imports services        │ (HTTP + JWT)
          │  directly)               │
          │                          ▼
          │                   FastAPI (api.py)
          │                          │
          ▼                          ▼
          Services / Business Rules (validation, authorization, transactions)
                         │
                         ▼
                  Repositories / DAO (all SQL)
                         │
                         ▼
                       MySQL
```

The desktop app calls the service layer in-process; the web app goes through the FastAPI layer, which wraps the *same* services. Every authorization rule therefore holds no matter which client is used.

## Technology Stack

| Area | Technologies |
|---|---|
| Desktop | Python 3.12, PyQt6 |
| Web frontend | React 19, Vite, React Router (plain JS, no CSS framework) |
| API | FastAPI, Pydantic request/response schemas, uvicorn, python-jose (JWT) |
| Database | MySQL 8.0, mysql-connector-python |
| Security | bcrypt, parameterized SQL, env-based configuration |
| Testing | pytest (unit + API + integration), Vitest + Testing Library (frontend), ruff |
| DevOps | GitHub Actions (CI + Windows EXE build), Docker Compose |

## Project Structure

```text
student-management-system/
├── main.py                  # PyQt6 desktop entry point
├── api.py                   # FastAPI layer over the same services
├── services.py              # business rules, validation, authorization
├── repositories.py          # all SQL
├── db.py / config.py        # connections and env configuration
├── validation.py            # shared validation helpers
├── tabs.py / dialogs.py     # desktop UI
├── resources/app.qss        # desktop stylesheet
├── sms-web/                 # React web application
├── database/                # schema.sql, seed_data.sql, queries.sql, migrations/
├── docker-init/             # SQL auto-applied by the MySQL container on first run
├── tests/                   # unit + API + integration suites
├── scripts/                 # create_user.py, build_windows.ps1
├── docs/                    # architecture, api, database, deployment, interview notes
├── StudentManagementSystem.spec  # PyInstaller build definition
├── BUILD_WINDOWS.md         # how to build the .exe
├── .github/workflows/       # ci.yml, windows-build.yml
└── .env.example
```

## Prerequisites

- Python 3.11 or 3.12
- Node.js 20+ (web app only)
- MySQL 8.0 locally or via Docker

## Local Setup

### 1. Database (Docker Compose — recommended)

```powershell
docker compose up -d
```

Starts MySQL 8.0 on host port **3777** with schema and seed data applied automatically on first run. Credentials come from the environment with documented dev-only defaults (`sms_dev_password`) — see `docker-compose.yml`.

> **Windows note (one-time fix, already applied on the dev machine):** after a reboot, Hyper-V/WinNAT reserves blocks of ports at random, which can make `docker compose up` fail with `ports are not available`. The permanent fix is to persistently reserve your chosen port **as Administrator** (once only):
>
> ```powershell
> net stop winnat
> netsh int ipv4 add excludedportrange protocol=tcp startport=3777 numberofports=1 store=persistent
> net start winnat
> ```
>
> WinNAT then skips that port when it carves out its boot-time ranges, and the Docker mapping survives every restart. A temporary alternative is to pick a port from `netsh int ipv4 show excludedportrange protocol=tcp` that is currently outside all listed ranges, update `DB_PORT` in `.env`, and re-run `docker compose up -d` — but the reservation is the lasting solution.

Then set in `.env`: `DB_PORT=3777`, `DB_PASSWORD=sms_dev_password`.

<details>
<summary>Using your own MySQL server instead</summary>

```powershell
mysql -u root -p < database/schema.sql
mysql -u root -p student_management < database/seed_data.sql
```

</details>

### 2. Python environment

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-api.txt   # only needed for the API
```

### 3. Environment variables

```powershell
Copy-Item .env.example .env
```

Fill in `DB_*` values. For the API, generate a JWT secret:

```powershell
python -c "import secrets; print(f'API_JWT_SECRET={secrets.token_urlsafe(48)}')"   # paste into .env
```

Never commit the real `.env` — it is git-ignored.

### 4. Login accounts

Seeding the demo data also creates two **demo-only** accounts so the app is usable immediately:

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | ADMIN |
| `demo_teacher` | `teach123` | TEACHER |

These exist for the demo dataset only — change or delete them before any real use. To create your own accounts instead (or in addition), run:

```powershell
python scripts/create_user.py
```

It prompts for username/password/role interactively; the password is never stored in source.

## Running

| Component | Command |
|---|---|
| Desktop app | `python main.py` |
| API | `uvicorn api:app --reload` → docs at `http://127.0.0.1:8000/docs` |
| Web app | `cd sms-web && npm install && npm run dev` → `http://localhost:5173` |
| Health check | `GET /health` — reports API + database status |

The web app reads the API URL from `VITE_API_URL` (build time); unset, it defaults to `http://127.0.0.1:8000` for development. See `sms-web/.env.example`.

## Testing

```powershell
python -m pytest -q          # unit + API + integration (integration skips without MySQL)
python -m compileall -q .    # syntax check
python -m ruff check .       # lint
cd sms-web && npm test && npm run build && npm run lint   # frontend tests, build, lint
```

Frontend tests (Vitest + Testing Library) cover login behavior, route protection, pagination rendering, search wiring and API error handling. Integration tests use the dedicated `student_management_test` database (configured via `TEST_DB_*` variables) and never touch a developer's real data. CI runs everything: unit tests, lint, frontend tests + build, and the integration suite against a MySQL 8.0 service container.

## Building the Windows EXE

```powershell
pyinstaller StudentManagementSystem.spec --noconfirm
# → dist\StudentManagementSystem\StudentManagementSystem.exe
```

Full instructions, troubleshooting and the one-step script are in [BUILD_WINDOWS.md](BUILD_WINDOWS.md). The exe reads `DB_*` configuration from the environment or a `.env` next to it — no secrets are bundled. GitHub Actions builds it automatically on pushes to `main` (artifact in the Actions tab).

## SQL Portfolio

`database/queries.sql` documents meaningful examples of joins, `GROUP BY`/`HAVING`, subqueries, correlated subqueries, `CASE`, `EXISTS`/`NOT EXISTS`, window functions (`RANK()`, running totals) and reporting views — each answering a real student-management question.

## Deployment

Realistic options are documented in [docs/deployment.md](docs/deployment.md) — frontend on a static host (Vercel/Netlify) with `VITE_API_URL` set at build time, API on a Python host (Render/Railway) with `CORS_ORIGINS` extended to the frontend origin, database managed or self-hosted. Nothing is claimed deployed here — the instructions are the deliverable.

## Security

- bcrypt password hashing; no plaintext or hash is ever logged
- JWT tokens with expiry; invalid/expired tokens rejected with 401
- All user-controlled SQL is parameterized; the repository layer owns every query
- Authorization enforced in services — verified by tests that bypass the UI and call services/API directly
- CORS is explicit (dev origins + `CORS_ORIGINS` config), credentials and origins never hard-coded
- Errors returned to clients are generic; details go to the server log

## Known Limitations

- Single-node design; no rate limiting on the API
- Desktop app targets Windows/Linux desktops only (PyQt6)
- Integration tests need a reachable MySQL; they skip otherwise

## Future Improvements

- Refresh-token flow for the web client (currently a single access token with server-side revocation)
- Automated GUI tests for the desktop app

## License

MIT — see [LICENSE](LICENSE).
