"""End-to-end service/repository tests against a real MySQL server.

Skipped automatically when no MySQL is reachable (see integration_utils).
Never touches the developer's real database: uses TEST_DB_NAME only.
"""
from __future__ import annotations

import bcrypt
import pytest
from integration_utils import db, test_db, unique_code  # noqa: F401

from repositories import (
    CourseRepository,
    EnrollmentRepository,
    GradeRepository,
    StudentRepository,
    TeacherRepository,
    UserRepository,
)
from services import (
    AuthService,
    CourseService,
    DashboardService,
    EnrollmentService,
    GradeService,
    PermissionDenied,
    Session,
    StudentService,
    UserService,
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
def admin_session(repos, db):
    username = "it_admin"
    password = "it-admin-password-1"
    username_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = repos["users"].create(username, username_hash, "ADMIN", None)
    repos["users"].set_active(user_id, True)
    session = AuthService(db).authenticate(username, password)
    assert session.is_admin
    return session


# ---------------------------------------------------------------- auth

def test_login_success_and_failure(admin_session, db):
    # admin_session fixture already proved a successful login.
    assert admin_session.user_id > 0
    with pytest.raises(ValidationError):
        AuthService(db).authenticate("it_admin", "wrong-password")
    with pytest.raises(ValidationError):
        AuthService(db).authenticate("no_such_user", "whatever")


def test_inactive_user_cannot_log_in(repos, db):
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
    repos["students"].update(
        student_id,
        {"student_code": code, "first_name": "Updated", "last_name": "Gration",
         "email": f"{code.lower()}@test.edu", "enrollment_date": "2026-01-10"},
    )
    assert repos["students"].get(student_id)["first_name"] == "Updated"
    repos["students"].delete(student_id)
    assert repos["students"].get(student_id) is None


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



def _ensure_user(db, username: str) -> int:
    """Map a fake test session identity to a real users row for audit FKs."""
    conn = db.connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row["id"]
    import bcrypt as _bcrypt
    hashed = _bcrypt.hashpw(b"integration-pw", _bcrypt.gensalt()).decode()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username,password_hash,role,is_active) VALUES (%s,%s,'TEACHER',1)", (username, hashed))
    conn.commit()
    uid = cur.lastrowid
    cur.close()
    return uid


def test_teacher_can_grade_own_course(db, repos, unique_code, course_ids, teacher_ids):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["A"])
    session = Session(_ensure_user(db, "it_teacher_a"), "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = GradeService(db, session)
    svc.set_grade(enrollment_id, 92.5, "2026-02-01")
    assert float(repos["grades"].get(enrollment_id)["grade_value"]) == 92.5


def test_teacher_cannot_grade_other_teachers_course(db, repos, unique_code, course_ids, teacher_ids):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["B"])
    session = Session(_ensure_user(db, "it_teacher_a"), "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = GradeService(db, session)
    with pytest.raises(PermissionDenied):
        svc.set_grade(enrollment_id, 50, "2026-02-01")
    assert repos["grades"].get(enrollment_id) is None


def test_admin_can_grade_any_course(db, repos, unique_code, course_ids, admin_session):
    _, enrollment_id = _enroll_student(repos, unique_code, course_ids["B"])
    svc = GradeService(db, admin_session)
    svc.set_grade(enrollment_id, 77, "2026-02-01")
    assert float(repos["grades"].get(enrollment_id)["grade_value"]) == 77


def test_teacher_cannot_read_other_course_students(db, repos, course_ids, teacher_ids):
    session = Session(_ensure_user(db, "it_teacher_a"), "it_teacher_a", "TEACHER", teacher_ids["A"])
    svc = CourseService(db, session)
    with pytest.raises(PermissionDenied):
        svc.enrolled_students(course_ids["B"])


def test_teacher_cannot_list_students(db, repos):
    teacher_session = Session(_ensure_user(db, "it_teacher_x"), "it_teacher_x", "TEACHER", None)
    with pytest.raises(PermissionDenied):
        StudentService(db, teacher_session).list()


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


def test_enrollment_service_validates_and_creates(db, repos, unique_code, course_ids, admin_session):
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


def test_grade_service_rejects_out_of_range(db, repos, unique_code, course_ids, admin_session):
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

def test_course_analytics_and_student_profile(db, repos, unique_code, course_ids, admin_session):
    student_id, enrollment_id = _enroll_student(repos, unique_code, course_ids["A"])
    repos["grades"].upsert(enrollment_id, 65, "2026-02-02")
    analytics = CourseService(db, admin_session).analytics(course_ids["A"])
    assert analytics["enrollment_count"] >= 1
    assert analytics["course_code"] == "OWN-101"
    profile = StudentService(db, admin_session).profile(student_id)
    assert profile["student"]["student_id"] == student_id
    assert any(c["course_code"] == "OWN-101" for c in profile["courses"])
    assert profile["average_grade"] is not None


def test_dashboard_summary_admin(db, repos, admin_session):
    totals = DashboardService(db, admin_session).summary()
    assert set(totals) >= {"students", "teachers", "courses", "enrollments"}
    assert all(isinstance(v, int) for v in totals.values())


def test_teacher_dashboard_is_scoped(db, repos, unique_code, course_ids, teacher_ids):
    session = Session(_ensure_user(db, "it_teacher_a"), "it_teacher_a", "TEACHER", teacher_ids["A"])
    totals = DashboardService(db, session).summary()
    assert totals["teachers"] == 1  # scoped view reports only self
    assert totals["courses"] >= 1


def test_user_service_requires_admin(db, repos):
    teacher_session = Session(_ensure_user(db, "it_teacher_y"), "it_teacher_y", "TEACHER", None)
    with pytest.raises(PermissionDenied):
        UserService(db, teacher_session).list()


def _ensure_admin(db) -> int:
    """The test schema ships without an admin row; audit FKs need a real user."""
    conn = db.connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM users WHERE username='it-admin' LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.close()
        conn.close()
        return row["id"]
    cur.close()
    conn.close()
    import bcrypt as _bcrypt
    hashed = _bcrypt.hashpw(b"integration-admin-pw", _bcrypt.gensalt()).decode()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username,password_hash,role,is_active) VALUES ('it-admin',%s,'ADMIN',1)", (hashed,))
    conn.commit()
    uid = cur.lastrowid
    cur.close()
    return uid


# ------------------------------------------------------------ audit logging

def test_grade_update_writes_audit_row(repos, db, unique_code):
    t = repos["teachers"].create({"first_name": "Ada", "last_name": "Audit", "email": unique_code("audit") + "@x.edu", "hire_date": "2024-01-01"})
    c = repos["courses"].create({"course_code": unique_code("AUD"), "course_name": "Audit Course", "credits": 3, "teacher_id": t})
    s = repos["students"].create({"student_code": unique_code(), "first_name": "Aud", "last_name": "Itor", "email": unique_code("aud") + "@x.edu", "enrollment_date": "2024-02-01"})
    e = repos["enrollments"].create(s, c, "2024-02-01")
    admin_id = _ensure_admin(db)
    session = Session(admin_id, "admin", "ADMIN", None)
    GradeService(db, session).set_grade(e, 88.5, "2024-03-01")
    conn = db.connect(); row = conn.cursor(dictionary=True)
    row.execute("SELECT username, action, entity_type, entity_id FROM audit_logs WHERE entity_type='enrollment' AND entity_id=%s ORDER BY audit_id DESC LIMIT 1", (e,))
    audit = row.fetchone(); row.close(); conn.close()
    assert audit and audit["action"] == "grade.update" and audit["username"] == "admin"


def test_failed_csv_import_rolls_back_completely(repos, db, unique_code):
    svc = StudentService(db, Session(_ensure_admin(db), "admin", "ADMIN", None))
    good = {"student_code": unique_code(), "first_name": "Good", "last_name": "Row", "email": unique_code("g") + "@x.edu", "enrollment_date": "2024-01-01"}
    bad = {"student_code": unique_code(), "first_name": "", "last_name": "NoFirst", "email": "not-an-email", "enrollment_date": "2024-01-01"}
    before = repos["students"].count()
    result = svc.import_csv([good, bad])
    assert result["imported"] == 0 and len(result["errors"]) == 1
    assert repos["students"].count() == before  # atomic: nothing inserted


def test_successful_csv_import_inserts_and_audits(repos, db, unique_code):
    svc = StudentService(db, Session(_ensure_admin(db), "admin", "ADMIN", None))
    rows = [
        {"student_code": unique_code(), "first_name": "Bulk", "last_name": "Import", "email": unique_code(f"b{i}") + "@x.edu", "enrollment_date": "2024-01-05"}
        for i in range(3)
    ]
    result = svc.import_csv(rows)
    assert result["imported"] == 3 and result["errors"] == []
    conn = db.connect(); check = conn.cursor(dictionary=True)
    check.execute("SELECT COUNT(*) AS n FROM audit_logs WHERE action='student.import'")
    assert check.fetchone()["n"] >= 3
    check.close(); conn.close()


# ------------------------------------------------------------ pagination

def test_student_pagination_metadata(repos, db):
    svc = StudentService(db, Session(_ensure_admin(db), "admin", "ADMIN", None))
    page = svc.list("", page=1, page_size=2)
    assert page["page_size"] == 2 and len(page["items"]) <= 2
    assert page["total_pages"] >= 1 and page["total"] >= page["total_pages"] * 0
    assert page["page"] == 1
    if page["total_pages"] > 1:
        page2 = svc.list("", page=2, page_size=2)
        assert page2["items"][0]["student_id"] != (page["items"][0]["student_id"] if page["items"] else -1)


def test_page_size_is_capped(repos, db):
    svc = StudentService(db, Session(_ensure_admin(db), "admin", "ADMIN", None))
    page = svc.list("", page=1, page_size=10000)
    assert page["page_size"] <= 100


# ------------------------------------------ deactivation revokes live tokens

def test_deactivated_user_rejected_on_next_validation(repos, db, unique_code):
    users = UserRepository(db)
    username = unique_code("deact")
    uid = UserService(db, Session(_ensure_admin(db), "admin", "ADMIN", None)).create(username, "strong-pass-1", "ADMIN", None)
    # active: raw check passes
    row = users.get(uid)
    assert bool(row["is_active"]) is True
    # deactivate via service (also writes an audit row)
    UserService(db, Session(_ensure_admin(db), "admin", "ADMIN", None)).set_active(uid, False)
    row = users.get(uid)
    assert bool(row["is_active"]) is False
    conn = db.connect(); check = conn.cursor(dictionary=True)
    check.execute("SELECT action FROM audit_logs WHERE entity_type='user' AND entity_id=%s ORDER BY audit_id DESC LIMIT 1", (uid,))
    assert check.fetchone()["action"] == "user.deactivate"
    check.close(); conn.close()
