# Design Notes — Student Management System

A short, honest explanation of *why* the project is built the way it is, for
interviews, viva, or your own reference. Everything here matches the code.

---

## 1. Architecture: UI → Services → Repositories → MySQL

```
PyQt6 UI (main.py, tabs.py, dialogs.py)
        │  calls only
        ▼
Services (services.py)      validation · authorization · workflows
        │  owns all SQL
        ▼
Repositories (repositories.py)
        │
        ▼
MySQL (db.py + config.py, env-based credentials)
```

**Why four layers instead of two?**

- *Testability* — services and repositories are tested without a GUI, using
  fakes (unit) and a real MySQL test database (integration).
- *Security* — authorization must not depend on which buttons the UI chose to
  show. `GradeService.set_grade` checks course ownership itself; a hidden
  button is not a security control.
- *Reuse* — `api.py` (FastAPI) reuses the identical service layer, proving the
  UI is just one client of the business logic.
- *Change isolation* — a query rewrite touches one repository; a new rule
  touches one service; the UI never notices.

**Rule enforced in review:** no `cursor.execute` in UI files. UI classes only
call services and render results.

---

## 2. Database design

Six tables. Entities first, then the relationships:

| Table | Purpose | Key decisions |
|---|---|---|
| `teachers` | staff records | `email UNIQUE`; name index for sorting |
| `students` | student records | `student_code UNIQUE`, `email UNIQUE` |
| `courses` | course catalog | `course_code UNIQUE`; FK → teachers |
| `enrollments` | **junction table** for students ↔ courses | `UNIQUE(student_id, course_id)` |
| `grades` | one current grade per enrollment | `enrollment_id UNIQUE`, CHECK 0–100 |
| `users` | login accounts | `password_hash`, role ENUM, nullable `teacher_id` |

### Normalization (3NF)

- Every non-key column depends on its table's key — e.g. teacher name lives
  only in `teachers`, so renaming a teacher is a single-row update.
- `enrollment_date` lives in `enrollments` (a fact about the *relationship*),
  not in `students` or `courses`. Grade facts live in `grades`, keyed by
  enrollment — a student's grade is meaningless without the course it was for.
- No repeating groups: a student taking five courses is five enrollment rows,
  not five columns.

### The many-to-many relationship

Students and courses are many-to-many. A direct FK is impossible in 1NF/2NF,
so `enrollments` decomposes it into two one-to-many relationships and carries
its own attribute (`enrollment_date`). The composite `UNIQUE(student_id,
course_id)` constraint enforces "a student can enroll in a course once" at the
database level — the service also checks, but the constraint is the last line
of defense against race conditions.

### Referential integrity and delete behavior

- Student deleted → enrollments `CASCADE` → their grades `CASCADE`.
  (Keeping orphan grades would be meaningless.)
- Course deleted → enrollments `CASCADE`, same reasoning.
- Teacher deleted → courses get `teacher_id = NULL` (`ON DELETE SET NULL`):
  the course still exists, it's just unassigned. Cascading would destroy the
  catalog, which is the wrong business outcome.
- `grades.enrollment_id` is `UNIQUE` — one current grade per enrollment. The
  upsert (`INSERT ... ON DUPLICATE KEY UPDATE`) relies on this constraint.

### Indexes (deliberate, not blanket)

| Index | Serves |
|---|---|
| `students(last_name, first_name)` | default sort + name search |
| `teachers(last_name, first_name)` | same |
| `enrollments(student_id)` | student profile / enrollment lists |
| `enrollments(course_id)` | course rosters; also backs the UNIQUE constraint lookups |
| `courses(teacher_id)` | teacher-scoped course listing (every teacher request filters on this) |

`student_code`, `course_code`, and emails get free unique indexes. No index on
`enrollment_date`: the table is small and the recent-enrollments query scans
few rows anyway — indexing it would slow writes for no measurable gain.
*Index decision rule: index what the WHERE/JOIN/ORDER BY actually does at
expected data volumes.*

### Views

`database/queries.sql` defines two reporting views:

- `student_performance` — courses taken + average grade per student
- `course_statistics` — enrollment count, average/highest/lowest grade per course

Views centralize reporting SQL so the app and ad-hoc analysis share one
definition instead of three drifting copies.

---

## 3. Transactions

`BaseRepository.transaction()` opens a connection with `autocommit=False`,
yields it, and commits on success / rolls back on any exception. Covered by
unit tests (fake connection) and an integration test that inserts an
enrollment then raises, asserting the row is gone after rollback.

Single-statement writes are atomic by themselves, so they use the plain
`execute()` path; the transaction helper exists for multi-statement workflows.

---

## 4. Authentication

- Passwords stored only as bcrypt hashes (`bcrypt.gensalt()` per user).
- `AuthService.authenticate` does the same generic rejection for
  unknown-user, wrong-password, and inactive-account — the response never
  reveals which one failed (prevents username enumeration).
- First user is created interactively by `scripts/create_user.py` (getpass, no
  password in argv, shell history, or source). No default admin password ships
  with the project.
- The REST API issues short-lived JWTs (HS256) from the same
  `AuthService`; the secret comes from `API_JWT_SECRET` and the app refuses to
  start without it.

## 5. Authorization

Two roles, checked **in services**:

| Operation | ADMIN | TEACHER |
|---|---|---|
| Manage students/teachers/courses/users | ✔ | ✗ (`require_admin` raises) |
| Enroll / unenroll students | ✔ | ✗ |
| View courses | all | only `teacher_id = own` (repo-level filter) |
| Read/enter grades | any course | only own courses (ownership check on the enrollment's course) |

The ownership check is the interesting part: `GradeService.set_grade` fetches
the enrollment *with its course's teacher_id* and compares it to the session's
teacher profile before writing. `admin_session` bypasses only the ownership
check, never validation.

## 6. Validation

One module (`validation.py`), used by services (authoritative) and dialogs
(early UX feedback only). Rules: identifier format, name charset, email
format, credits 1–6, grade 0–100. Services validate again regardless of what
the UI checked — API clients skip the GUI entirely, so the service is the
boundary that matters.

## 7. Error handling

MySQL error numbers are mapped to human messages where safe
(1062 duplicate → "already exists", 1451/1452 FK → "still referenced");
everything else is logged with a traceback and shown to the user as a generic
message. Raw errors and SQL never reach the UI; secrets never reach the log.

## 8. API layer

`api.py` is deliberately thin (~20 endpoints, no business logic): JWT login,
then the same services the desktop app uses. Domain exceptions map to HTTP
codes — ValidationError→422, PermissionDenied→403, NotFoundError→404,
db errors→503. Tests (`tests/test_api.py`) verify the mapping without a
database.

## 9. Testing strategy

| Suite | Needs MySQL? | What it proves |
|---|---|---|
| `test_validation.py` | no | input rules |
| `test_services.py` | no | auth logic, permission checks, service→repo delegation (fakes) |
| `test_repositories.py` | no | commit/rollback semantics (fake connection) |
| `test_api.py` | no | HTTP mapping, JWT handling |
| `test_integration.py` | yes (`TEST_DB_*`) | the above against a real MySQL: constraints, cascade, rollback, scoped dashboards |

Integration tests **skip** when no MySQL is configured, so the suite is green
everywhere; CI runs them against a real MySQL 8.0 service container. They only
ever create/drop `student_management_test`.

## 10. Known limitations (honest list)

- Desktop-first; the API is read/write but has no pagination or rate limiting.
- One migration script (not a migration framework) — fine at this scale.
- No audit log of admin changes.
- UI tests are manual; automated GUI testing was out of scope.
