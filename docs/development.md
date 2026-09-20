# Development Guide

## Layout quick reference

| File | Responsibility |
|---|---|
| `main.py` | Desktop entry point, login dialog, main window |
| `tabs.py` / `dialogs.py` | Desktop UI widgets (no SQL, no rules) |
| `services.py` | All business rules, authorization, workflows |
| `repositories.py` | All SQL |
| `validation.py` | Shared validation helpers |
| `db.py` / `config.py` | Connections, env config |
| `api.py` | HTTP layer mapping to services |
| `sms-web/` | React frontend |

## Conventions

- New SQL goes in a repository, never in services/UI/API.
- New rules go in a service with a test; UI/API just call it.
- Parameterized queries only — no f-string SQL, ever.
- Ruff must stay clean (`python -m ruff check .`); config in `pyproject.toml`.
- Compact one-line statements are tolerated in existing desktop code; prefer
  normal formatting in new files.

## Test strategy

- `tests/test_validation.py`, `test_services.py`, `test_repositories.py` — no database needed
- `tests/test_api.py` — FastAPI TestClient, no database
- `tests/test_integration.py` — real MySQL via `TEST_DB_*` (skips if unreachable; uses only `student_management_test`)

Run everything: `python -m pytest -q`

## Adding an API endpoint

1. Add/extend the service method with validation + authorization.
2. Add the route in `api.py`; wrap errors with `_http_error`.
3. Add a test in `tests/test_api.py` (and an integration test if the service hits MySQL).

## Frontend

```bash
cd sms-web
npm install
npm run dev      # dev server on :5173, proxies nothing — calls VITE_API_URL
npm run build && npm run lint
```

Backend must be running (`uvicorn api:app --reload`) with CORS already
covering `localhost:5173` (it does by default).
