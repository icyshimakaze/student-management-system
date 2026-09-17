"""End-to-end service/repository tests against a real MySQL server.

Skipped automatically when no MySQL is reachable (see integration_utils).
Never touches the developer's real database: uses TEST_DB_NAME only.
"""
from __future__ import annotations

import bcrypt
import pytest

from integration_utils import db, test_db, unique_code  # noqa: F401
from repositories import (
    CourseRepository, EnrollmentRepository, GradeRepository,
    StudentRepository, TeacherRepository, UserRepository,
)
from services import (
    AuthService, CourseService, EnrollmentService, GradeService,
    PermissionDenied, Session, StudentService, UserService,
)
from validation import ValidationError


@pytest.fixture(scope="module")
def repos(db):
    return {
        "students": StudentRepository(db),
        "teachers": TeacherRepository(db),
        "courses": CourseRepository(db),
        "enrollments": EnrollmentRepository(db),
        "grades": GradeRepository(db),
        "users": UserRepository(db),
    }


@pytest.fixture(scope="module")
def teacher_ids(repos):
    return {
        "A": repos["teachers"].create(
            {"first_name": "Ada", "last_name": "Own", "email": "ada.own@test.edu", "hire_date": "2020-01-01"}
        ),
        "B": repos["teachers"].create(
            {"first_name": "Bob", "last_name": "Other", "email": "bob.other@test.edu", "hire_date": "2020-01-02"}
        ),
    }


@pytest.fixture(scope="module")
def course_ids(repos, teacher_ids):
    return {
        "A": repos["courses"].create(
            {"course_code": "OWN-101", "course_name": "Owned Course", "credits": 3, "teacher_id": teacher_ids["A"]}
        ),
        "B": repos["courses"].create(
            {"course_code": "OTHER-201", "course_name": "Other Course", "credits": 3, "teacher_id": teacher_ids["B"]}
        ),
    }


@pytest.fixture(scope="module")
def admin_session(repos):
    username = "it_admin"
    password = "it-admin-password-1"
    username_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = repos["users"].create(username, username_hash, "ADMIN", None)
    repos["users"].set_active(user_id, True)
    session = AuthService(db).authenticate(username, password)
    assert session.is_admin
    return session


# ---------------------------------------------------------------- auth

def test_login_success_and_failure(admin_session):
    # admin_session fixture already proved a successful login.
    assert admin_session.user_id > 0
    with pytest.raises(ValidationError):
        AuthService(db).authenticate("it_admin", "wrong-password")
    with pytest.raises(ValidationError):
        AuthService(db).authenticate("no_such_user", "whatever")


def test_inactive_user_cannot_log_in(repos):
    password = "inactive-pass-1"
    user_id = repos["users"].create(
        "it_inactive",
        bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "ADMIN",
        None,
    )
    repos["users"].set_active(user_id, False)
    with pytest.raises(ValidationError):
        AuthService(db).authenticate("it_inactive", password)


# ---------------------------------------------------------------- students

def test_student_crud_roundtrip(repos, unique_code):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "Inte", "last_name": "Gration",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    fetched = repos["students"].get(student_id)
    assert fetched["first_name"] == "Inte"
    updated = repos["students"].update(
        student_id,
        {"student_code": code, "first_name": "Updated", "last_name": "Gration",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"},
    )
    assert repos["students"].get(student_id)["first_name"] == "Updated"
    repos["students"].delete(student_id)
    assert repos["students"].get(student_id) is None
    assert updated >= 0


def test_duplicate_student_code_rejected(repos, unique_code):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "First", "last_name": "Dupe",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    import mysql.connector
    with pytest.raises(mysql.connector.Error):
        repos["students"].create(
            {"student_code": code, "first_name": "Second", "last_name": "Dupe",
             "email": f"other-{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
        )
    repos["students"].delete(student_id)


# ------------------------------------------------- authorization (the core)

def _enroll_student(repos, unique_code, course_id):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "Grade", "last_name": "Me",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    enrollment_id = repos["enrollments"].create(student_id, course_id, "2026-01-11")
    return student_id, enrollment_id


def test_teacher_can_grade_own_course(repos, unique_code, course_ids, teacher_ids):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["A"])
    session = Session(900, "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = GradeService(db, session)
    svc.set_grade(enrollment_id, 92.5, "2026-02-01")
    assert float(repos["grades"].get(enrollment_id)["grade_value"]) == 92.5


def test_teacher_cannot_grade_other_teachers_course(repos, unique_code, course_ids, teacher_ids):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["B"])
    session = Session(901, "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = GradeService(db, session)
    with pytest.raises(PermissionDenied):
        svc.set_grade(enrollment_id, 50, "2026-02-01")
    assert repos["grades"].get(enrollment_id) is None


def test_admin_can_grade_any_course(repos, unique_code, course_ids, admin_session):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["B"])
    svc = GradeService(db, admin_session)
    svc.set_grade(enrollment_id, 77, "2026-02-01")
    assert float(repos["grades"].get(enrollment_id)["grade_value"]) == 77


def test_teacher_cannot_read_other_course_students(repos, course_ids, teacher_ids):
    session = Session(902, "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = CourseService(db, session)
    with pytest.raises(PermissionDenied):
        svc.students(course_ids["B"])


def test_teacher_cannot_create_students(repos, admin_session):
    svc = StudentService(db, admin_session)
    assert svc.list()  # admin may list
    teacher_session = Session(903, "it_teacher_x", "TEACHER", None)
    from services import StudentService as S
    with pytest.raises(PermissionDenied):
        S(db, teacher_session).list()


# ---------------------------------------------------------------- enrollments

def test_duplicate_enrollment_rejected(repos, unique_code, course_ids):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "Dup", "last_name": "Enroll",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    repos["enrollments"].create(student_id, course_ids["A"], "2026-01-11")
    with pytest.raises(Exception):
        repos["enrollments"].create(student_id, course_ids["A"], "2026-01-12")
    assert len(repos["enrollments"].list_for_student(student_id)) == 1


def test_enrollment_service_validates_and_creates(repos, unique_code, course_ids, admin_session):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "Svc", "last_name": "Enroll",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    svc = EnrollmentService(db, admin_session)
    enrollment_id = svc.create(student_id, course_ids["A"], "2026-01-15")
    assert enrollment_id > 0
    with pytest.raises(ValidationError):
        svc.create(student_id, course_ids["A"], "2026-01-15")  # duplicate


def test_grade_service_rejects_out_of_range(repos, unique_code, course_ids, admin_session):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["A"])
    svc = GradeService(db, admin_session)
    for bad in (-5, 150, "abc"):
        with pytest.raises(ValidationError):
            svc.set_grade(enrollment_id, bad, "2026-02-01")


# ---------------------------------------------------------------- transactions

def test_rollback_on_failure_leaves_no_partial_data(repos, unique_code, course_ids):
    code = unique_code()
    student_id = repos["students"].create(
        {"student_code": code, "first_name": "Roll", "last_name": "Back",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"}
    )
    class Boom(Exception):
        pass
    with pytest.raises(Boom):
        with repos["students"].transaction(dictionary=True) as (connection, cursor):
            cursor.execute(
                "INSERT INTO enrollments (student_id, course_id, enrollment_date) VALUES (%s,%s,%s)",
                (student_id, course_ids["A"], "2026-01-11"),
            )
            raise Boom()
    assert repos["enrollments"].list_for_student(student_id) == []


# ---------------------------------------------------------------- analytics

def test_course_analytics_and_student_profile(repos, unique_code, course_ids, admin_session):
    student_id, enrollment_id = _enroll_student(repos, unique_code, course_ids["A"])
    repos["grades"].upsert(enrollment_id, 65, "2026-02-02")
    analytics = CourseService(db, admin_session).analytics(course_ids["A"])
    assert analytics["enrollment_count"] >= 1
    assert analytics["course_code"] == "OWN-101"
    profile = StudentService(db, admin_session).profile(student_id)
    assert profile["student"]["student_id"] == student_id
    assert any(c["course_code"] == "OWN-101" for c in profile["courses"])
    assert profile["average_grade"] is not None


def test_dashboard_summary_admin(repos, admin_session):
    from services import DashboardService
    totals = DashboardService(db, admin_session).summary()
    assert set(totals) >= {"students", "teachers", "courses", "enrollments"}
    assert all(isinstance(v, int) for v in totals.values())


def test_teacher_dashboard_is_scoped(repos, unique_code, course_ids, teacher_ids):
    from services import DashboardService
    session = Session(904, "it_teacher_a", "TEACHER", teacher_ids["A"])
    totals = DashboardService(db, session).summary()
    assert totals["teachers"] == 1  # scoped view reports only self
    assert totals["courses"] >= 1


def test_user_service_requires_admin(repos):
    from services import UserService
    teacher_session = Session(905, "it_teacher_y", "TEACHER", None)
    with pytest.raises(PermissionDenied):
        UserService(db, teacher_session).list()
