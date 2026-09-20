import bcrypt
import pytest

from repositories import AuditLogRepository  # noqa: F401  (used by services)
from services import (
    AuthService,
    EnrollmentService,
    GradeService,
    PermissionDenied,
    Session,
    StudentService,
    UserService,
)
from validation import ValidationError


class _FakeConn:
    lastrowid = 99
    def cursor(self): return _FakeConn()
    def execute(self, *a): pass

class FakeUsers:
    def __init__(self, user): self.user=user; self.created=None; self.active={user["id"]: user["is_active"]}
    def get_by_username(self, username): return self.user if self.user and self.user["username"] == username else None
    def get(self, user_id): return {"id": user_id} if user_id in self.active else None
    def create(self, *args): self.created=args; return 99
    def set_active(self, user_id, active): self.active[user_id]=active; return 1
    def run_in_transaction(self, callback): return callback(_FakeConn(), _FakeConn())


def test_authenticate_valid_password():
    hashed=bcrypt.hashpw(b"correct-password",bcrypt.gensalt()).decode()
    repo=FakeUsers({"id":1,"username":"admin","password_hash":hashed,"role":"ADMIN","is_active":True,"teacher_id":None})
    session=AuthService(None,repo).authenticate("admin","correct-password")
    assert session.is_admin and session.user_id == 1


def test_authenticate_rejects_inactive_user():
    hashed=bcrypt.hashpw(b"correct-password",bcrypt.gensalt()).decode()
    repo=FakeUsers({"id":1,"username":"admin","password_hash":hashed,"role":"ADMIN","is_active":False,"teacher_id":None})
    with pytest.raises(ValidationError): AuthService(None,repo).authenticate("admin","correct-password")


def test_authenticate_rejects_bad_password():
    hashed=bcrypt.hashpw(b"correct-password",bcrypt.gensalt()).decode()
    repo=FakeUsers({"id":1,"username":"admin","password_hash":hashed,"role":"ADMIN","is_active":True,"teacher_id":None})
    with pytest.raises(ValidationError): AuthService(None,repo).authenticate("admin","wrong-password")


class FakeEnrollmentRepo:
    def __init__(self, row=None): self.row=row
    def get(self, enrollment_id): return self.row


class FakeGradeRepo:
    def __init__(self): self.called=None
    executed = None
    def upsert(self, *args): self.called=args; return 12
    def get(self, enrollment_id): return {"grade_value": 80}
    def run_in_transaction(self, callback):
        class _C:  # minimal connection/cursor doubles for the audit no-op
            lastrowid = 55
            def cursor(self): return self
            def execute(self, sql, params=None):
                FakeGradeRepo.executed = (sql, params)
        return callback(_C(), _C())


class FakeStudentRepo:
    def __init__(self): self.created=None
    def get(self, student_id): return {"student_id": student_id}
    def create(self, data): self.created=data; return 42


class FakeTeacherRepo:
    def __init__(self): self.exists_ids={7}
    def exists(self, teacher_id): return teacher_id in self.exists_ids


def make_grade_service(role="TEACHER", teacher_id=7, enrollment_teacher=7):
    svc=GradeService(None,Session(1,"u",role,teacher_id))
    svc.enrollments=FakeEnrollmentRepo({"enrollment_id":55,"student_id":1,"course_id":2,"teacher_id":enrollment_teacher})
    svc.grades=FakeGradeRepo()
    return svc


def test_teacher_can_grade_own_course():
    svc=make_grade_service()
    assert svc.set_grade(55,91.25,"2026-09-17") == 55
    assert FakeGradeRepo.executed[1] == (55, 91.25, "2026-09-17")


def test_teacher_cannot_grade_another_teachers_course():
    svc=make_grade_service(enrollment_teacher=8)
    with pytest.raises(PermissionDenied): svc.set_grade(55,91,"2026-09-17")


def test_admin_can_grade_any_course():
    svc=make_grade_service(role="ADMIN",teacher_id=None,enrollment_teacher=8)
    assert svc.set_grade(55,91,"2026-09-17") == 55


def test_student_create_requires_admin():
    svc=StudentService(None,Session(2,"teacher","TEACHER",7)); svc.students=FakeStudentRepo()
    with pytest.raises(PermissionDenied): svc.create({"student_code":"STU-9","first_name":"Ava","last_name":"Lee","email":"ava@example.com","enrollment_date":"2026-09-17"})


def test_student_create_validates_and_delegates():
    svc=StudentService(None,Session(2,"admin","ADMIN",None)); repo=FakeStudentRepo(); svc.students=repo
    assert svc.create({"student_code":"STU-0009","first_name":"Ava","last_name":"Lee","email":"Ava@Example.com","enrollment_date":"2026-09-17"}) == 42
    assert repo.created["email"] == "ava@example.com"


def test_enrollment_service_blocks_teacher_mutation():
    svc=EnrollmentService(None,Session(2,"teacher","TEACHER",7))
    with pytest.raises(PermissionDenied): svc.available_courses(1)


def test_user_service_requires_secure_password_and_links_teacher():
    svc=UserService(None,Session(1,"admin","ADMIN",None)); svc.teachers=FakeTeacherRepo(); repo=FakeUsers({"id":1,"username":"admin","password_hash":"x","role":"ADMIN","is_active":True,"teacher_id":None}); svc.users=repo

    captured = {}
    def _capture(callback_arg):
        class _Cur:
            lastrowid = 99
            def execute(self, sql, params): captured["params"] = params
        class _Conn:
            def cursor(self): return _Cur()
        return callback_arg(_Conn(), _Cur())  # service callback drives cursor.execute
    repo.run_in_transaction = _capture

    assert svc.create("teacher01","long-enough","TEACHER",7) == 99
    # create now routes through a transaction callback: params = (username, hash, role, teacher_id)
    assert captured["params"][2:] == ("TEACHER", 7)
    with pytest.raises(ValidationError): svc.create("x","short","ADMIN",None)
