"""Business services: authorization, validation and workflow coordination."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import bcrypt
import mysql.connector

from repositories import (
    CourseRepository, DashboardRepository, EnrollmentRepository, GradeRepository,
    StudentRepository, TeacherRepository, UserRepository,
)
from validation import ValidationError, credits, email, identifier, grade, name, required

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

    def require_admin(self) -> None:
        if not self.session.is_admin:
            raise PermissionDenied("This action is available to administrators only.")

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


class AuthService:
    def __init__(self, db, user_repo: UserRepository | None = None):
        self.db = db
        self.users = user_repo or UserRepository(db)

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
        return Session(user["id"], user["username"], user["role"], user["teacher_id"])


class StudentService(BaseService):
    def list(self, search: str = "") -> list[dict[str, Any]]:
        self.require_admin()
        return self.ensure_error("student listing", self.students.list, search)

    def get(self, student_id: int) -> dict[str, Any]:
        self.require_admin()
        row = self.ensure_error("student lookup", self.students.get, student_id)
        if not row:
            raise NotFoundError("Student not found.")
        return row

    def create(self, data: dict[str, Any]) -> int:
        self.require_admin()
        clean = {
            "student_code": identifier(data.get("student_code"), "Student ID"),
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "enrollment_date": required(data.get("enrollment_date"), "Enrollment date"),
        }
        return self.ensure_error("student creation", self.students.create, clean)

    def update(self, student_id: int, data: dict[str, Any]) -> int:
        self.require_admin()
        self.get(student_id)
        clean = {
            "student_code": identifier(data.get("student_code"), "Student ID"),
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "enrollment_date": required(data.get("enrollment_date"), "Enrollment date"),
        }
        return self.ensure_error("student update", self.students.update, student_id, clean)

    def delete(self, student_id: int) -> int:
        self.require_admin()
        self.get(student_id)
        return self.ensure_error("student deletion", self.students.delete, student_id)

    def profile(self, student_id: int) -> dict[str, Any]:
        self.require_admin()
        return self.ensure_error("student profile", self.students.profile, student_id)


class TeacherService(BaseService):
    def list(self, search: str = "") -> list[dict[str, Any]]:
        self.require_admin()
        return self.ensure_error("teacher listing", self.teachers.list, search)

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
        return self.ensure_error("teacher creation", self.teachers.create, clean)

    def update(self, teacher_id: int, data: dict[str, Any]) -> int:
        self.require_admin()
        self.get(teacher_id)
        clean = {
            "first_name": name(data.get("first_name"), "First name"),
            "last_name": name(data.get("last_name"), "Last name"),
            "email": email(data.get("email")),
            "hire_date": required(data.get("hire_date"), "Hire date"),
        }
        return self.ensure_error("teacher update", self.teachers.update, teacher_id, clean)

    def delete(self, teacher_id: int) -> int:
        self.require_admin()
        self.get(teacher_id)
        return self.ensure_error("teacher deletion", self.teachers.delete, teacher_id)


class CourseService(BaseService):
    def list(self, search: str = "") -> list[dict[str, Any]]:
        teacher_id = None if self.session.is_admin else self.require_teacher()
        return self.ensure_error("course listing", self.courses.list, teacher_id, search)

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
        return self.ensure_error("course creation", self.courses.create, clean)

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
        return self.ensure_error("course update", self.courses.update, course_id, clean)

    def delete(self, course_id: int) -> int:
        self.require_admin()
        self.get(course_id)
        return self.ensure_error("course deletion", self.courses.delete, course_id)

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
        if not self.students.get(student_id):
            raise ValidationError("Student does not exist.")
        if not self.courses.get(course_id):
            raise ValidationError("Course does not exist.")
        if self.enrollments.exists(student_id, course_id):
            raise ValidationError("This student is already enrolled in the selected course.")
        return self.ensure_error("enrollment creation", self.enrollments.create, student_id, course_id, required(enrollment_date, "Enrollment date"))

    def delete(self, enrollment_id: int) -> int:
        self.require_admin()
        if not self.enrollments.get(enrollment_id):
            raise NotFoundError("Enrollment not found.")
        return self.ensure_error("enrollment deletion", self.enrollments.delete, enrollment_id)


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
        return self.ensure_error("grade update", self.grades.upsert, enrollment_id, clean_value, clean_date)


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
        return self.ensure_error("user creation", self.users.create, username, password_hash, role, teacher_id)

    def set_active(self, user_id: int, is_active: bool) -> int:
        self.require_admin()
        if user_id == self.session.user_id and not is_active:
            raise ValidationError("You cannot deactivate the currently signed-in account.")
        if not self.users.get(user_id):
            raise NotFoundError("User not found.")
        return self.ensure_error("user activation change", self.users.set_active, user_id, bool(is_active))


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
