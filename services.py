"""Business services: authorization, validation and workflow coordination."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import bcrypt
import mysql.connector

from repositories import (
    AuditLogRepository,
    CourseRepository,
    DashboardRepository,
    EnrollmentRepository,
    GradeRepository,
    StudentRepository,
    TeacherRepository,
    UserRepository,
)
from validation import (
    ValidationError,
    credits,
    email,
    grade,
    identifier,
    name,
    required,
)

LOGGER = logging.getLogger(__name__)


class PermissionDenied(PermissionError):
    """Raised when the authenticated user lacks permission for an operation."""


class NotFoundError(LookupError):
    """Raised when a requested record no longer exists."""


def _friendly_db_error(error: mysql.connector.Error) -> ValidationError | None:
    errno = getattr(error, "errno", None)
    if errno == 1062:
        return ValidationError("A record with the same unique identifier already exists.")
    if errno in {1451, 1452}:
        return ValidationError("This record is still referenced by related data.")
    return None


@dataclass(frozen=True)
class Session:
    user_id: int
    username: str
    role: str
    teacher_id: int | None

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class BaseService:
    def __init__(self, db, session: Session):
        self.db = db
        self.session = session
        self.students = StudentRepository(db)
        self.teachers = TeacherRepository(db)
        self.courses = CourseRepository(db)
        self.enrollments = EnrollmentRepository(db)
        self.grades = GradeRepository(db)
        self.dashboard_repo = DashboardRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditLogRepository(db)

    def require_admin(self) -> None:
        if not self.session.is_admin:
            raise PermissionDenied("This action is available to administrators only.")

    @staticmethod
    def _page_args(page: int, page_size: int) -> tuple[int, int, int]:
        """Normalize pagination inputs into (page, page_size, offset)."""
        page = max(1, int(page))
        page_size = min(max(1, int(page_size)), MAX_PAGE_SIZE)
        return page, page_size, (page - 1) * page_size

    @staticmethod
    def _page_result(items: list[dict[str, Any]], page: int, page_size: int, total: int) -> dict[str, Any]:
        """Build the standard paginated envelope returned by all list endpoints."""
        import math

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, math.ceil(total / page_size)),
        }

    def require_teacher(self) -> int:
        if self.session.is_admin:
            raise PermissionDenied("This operation requires a teacher account.")
        if self.session.role != "TEACHER" or self.session.teacher_id is None:
            raise PermissionDenied("This account is not linked to a teacher profile.")
        return self.session.teacher_id

    def ensure_error(self, operation: str, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except mysql.connector.Error as error:
            mapped = _friendly_db_error(error)
            if mapped:
                raise mapped from error
            LOGGER.exception("Database failure during %s", operation)
            raise

    def _audit_with(self, connection, action: str, entity_type: str, entity_id: int | None, details: dict[str, Any] | None = None) -> None:
        """Record an audit row on the caller's open transaction so the event is
        atomic with the operation it describes."""
        if self.db is None:  # db=None only in lightweight unit tests
            return
        self.audit.record(
            connection,
            user_id=self.session.user_id,
            username=self.session.username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    def audited(self, action: str, entity_type: str, operation: str, func, *args, details=None, entity_id: int | None = None, **kwargs):
        """Run a mutating operation and record its audit trail.

        Success  -> SUCCESS row (with `details(entity_id)` when a callable is
                    passed, so the new record's id can be included).
        Failure  -> REJECTED row when the caller made a rule mistake
                    (ValidationError / PermissionDenied / NotFoundError),
                    FAILED row for anything else (database failure). The
                    rejection row is written best-effort on its own
                    transaction: if the database is down, there is nowhere
                    to write it anyway.
        """
        try:
            result = self.ensure_error(operation, func, *args, **kwargs)
        except (ValidationError, PermissionDenied, LookupError) as error:
            self._audit_standalone(action, entity_type, None, str(error), "REJECTED")
            raise
        except Exception as error:  # database failure -> FAILED, best-effort
            self._audit_standalone(action, entity_type, None, f"Database error: {error}", "FAILED")
            raise
        if entity_id is None:
            entity_id = result if isinstance(result, int) and result > 0 else None
        extra = details(entity_id) if callable(details) else details
        if self.db is not None:
            def _write(connection, cursor):
                self._audit_with(connection, action, entity_type, entity_id, extra)
                return result
            return self.ensure_error(f"{operation} audit", self._runner_for(entity_type), _write)
        return result

    def _runner_for(self, entity_type: str):
        """Pick a repository transaction runner for the audit write."""
        return self.students.run_in_transaction

    def _audit_standalone(self, action: str, entity_type: str, entity_id: int | None, detail: str, status: str) -> None:
        """Best-effort audit write outside the operation's transaction."""
        if self.db is None:
            return
        try:
            def _write(connection, cursor):
                self.audit.record(
                    connection,
                    user_id=self.session.user_id,
                    username=self.session.username,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    details={"reason": detail[:500]},
                    status=status,
                )
                return 0
            self.students.run_in_transaction(_write)
        except Exception:
            LOGGER.exception("Failed to write %s audit record", status)


class AuthService:
    def __init__(self, db, user_repo: UserRepository | None = None):
        self.db = db
        self.users = user_repo or UserRepository(db)
        self.audit = AuditLogRepository(db)

    def authenticate(self, username: str, password: str) -> Session:
        username = required(username, "Username")
        password = required(password, "Password")
        try:
            user = self.users.get_by_username(username)
        except mysql.connector.Error:
            LOGGER.exception("Authentication database failure")
            raise
        if not user or not user["is_active"] or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            LOGGER.warning("Unsuccessful login for username=%s", username)
            raise ValidationError("Invalid username or password, or the account is inactive.")
        LOGGER.info("Successful login for user_id=%s", user["id"])
        if self.db is not None:  # db=None only in lightweight unit tests
            self._audit_login(user["id"], user["username"])
        return Session(user["id"], user["username"], user["role"], user["teacher_id"])

    def _audit_login(self, user_id: int, username: str) -> None:
        """Best-effort login audit: a logging failure must not block sign-in."""
        try:
            connection = self.db.connect()
            try:
                self.audit.record(
                    connection, user_id=user_id, username=username,
                    action="user.login", entity_type="user", entity_id=user_id,
                )
                connection.commit()
            finally:
                connection.close()
        except mysql.connector.Error:
            LOGGER.exception("Failed to write login audit record")


class StudentService(BaseService):

    def list(self, search: str = "", page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        """Paginated listing. Returns {items, page, page_size, total, total_pages}."""
        self.require_admin()
        page, page_size, offset = self._page_args(page, page_size)
        items = self.ensure_error("student listing", self.students.list, search, page_size, offset)
        total = self.ensure_error("student count", self.students.count, search)
        return self._page_result(items, page, page_size, total)

    def all(self, search: str = "") -> list[dict[str, Any]]:
        """Unpaged listing used by CSV export only."""
        self.require_admin()
        return self.ensure_error("student export listing", self.students.list, search)

    def get(self, student_id: int) -> dict[str, Any]:
        self.require_admin()
        row = self.ensure_error("student lookup", self.students.get, student_id)
        if not row:
            raise NotFoundError("Student not found.")
        return row

    def _validate_student(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "student_code": identifier(data.get("student_code"), "Student ID"),
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "enrollment_date": required(data.get("enrollment_date"), "Enrollment date"),
        }

    def create(self, data: dict[str, Any]) -> int:
        self.require_admin()
        clean = self._validate_student(data)
        return self.audited("student.create", "student", "student creation", self.students.create, clean,
                            details=lambda new_id: {"student_code": clean["student_code"],
                                                    "name": f"{clean['first_name']} {clean['last_name']}", "student_id": new_id})

    def update(self, student_id: int, data: dict[str, Any]) -> int:
        self.require_admin()
        existing = self.get(student_id)
        clean = self._validate_student(data)
        return self.audited("student.update", "student", "student update", self.students.update, student_id, clean,
                            entity_id=student_id,
                            details={"student_code": clean["student_code"],
                                     "name": f"{clean['first_name']} {clean['last_name']}",
                                     "previous": {k: existing[k] for k in ("student_code", "first_name", "last_name", "email")}})

    def delete(self, student_id: int) -> int:
        self.require_admin()
        existing = self.get(student_id)
        removed = self.audited("student.delete", "student", "student deletion", self.students.delete, student_id,
                               entity_id=student_id,
                               details={"student_code": existing["student_code"],
                                        "name": f"{existing['first_name']} {existing['last_name']}"})
        return student_id

    def profile(self, student_id: int) -> dict[str, Any]:
        self.require_admin()
        return self.ensure_error("student profile", self.students.profile, student_id)

    def import_csv(self, rows: list[dict[str, str]]) -> dict[str, Any]:
        """Transactional bulk import. Validates every row first; if ANY row is
        invalid, nothing is inserted (atomic policy). Returns a summary of the
        validation so the caller can show the user exactly what went wrong."""
        self.require_admin()
        cleaned: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for index, raw in enumerate(rows, start=2):  # line 1 is the header
            try:
                cleaned.append(self._validate_student(raw))
            except ValidationError as error:
                errors.append({"row": index, "error": str(error), "student_code": raw.get("student_code", "")})
        if errors:
            return {"imported": 0, "errors": errors, "validated": len(cleaned)}
        if not cleaned:
            return {"imported": 0, "errors": [], "validated": 0}

        def _do_import(connection, cursor) -> int:
            inserted = 0
            for row_data in cleaned:
                cursor.execute(
                    """INSERT INTO students
                       (student_code, first_name, last_name, email, enrollment_date)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (row_data["student_code"], row_data["first_name"], row_data["last_name"],
                     row_data["email"], row_data["enrollment_date"]),
                )
                new_id = cursor.lastrowid
                self._audit_with(
                    connection, "student.import", "student", new_id,
                    {"student_code": row_data["student_code"]},
                )
                inserted += 1
            return inserted

        imported = self.ensure_error("student CSV import", self.students.bulk_insert, _do_import)
        return {"imported": imported, "errors": [], "validated": len(cleaned)}


class TeacherService(BaseService):
    def list(self, search: str = "", page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        """Paginated listing. Returns {items, page, page_size, total, total_pages}."""
        self.require_admin()
        page, page_size, offset = self._page_args(page, page_size)
        items = self.ensure_error("teacher listing", self.teachers.list, search, page_size, offset)
        total = self.ensure_error("teacher count", self.teachers.count, search)
        return self._page_result(items, page, page_size, total)

    def choices(self) -> list[tuple[int, str]]:
        self.require_admin()
        return self.ensure_error("teacher choices", self.teachers.choices)

    def get(self, teacher_id: int) -> dict[str, Any]:
        self.require_admin()
        row = self.ensure_error("teacher lookup", self.teachers.get, teacher_id)
        if not row:
            raise NotFoundError("Teacher not found.")
        return row

    def create(self, data: dict[str, Any]) -> int:
        self.require_admin()
        clean = {
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "hire_date": required(data.get("hire_date"), "Hire date"),
        }
        return self.audited("teacher.create", "teacher", "teacher creation", self.teachers.create, clean,
                            details=lambda new_id: {"name": f"{clean['first_name']} {clean['last_name']}", "teacher_id": new_id})

    def update(self, teacher_id: int, data: dict[str, Any]) -> int:
        self.require_admin()
        self.get(teacher_id)
        clean = {
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "hire_date": required(data.get("hire_date"), "Hire date"),
        }
        return self.audited("teacher.update", "teacher", "teacher update", self.teachers.update, teacher_id, clean,
                            entity_id=teacher_id,
                            details={"name": f"{clean['first_name']} {clean['last_name']}"})

    def delete(self, teacher_id: int) -> int:
        self.require_admin()
        existing = self.get(teacher_id)
        return self.audited("teacher.delete", "teacher", "teacher deletion", self.teachers.delete, teacher_id,
                            entity_id=teacher_id,
                            details={"name": f"{existing['first_name']} {existing['last_name']}"})


class CourseService(BaseService):
    def list(self, search: str = "", page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        """Paginated listing. Returns {items, page, page_size, total, total_pages}."""
        teacher_id = None if self.session.is_admin else self.require_teacher()
        page, page_size, offset = self._page_args(page, page_size)
        items = self.ensure_error("course listing", self.courses.list, teacher_id, search, page_size, offset)
        total = self.ensure_error("course count", self.courses.count, search)
        return self._page_result(items, page, page_size, total)

    def choices_for_student(self, student_id: int) -> list[tuple[int, str]]:
        if not self.session.is_admin:
            self.require_teacher()
        return self.ensure_error("course choices", self.enrollments.available_courses, student_id)

    def get(self, course_id: int) -> dict[str, Any]:
        row = self.ensure_error("course lookup", self.courses.get, course_id)
        if not row:
            raise NotFoundError("Course not found.")
        if not self.session.is_admin and row["teacher_id"] != self.require_teacher():
            raise PermissionDenied("You can only access your assigned courses.")
        return row

    def teacher_choices(self) -> list[tuple[int, str]]:
        self.require_admin()
        return self.ensure_error("teacher choices for course", self.teachers.choices)

    def create(self, data: dict[str, Any]) -> int:
        self.require_admin()
        clean = {
            "course_code": identifier(data.get("course_code"), "Course code"),
            "course_name": required(data.get("course_name"), "Course name"),
            "credits": credits(data.get("credits")),
            "teacher_id": data.get("teacher_id"),
        }
        if clean["teacher_id"] is not None and not self.teachers.exists(int(clean["teacher_id"])):
            raise ValidationError("Selected teacher does not exist.")
        return self.audited("course.create", "course", "course creation", self.courses.create, clean,
                            details=lambda new_id: {"course_code": clean["course_code"], "course_id": new_id})

    def update(self, course_id: int, data: dict[str, Any]) -> int:
        self.require_admin()
        self.get(course_id)
        clean = {
            "course_code": identifier(data.get("course_code"), "Course code"),
            "course_name": required(data.get("course_name"), "Course name"),
            "credits": credits(data.get("credits")),
            "teacher_id": data.get("teacher_id"),
        }
        if clean["teacher_id"] is not None and not self.teachers.exists(int(clean["teacher_id"])):
            raise ValidationError("Selected teacher does not exist.")
        return self.audited("course.update", "course", "course update", self.courses.update, course_id, clean,
                            entity_id=course_id,
                            details={"course_code": clean["course_code"]})

    def delete(self, course_id: int) -> int:
        self.require_admin()
        existing = self.get(course_id)
        return self.audited("course.delete", "course", "course deletion", self.courses.delete, course_id,
                            entity_id=course_id,
                            details={"course_code": existing["course_code"], "course_name": existing["course_name"]})

    def analytics(self, course_id: int) -> dict[str, Any]:
        row = self.get(course_id)
        analytics = self.ensure_error("course analytics", self.courses.analytics, course_id)
        if not analytics:
            raise NotFoundError("Course analytics unavailable because the course no longer exists.")
        analytics["course_code"] = row["course_code"]
        return analytics

    def enrolled_students(self, course_id: int) -> list[dict[str, Any]]:
        self.get(course_id)
        return self.ensure_error("course students", self.courses.students, course_id)


class EnrollmentService(BaseService):
    def list_for_student(self, student_id: int) -> list[dict[str, Any]]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        return self.ensure_error("student enrollments", self.enrollments.list_for_student, student_id, teacher_id)

    def available_courses(self, student_id: int) -> list[tuple[int, str]]:
        if not self.session.is_admin:
            raise PermissionDenied("Teachers cannot change student enrollments.")
        return self.ensure_error("available courses", self.enrollments.available_courses, student_id)

    def create(self, student_id: int, course_id: int, enrollment_date: str) -> int:
        self.require_admin()

        def _operation() -> int:
            # Checks live inside the audited operation so a rule rejection
            # (unknown student/course, duplicate enrollment) is itself audited.
            if not self.students.get(student_id):
                raise ValidationError("Student does not exist.")
            if not self.courses.get(course_id):
                raise ValidationError("Course does not exist.")
            if self.enrollments.exists(student_id, course_id):
                raise ValidationError("This student is already enrolled in the selected course.")
            return self.enrollments.create(student_id, course_id, required(enrollment_date, "Enrollment date"))

        return self.audited("enrollment.create", "enrollment", "enrollment creation", _operation,
                            details=lambda new_id: {"student_id": student_id, "course_id": course_id, "enrollment_id": new_id})

    def delete(self, enrollment_id: int) -> int:
        self.require_admin()
        enrollment = self.enrollments.get(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment not found.")
        return self.audited("enrollment.delete", "enrollment", "enrollment deletion", self.enrollments.delete, enrollment_id,
                            entity_id=enrollment_id,
                            details={"student": enrollment.get("student_name"), "course": enrollment.get("course_code")})


class GradeService(BaseService):
    def get(self, enrollment_id: int) -> dict[str, Any] | None:
        enrollment = self.enrollments.get(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment not found.")
        if not self.session.is_admin and enrollment["teacher_id"] != self.require_teacher():
            raise PermissionDenied("Teachers can only access grades in their own courses.")
        return self.ensure_error("grade lookup", self.grades.get, enrollment_id)

    def set_grade(self, enrollment_id: int, value: float, graded_date: str) -> int:
        enrollment = self.enrollments.get(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment no longer exists.")
        if not self.session.is_admin and enrollment["teacher_id"] != self.require_teacher():
            raise PermissionDenied("Teachers can only grade students in their own courses.")
        clean_value = grade(value)
        clean_date = required(graded_date, "Graded date")

        def _upsert_and_audit(connection, cursor) -> int:
            cursor.execute(
                """INSERT INTO grades (enrollment_id, grade_value, graded_date)
                   VALUES (%s,%s,%s)
                   ON DUPLICATE KEY UPDATE grade_value=VALUES(grade_value), graded_date=VALUES(graded_date)""",
                (enrollment_id, clean_value, clean_date),
            )
            self._audit_with(
                connection, "grade.update", "enrollment", enrollment_id,
                {"grade_value": float(clean_value),
                 "student": enrollment.get("student_name"),
                 "course": enrollment.get("course_code")},
            )
            return enrollment_id

        return self.ensure_error("grade update", self.grades.run_in_transaction, _upsert_and_audit)


class DashboardService(BaseService):
    def summary(self) -> dict[str, Any]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        totals = self.ensure_error("dashboard totals", self.dashboard_repo.totals)
        if teacher_id is not None:
            scoped = self.dashboard_repo.teacher_totals(teacher_id)
            totals = {"students": scoped["students"], "teachers": 1, "courses": scoped["courses"], "enrollments": scoped["enrollments"]}
        return totals

    def grade_distribution(self) -> list[dict[str, Any]]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        return self.ensure_error("grade distribution", self.dashboard_repo.grade_distribution, teacher_id)

    def recent_enrollments(self) -> list[dict[str, Any]]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        return self.ensure_error("recent enrollments", self.dashboard_repo.recent_enrollments, teacher_id)

    def course_summary(self) -> list[dict[str, Any]]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        return self.ensure_error("course summary", self.dashboard_repo.course_summary, teacher_id)


class UserService(BaseService):
    def _raw_get(self, user_id: int) -> dict[str, Any] | None:
        """Unauthenticated row fetch used by the API's token-state check.

        Deliberately bypasses require_admin: the caller is the authentication
        dependency itself, verifying that the token's account still exists,
        is active, and has an unchanged role."""
        return self.ensure_error("user lookup", self.users.get, user_id)

    def list(self) -> list[dict[str, Any]]:
        self.require_admin()
        return self.ensure_error("user listing", self.users.list)

    def get(self, user_id: int) -> dict[str, Any] | None:
        self.require_admin()
        return self.ensure_error("user lookup", self.users.get, user_id)

    def create(self, username: str, password: str, role: str, teacher_id: int | None) -> int:
        self.require_admin()
        username = identifier(username, "Username")
        password = required(password, "Password")
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        role = required(role, "Role").upper()
        if role not in {"ADMIN", "TEACHER"}:
            raise ValidationError("Role must be ADMIN or TEACHER.")
        if role == "ADMIN":
            teacher_id = None
        elif teacher_id is None or not self.teachers.exists(int(teacher_id)):
            raise ValidationError("A TEACHER account must be linked to a valid teacher profile.")
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        def _create_and_audit(connection, cursor) -> int:
            cursor.execute(
                "INSERT INTO users (username,password_hash,role,teacher_id) VALUES (%s,%s,%s,%s)",
                (username, password_hash, role, teacher_id),
            )
            new_id = cursor.lastrowid
            self._audit_with(
                connection, "user.create", "user", new_id,
                {"new_username": username, "role": role, "teacher_id": teacher_id},
            )
            return new_id

        return self.ensure_error("user creation", self.users.run_in_transaction, _create_and_audit)

    def set_active(self, user_id: int, is_active: bool) -> int:
        self.require_admin()
        if user_id == self.session.user_id and not is_active:
            raise ValidationError("You cannot deactivate the currently signed-in account.")
        target = self.users.get(user_id)
        if not target:
            raise NotFoundError("User not found.")

        def _deactivate_and_audit(connection, cursor) -> int:
            cursor.execute("UPDATE users SET is_active=%s WHERE id=%s", (bool(is_active), user_id))
            self._audit_with(
                connection, "user.deactivate" if not is_active else "user.activate", "user", user_id,
                {"target_username": target["username"]},
            )
            return user_id

        return self.ensure_error("user activation change", self.users.run_in_transaction, _deactivate_and_audit)


class AuditLogService(BaseService):
    """Admin-only read access to the audit trail."""

    def list(self, *, action: str = "", entity_type: str = "", username: str = "", status: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
        self.require_admin()
        page, page_size, offset = self._page_args(page, page_size)
        items = self.ensure_error(
            "audit listing", self.audit.list,
            action=action, entity_type=entity_type, username=username, status=status,
            limit=page_size, offset=offset,
        )
        total = self.ensure_error(
            "audit count", self.audit.count,
            action=action, entity_type=entity_type, username=username, status=status,
        )
        return self._page_result(items, page, page_size, total)


class ServiceBundle:
    """Convenience factory keeping every UI screen on the same session boundary."""
    def __init__(self, db, session: Session):
        self.auth = AuthService(db)
        self.students = StudentService(db, session)
        self.teachers = TeacherService(db, session)
        self.courses = CourseService(db, session)
        self.enrollments = EnrollmentService(db, session)
        self.grades = GradeService(db, session)
        self.dashboard = DashboardService(db, session)
        self.users = UserService(db, session)
        self.audit_logs = AuditLogService(db, session)
