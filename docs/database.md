# Database

Schema lives in `database/schema.sql`; demo data in `seed_data.sql`; reporting examples in `queries.sql`.

## Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `students` | Student records | `student_code` UNIQUE, required name/email, valid email format |
| `teachers` | Teacher records | Required names, unique identifier |
| `courses` | Course catalog | `course_code` UNIQUE, credits 1–6, optional teacher FK |
| `enrollments` | **Many-to-many** students ↔ courses | UNIQUE (`student_id`, `course_id`) prevents duplicates; FKs cascade on student/course delete |
| `grades` | One grade per enrollment | `enrollment_id` UNIQUE + FK; grade range enforced by services and CHECK |
| `users` | Login accounts | `username` UNIQUE; `password_hash` (bcrypt only); `role` ADMIN/TEACHER; `is_active` flag; optional `teacher_id` link |
| `audit_logs` | Append-only change/login trail | FK to `users` (SET NULL on delete); indexed on `user_id`, `action`, `(entity_type, entity_id)`, `created_at`; no UPDATE/DELETE by design |

## Design decisions

- **`enrollments` as associative entity** with a composite unique constraint — duplicates are impossible at the database level, not just in app code.
- **`grades` 1-to-0..1 with `enrollments`** via unique FK — the current grade is a property of the enrollment; grade history would be a deliberate schema change.
- **Cascade rules:** deleting a student or course removes dependent enrollments/grades (child data has no meaning alone); deleting a teacher nulls `courses.teacher_id` (courses survive).
- **Indexes** on every foreign key plus searched columns (`student_code`, `course_code`, usernames); the schema avoids indexing columns that are never filtered.
- **`users.role`** is an ENUM of `ADMIN`/`TEACHER`; authorization reads it in services.
- **`audit_logs`** rows are written on the *same connection/transaction* as the operation they describe, so an audit entry can never exist without its change (and vice versa). Never stores passwords or tokens.

## Migrations

`database/migrations/` contains the one-time upgrade script for pre-auth installs. New installs just run `schema.sql` + `seed_data.sql` (or use Docker, which applies `docker-init/` automatically).

## Testing

Integration tests load the schema into a dedicated `student_management_test` database (`TEST_DB_*` variables), exercise repositories/services against real MySQL, and drop it afterwards. They never touch a developer's configured database.
