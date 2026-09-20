# API Reference (summary)

Interactive OpenAPI docs: run the API and open `http://127.0.0.1:8000/docs`.

## Conventions

- All routes except `/health` and `/auth/login` require `Authorization: Bearer <token>`.
- Errors: `401` missing/invalid token · `403` role or ownership denied · `404` missing record · `422` validation failure · `503` database unavailable. Details come in `{"detail": "..."}`.
- Token validation re-loads the user row on every request: a deactivated account gets `401 Account is deactivated` even with a still-valid token.
- List endpoints accept `page` (≥1) and `page_size` (1–100) and return a `{items, page, page_size, total, total_pages}` envelope. Request bodies are typed Pydantic models (see `/docs`).
- Teachers receive 403 on any admin-only route or course they do not teach; this is enforced in services, so it holds for every client.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness; reports database reachability |
| POST | `/auth/login` | Get JWT (`{username, password}` → `{access_token, role}`) |
| GET | `/students?search=&page=&page_size=` | List/search students, paginated (admin) |
| POST/PUT/DELETE | `/students[/{id}]` | Create / update / delete student (admin) |
| GET | `/students/{id}/profile` | Student info + courses + average grade |
| GET | `/students/export` | CSV export of all students (admin) |
| POST | `/students/import` | Bulk CSV import (admin): all-or-nothing; 422 with per-row errors if any row fails |
| GET | `/students/{id}/enrollments` | Enrollments with grades |
| GET | `/students/{id}/available-courses` | Courses the student is not yet enrolled in (admin) |
| POST | `/students/{id}/enrollments` | Enroll into a course (admin; duplicates rejected) |
| GET/POST/PUT/DELETE | `/teachers[/{id}]` | Teacher CRUD (admin) |
| GET/POST/PUT/DELETE | `/courses[/{id}]` | Course CRUD (writes admin) |
| GET | `/courses/{id}/students` | Roster (teacher: own courses only) |
| GET | `/courses/{id}/analytics` | Enrollment count, avg/high/low grade |
| PUT | `/enrollments/{id}/grade` | Set/update grade (teacher: own courses only) |
| GET | `/dashboard/summary` | Totals (teacher: scoped to their courses) |
| GET | `/dashboard/grade-distribution` | Grade bands A–F |
| GET | `/dashboard/recent-enrollments` | Latest enrollments |
| GET | `/users` · POST `/users` | List/create users (admin) |
| PUT | `/users/{id}/active` | Activate/deactivate (admin); deactivation revokes live tokens |
| GET | `/audit-logs?action=&entity_type=&username=&page=` | Audit trail (admin), filterable + paginated |

## Example session

```bash
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}'
# → {"access_token":"eyJ...","token_type":"bearer","role":"ADMIN"}

curl http://127.0.0.1:8000/dashboard/summary -H "Authorization: Bearer $TOKEN"
```
