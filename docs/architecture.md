# Architecture

## Layers

```
UI (PyQt6 tabs/dialogs  |  React pages)
        │
Services (services.py)      ← validation, authorization, workflows, transactions
        │
Repositories (repositories.py) ← every SQL statement
        │
MySQL
```

- **UI** renders data and forwards user intent. It contains no SQL and no business rules. The desktop app imports services directly; the web app makes HTTP calls.
- **Services** own the rules: input validation (via `validation.py`), authorization (role + course-ownership checks), and multi-step workflows (e.g. enrollment creation inside a transaction).
- **Repositories** own SQL. All user-controlled values are passed as parameters; no string-built SQL exists anywhere.
- **db.py/config.py** own connection lifecycle and environment configuration.

## Why a shared service core matters

`api.py` is deliberately thin: it maps HTTP requests to service calls and domain errors to status codes (422 validation, 403 permission, 404 not found, 503 database). There is no second implementation of any business rule — the same `StudentService.create()` protects the desktop form, the React form, and any HTTP client. This is the main structural argument of the project: **authorization cannot be bypassed through an alternate client**.

## Cross-cutting

- **Sessions:** the domain `Session` object (user_id, username, role, teacher_id) is created by `AuthService`. The API embeds it in a JWT; the desktop app holds it in memory.
- **Transactions:** repositories expose connection-scoped transactions; the rollback test (`tests/test_integration.py::test_rollback_on_failure_leaves_no_partial_data`) proves partial writes never persist.
- **Logging:** application events go to a rotating file (desktop: `%LOCALAPPDATA%\StudentManagementSystem\` when frozen); credentials and hashes are never logged.
- **Error policy:** users see human-readable messages; stack traces go to logs only.
