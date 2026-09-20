"""Small FastAPI layer exposing the existing service layer over HTTP.

The API is intentionally thin: it reuses AuthService + ServiceBundle so the
same validation and authorization rules protect both the PyQt6 UI and HTTP
clients. Sessions are stateless JWTs; passwords never appear in logs.

Run locally (after `pip install -r requirements-api.txt`):

    uvicorn api:app --reload

Interactive docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import mysql.connector
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from db import DatabaseConnection
from schemas import (
    CourseCreate,
    CourseUpdate,
    CsvImportResult,
    EnrollmentCreate,
    GradeUpdate,
    LoginRequest,
    StudentCreate,
    StudentUpdate,
    TeacherCreate,
    TeacherUpdate,
    TokenResponse,
    UserActiveUpdate,
    UserCreate,
)
from services import (
    AuthService,
    NotFoundError,
    PermissionDenied,
    ServiceBundle,
    ValidationError,
)
from services import (
    Session as DomainSession,
)

LOGGER = logging.getLogger(__name__)

SECRET_KEY = os.getenv("API_JWT_SECRET", "")
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = int(os.getenv("API_TOKEN_TTL_MINUTES", "120"))
if not SECRET_KEY:
    raise RuntimeError(
        "API_JWT_SECRET is not set. Provide a long random value in .env before starting the API."
    )

app = FastAPI(
    title="Student Management System API",
    description="Thin HTTP layer over the same services that back the PyQt6 desktop UI.",
    version="1.0.0",
)
bearer = HTTPBearer(auto_error=False)

# The React dev server (Vite: 5173/4173, or any other local port) is always
# allowed for local work via a localhost-only regex. Additional production
# origins (e.g. a deployed frontend URL) come from CORS_ORIGINS, comma-
# separated — set it in the environment or .env; never commit it.
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
CORS_ORIGINS += [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model of record: a domain Session plus the request-scoped services.
def _domain_session(payload: dict) -> DomainSession:
    return DomainSession(
        user_id=int(payload["sub"]),
        username=payload["username"],
        role=payload["role"],
        teacher_id=payload.get("teacher_id"),
    )


def current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> tuple[DomainSession, ServiceBundle]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    session = _domain_session(payload)
    # Revalidate account state on EVERY request so a deactivated account's
    # existing token stops working immediately (revocation without a denylist).
    services = ServiceBundle(DatabaseConnection(), session)
    try:
        user = services.users._raw_get(session.user_id)
    except mysql.connector.Error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")
    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
    if user["role"] != session.role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account role changed; sign in again")
    return session, services


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, ValidationError):
        return HTTPException(422, str(error))
    if isinstance(error, PermissionDenied):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(error))
    if isinstance(error, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(error))
    if isinstance(error, mysql.connector.Error):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    # Unexpected: log the full traceback server-side, but never leak it to the client.
    LOGGER.exception("Unhandled API error", exc_info=error)
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> dict[str, Any]:
    try:
        session = AuthService(DatabaseConnection()).authenticate(body.username, body.password)
    except ValidationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error))
    except mysql.connector.Error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    token = jwt.encode(
        {
            "sub": str(session.user_id),
            "username": session.username,
            "role": session.role,
            "teacher_id": session.teacher_id,
            "exp": datetime.now(UTC) + timedelta(minutes=TOKEN_TTL_MINUTES),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer", "role": session.role}


# --------------------------------------------------------------------- health

@app.get("/health", tags=["health"])
def health():
    """Liveness probe. Reports whether the API can reach MySQL."""
    try:
        connection = DatabaseConnection().connect()
        connection.close()
        return {"status": "ok", "database": "ok"}
    except mysql.connector.Error:
        return {"status": "ok", "database": "unreachable"}


# ------------------------------------------------------------------ students

@app.get("/students")
def list_students(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(current_session),
):
    session, services = ctx
    try:
        return services.students.list(search, page, page_size)
    except Exception as error:
        raise _http_error(error)


@app.get("/students/export")
def export_students(ctx=Depends(current_session)):
    """CSV export of all students (admin only, enforced by the service)."""
    import csv
    import io

    session, services = ctx
    try:
        rows = services.students.all()
    except Exception as error:
        raise _http_error(error)

    def _safe_cell(value: Any) -> Any:
        """Neutralize spreadsheet formula injection: a cell starting with =,+,-,@
        would execute as a formula when the CSV is opened in Excel/LibreOffice."""
        if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
            return "'" + value
        return value

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["student_code", "first_name", "last_name", "email", "enrollment_date"])
    for row in rows:
        writer.writerow([
            _safe_cell(row["student_code"]),
            _safe_cell(row["first_name"]),
            _safe_cell(row["last_name"]),
            _safe_cell(row["email"]),
            row["enrollment_date"],
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"},
    )


@app.post("/students/import", response_model=CsvImportResult)
def import_students(body: dict[str, list[dict[str, str]]], ctx=Depends(current_session)):
    """Bulk CSV import. Validates every row; if any row fails, nothing is
    inserted and the response lists each failing row with its reason."""
    session, services = ctx
    try:
        result = services.students.import_csv(body.get("rows", []))
        if result["errors"]:
            raise HTTPException(422, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as error:
        raise _http_error(error)


@app.get("/students/{student_id}")
def get_student(student_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.students.get(student_id)
    except Exception as error:
        raise _http_error(error)


@app.post("/students", status_code=201)
def create_student(body: StudentCreate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        student_id = services.students.create(body.model_dump())
        return {"student_id": student_id}
    except Exception as error:
        raise _http_error(error)


@app.put("/students/{student_id}")
def update_student(student_id: int, body: StudentUpdate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.students.update(student_id, body.model_dump())
        return {"updated": True}
    except Exception as error:
        raise _http_error(error)


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.students.delete(student_id)
    except Exception as error:
        raise _http_error(error)


@app.get("/students/{student_id}/profile")
def student_profile(student_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.students.profile(student_id)
    except Exception as error:
        raise _http_error(error)


# ------------------------------------------------------------------ teachers

@app.get("/teachers")
def list_teachers(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(current_session),
):
    session, services = ctx
    try:
        return services.teachers.list(search, page, page_size)
    except Exception as error:
        raise _http_error(error)


@app.post("/teachers", status_code=201)
def create_teacher(body: TeacherCreate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return {"teacher_id": services.teachers.create(body.model_dump())}
    except Exception as error:
        raise _http_error(error)


@app.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, body: TeacherUpdate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.teachers.update(teacher_id, body.model_dump())
        return {"updated": True}
    except Exception as error:
        raise _http_error(error)


@app.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.teachers.delete(teacher_id)
    except Exception as error:
        raise _http_error(error)


# ------------------------------------------------------------------- courses

@app.get("/courses")
def list_courses(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(current_session),
):
    session, services = ctx
    try:
        return services.courses.list(search, page, page_size)
    except Exception as error:
        raise _http_error(error)


@app.post("/courses", status_code=201)
def create_course(body: CourseCreate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return {"course_id": services.courses.create(body.model_dump())}
    except Exception as error:
        raise _http_error(error)


@app.put("/courses/{course_id}")
def update_course(course_id: int, body: CourseUpdate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.courses.update(course_id, body.model_dump())
        return {"updated": True}
    except Exception as error:
        raise _http_error(error)


@app.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.courses.delete(course_id)
    except Exception as error:
        raise _http_error(error)


@app.get("/courses/{course_id}/analytics")
def course_analytics(course_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.courses.analytics(course_id)
    except Exception as error:
        raise _http_error(error)


@app.get("/courses/{course_id}/students")
def course_students(course_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.courses.enrolled_students(course_id)
    except Exception as error:
        raise _http_error(error)


# ---------------------------------------------------------------- enrollments

@app.get("/students/{student_id}/enrollments")
def student_enrollments(student_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.enrollments.list_for_student(student_id)
    except Exception as error:
        raise _http_error(error)


@app.get("/students/{student_id}/available-courses")
def student_available_courses(student_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return [
            {"course_id": course_id, "course_name": name}
            for course_id, name in services.enrollments.available_courses(student_id)
        ]
    except Exception as error:
        raise _http_error(error)


@app.post("/students/{student_id}/enrollments", status_code=201)
def enroll_student(student_id: int, body: EnrollmentCreate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        enrollment_id = services.enrollments.create(
            student_id, body.course_id, body.enrollment_date
        )
        return {"enrollment_id": enrollment_id}
    except Exception as error:
        raise _http_error(error)


@app.delete("/enrollments/{enrollment_id}", status_code=204)
def delete_enrollment(enrollment_id: int, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.enrollments.delete(enrollment_id)
    except Exception as error:
        raise _http_error(error)


# --------------------------------------------------------------------- grades

@app.put("/enrollments/{enrollment_id}/grade")
def set_grade(enrollment_id: int, body: GradeUpdate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        grade_id = services.grades.set_grade(
            enrollment_id, body.grade_value, body.graded_date
        )
        return {"grade_id": grade_id}
    except Exception as error:
        raise _http_error(error)


# ------------------------------------------------------------------ dashboard

@app.get("/dashboard/summary")
def dashboard_summary(ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.dashboard.summary()
    except Exception as error:
        raise _http_error(error)


@app.get("/dashboard/grade-distribution")
def grade_distribution(ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.dashboard.grade_distribution()
    except Exception as error:
        raise _http_error(error)


@app.get("/dashboard/recent-enrollments")
def recent_enrollments(ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.dashboard.recent_enrollments()
    except Exception as error:
        raise _http_error(error)


# ---------------------------------------------------------------------- users

@app.get("/users")
def list_users(ctx=Depends(current_session)):
    session, services = ctx
    try:
        return services.users.list()
    except Exception as error:
        raise _http_error(error)


@app.post("/users", status_code=201)
def create_user(body: UserCreate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        return {
            "user_id": services.users.create(
                body.username,
                body.password,
                body.role,
                body.teacher_id,
            )
        }
    except Exception as error:
        raise _http_error(error)


@app.put("/users/{user_id}/active")
def set_user_active(user_id: int, body: UserActiveUpdate, ctx=Depends(current_session)):
    session, services = ctx
    try:
        services.users.set_active(user_id, body.is_active)
        return {"updated": True}
    except Exception as error:
        raise _http_error(error)


# ----------------------------------------------------------------- audit logs

@app.get("/audit-logs")
def list_audit_logs(
    action: str = "",
    entity_type: str = "",
    username: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(current_session),
):
    """Admin-only audit trail with filtering and pagination."""
    session, services = ctx
    try:
        return services.audit_logs.list(
            action=action, entity_type=entity_type, username=username, status=status,
            page=page, page_size=page_size,
        )
    except Exception as error:
        raise _http_error(error)
