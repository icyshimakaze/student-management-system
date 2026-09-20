# Interview Notes

Concise answers grounded in what this repository actually does. If a topic
is not here, the project does not implement it — don't claim it does.

1. **Why React for the web frontend?** Small learning surface, component model fits CRUD pages, Vite gives fast builds. Plain JavaScript + hand-written CSS keeps the dependency list to React, React Router and the dev toolchain — every line is explainable.

2. **Why FastAPI?** Thin HTTP layer over existing services; automatic OpenAPI docs; native async; Pydantic-backed request parsing. The API file contains zero business rules — it maps requests to service calls and domain errors to status codes.

3. **Why MySQL?** The domain is strongly relational (students ↔ courses many-to-many, enrollment-scoped grades). MySQL gives FKs, unique constraints, cascades, transactions and window functions that map directly onto those relationships.

4. **Why services + repositories?** Repositories isolate SQL so no other layer writes queries; services concentrate validation and authorization so **every client** (desktop, web, HTTP) gets identical rules. This kills the classic "UI hides the button so it's safe" fallacy — permissions live below the UI.

5. **How does authentication work?** `AuthService.authenticate()` looks up the user, rejects inactive accounts, verifies bcrypt hashes, and returns a domain `Session`. Generic failure message — no username enumeration.

6. **How does JWT work here?** After login the API signs `{sub, username, role, teacher_id, exp}` (HS256, 120-min TTL). Each request's Bearer token is decoded and rebuilt into the domain `Session`; expired/garbage tokens get 401. The token is stateless — no server-side session store.

7. **How are passwords stored?** `bcrypt.hashpw` with generated salts; only the hash is stored (`users.password_hash`). Verification via `bcrypt.checkpw`. Passwords and hashes are never logged.

8. **How do frontend and backend communicate?** The web app calls JSON REST endpoints with `Authorization: Bearer <token>`. The API URL is build-time config (`VITE_API_URL`); 401s trigger a global session-expired handler that redirects to login.

9. **How do CRUD operations flow?** UI → service (validate + authorize) → repository (parameterized SQL) → MySQL. Example: student delete cascades enrollments/grades via FK rules.

10. **How is the many-to-many modeled?** `enrollments` is the associative table with UNIQUE(student_id, course_id). Grades hang off enrollments (unique FK), so an enrollment has at most one current grade.

11. **How are transactions handled?** Repositories run connection-scoped transactions with commit/rollback. A test deliberately fails a multi-step write and asserts nothing partial persisted.

12. **How does validation work?** `validation.py` has shared helpers (required, name, email, identifier, numeric ranges). Services call them; the desktop dialogs reuse the same helpers for immediate feedback; the API surfaces failures as 422 with the message.

13. **How are errors handled?** Domain errors (ValidationError/PermissionDenied/NotFoundError) map to 422/403/404; unexpected exceptions become generic 500s with details logged server-side. Desktop shows human-readable dialogs; tracebacks go to the log file.

14. **Desktop vs web app?** Desktop imports services in-process (no HTTP, config via `.env`); the web app crosses the API with JWTs. Same rules both ways — that symmetry is the architecture's core claim.

15. **How is the EXE built?** PyInstaller spec bundles the app + `resources/app.qss`; resource paths resolve via `sys._MEIPASS` in frozen mode; logs go to `%LOCALAPPDATA%`. One-folder mode for fast startup and fewer antivirus false positives. CI builds it on a Windows runner every push.

16. **How do environment variables work?** `config.py`/`api.py` read `DB_*`, `API_JWT_SECRET`, `CORS_ORIGINS` via python-dotenv; `.env` is git-ignored, `.env.example` documents every variable. No credential ever appears in source or logs.

17. **How is the project tested?** pytest: unit (validation, auth matrix, service delegation), API (FastAPI TestClient: login, 401s, error mapping), integration (real MySQL in a dedicated test database: CRUD, constraints, rollback, RBAC, analytics). Plus ruff lint and compileall in CI.

18. **How does CI work?** `ci.yml`: Python 3.12 → install → compileall → ruff → unit tests; then integration tests against a MySQL 8 service container; plus a Node job building the frontend. `windows-build.yml`: PyInstaller on windows-latest, exe uploaded as artifact.

19. **How could this be deployed?** Frontend static (Vercel/Netlify) with `VITE_API_URL`; API on Render/Railway with `CORS_ORIGINS` set; managed MySQL; `/health` as probe. Documented in `docs/deployment.md`.

20. **Known limitations?** No pagination or rate limiting; single-node; grade history not modeled (current grade only); integration tests need a live MySQL (skip otherwise). Stating these is a strength, not a weakness.

**Best war story:** integration tests caught a real bug unit tests missed — `CourseService.students()` was shadowed by a `self.students` repository attribute, silently breaking course rosters. Fakes couldn't catch it because they replace the attributes involved; only exercising the real class hierarchy did. That's why both test layers exist here.
