"""Repository layer: all SQL/database access lives here."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class BaseRepository:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def transaction(self, *, dictionary: bool = False) -> Iterator[Any]:
        connection = self.db.connect()
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield connection, cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        connection = self.db.connect()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            connection.close()

    def fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        connection = self.db.connect()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute one statement. Returns the new row's id for INSERTs and the
        affected-row count for UPDATE/DELETE (lastrowid is 0 there)."""
        with self.transaction() as (_, cursor):
            cursor.execute(sql, params)
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def run_in_transaction(self, callback) -> int:
        """Run callback(connection, cursor) inside one transaction. Lets the
        service write a change and its audit row atomically."""
        connection = self.db.connect()
        cursor = connection.cursor()
        try:
            result = callback(connection, cursor)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


class StudentRepository(BaseRepository):
    BASE_SELECT = """
        SELECT s.student_id, s.student_code, s.first_name, s.last_name, s.email,
               s.enrollment_date,
               GROUP_CONCAT(DISTINCT c.course_name ORDER BY c.course_name SEPARATOR ', ') AS courses,
               ROUND(AVG(g.grade_value), 2) AS avg_grade
        FROM students s
        LEFT JOIN enrollments e ON e.student_id = s.student_id
        LEFT JOIN courses c ON c.course_id = e.course_id
        LEFT JOIN grades g ON g.enrollment_id = e.enrollment_id
    """

    BASE_WHERE = """
        WHERE (%s = '' OR s.first_name LIKE %s OR s.last_name LIKE %s
               OR s.student_code LIKE %s OR s.email LIKE %s)
    """

    def list(self, search: str = "", limit: int = 0, offset: int = 0) -> list[dict[str, Any]]:
        """List students; limit=0 means no pagination (used by export)."""
        term = search.strip()
        pattern = f"%{term}%"
        params: list[Any] = [term, pattern, pattern, pattern, pattern]
        sql = self.BASE_SELECT + self.BASE_WHERE + " GROUP BY s.student_id ORDER BY s.last_name, s.first_name"
        if limit:
            sql += " LIMIT %s OFFSET %s"
            params += [limit, offset]
        return self.fetch_all(sql, tuple(params))

    def count(self, search: str = "") -> int:
        term = search.strip()
        pattern = f"%{term}%"
        row = self.fetch_one(
            "SELECT COUNT(*) AS total FROM students s " + self.BASE_WHERE,
            (term, pattern, pattern, pattern, pattern),
        )
        return int(row["total"]) if row else 0

    def get(self, student_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT * FROM students WHERE student_id=%s", (student_id,))

    def create(self, data: dict[str, Any]) -> int:
        return self.execute(
            """INSERT INTO students
               (student_code, first_name, last_name, email, enrollment_date)
               VALUES (%s,%s,%s,%s,%s)""",
            (data["student_code"], data["first_name"], data["last_name"], data["email"], data["enrollment_date"]),
        )

    def update(self, student_id: int, data: dict[str, Any]) -> int:
        return self.execute(
            """UPDATE students SET student_code=%s, first_name=%s, last_name=%s,
               email=%s, enrollment_date=%s WHERE student_id=%s""",
            (data["student_code"], data["first_name"], data["last_name"], data["email"], data["enrollment_date"], student_id),
        )

    def delete(self, student_id: int) -> int:
        return self.execute("DELETE FROM students WHERE student_id=%s", (student_id,))

    def bulk_insert(self, callback) -> int:
        """Run callback(connection, cursor) inside ONE transaction and return
        its result. Used by the CSV import so all-or-nothing holds."""
        connection = self.db.connect()
        cursor = connection.cursor()
        try:
            result = callback(connection, cursor)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def profile(self, student_id: int) -> dict[str, Any]:
        student = self.get(student_id)
        if not student:
            return {"student": None, "courses": [], "average_grade": None}
        courses = self.fetch_all(
            """SELECT c.course_code, c.course_name, c.credits, e.enrollment_date,
                      g.grade_value, g.graded_date
               FROM enrollments e
               JOIN courses c ON c.course_id=e.course_id
               LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
               WHERE e.student_id=%s ORDER BY c.course_code""",
            (student_id,),
        )
        avg = self.fetch_one(
            """SELECT ROUND(AVG(g.grade_value),2) AS average_grade
               FROM enrollments e JOIN grades g ON g.enrollment_id=e.enrollment_id
               WHERE e.student_id=%s""",
            (student_id,),
        )
        return {"student": student, "courses": courses, "average_grade": avg["average_grade"] if avg else None}


class TeacherRepository(BaseRepository):
    def list(self, search: str = "", limit: int = 0, offset: int = 0) -> list[dict[str, Any]]:
        term = search.strip()
        p = f"%{term}%"
        sql = """SELECT t.teacher_id, t.first_name, t.last_name, t.email, t.hire_date,
                      COUNT(DISTINCT c.course_id) AS courses_taught
               FROM teachers t LEFT JOIN courses c ON c.teacher_id=t.teacher_id
               WHERE (%s='' OR t.first_name LIKE %s OR t.last_name LIKE %s OR t.email LIKE %s)
               GROUP BY t.teacher_id ORDER BY t.last_name, t.first_name"""
        params: list[Any] = [term, p, p, p]
        if limit:
            sql += " LIMIT %s OFFSET %s"
            params += [limit, offset]
        return self.fetch_all(sql, tuple(params))

    def count(self, search: str = "") -> int:
        term = search.strip()
        p = f"%{term}%"
        row = self.fetch_one(
            """SELECT COUNT(*) AS total FROM teachers t
               WHERE (%s='' OR t.first_name LIKE %s OR t.last_name LIKE %s OR t.email LIKE %s)""",
            (term, p, p, p),
        )
        return int(row["total"]) if row else 0

    def get(self, teacher_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT * FROM teachers WHERE teacher_id=%s", (teacher_id,))

    def exists(self, teacher_id: int) -> bool:
        return self.get(teacher_id) is not None

    def create(self, data: dict[str, Any]) -> int:
        return self.execute(
            "INSERT INTO teachers (first_name,last_name,email,hire_date) VALUES (%s,%s,%s,%s)",
            (data["first_name"], data["last_name"], data["email"], data["hire_date"]),
        )

    def update(self, teacher_id: int, data: dict[str, Any]) -> int:
        return self.execute(
            "UPDATE teachers SET first_name=%s,last_name=%s,email=%s,hire_date=%s WHERE teacher_id=%s",
            (data["first_name"], data["last_name"], data["email"], data["hire_date"], teacher_id),
        )

    def delete(self, teacher_id: int) -> int:
        return self.execute("DELETE FROM teachers WHERE teacher_id=%s", (teacher_id,))

    def choices(self) -> list[tuple[int, str]]:
        rows = self.fetch_all("SELECT teacher_id, CONCAT(first_name,' ',last_name) AS name FROM teachers ORDER BY last_name,first_name")
        return [(r["teacher_id"], r["name"]) for r in rows]


class CourseRepository(BaseRepository):
    def list(self, teacher_id: int | None = None, search: str = "", limit: int = 0, offset: int = 0) -> list[dict[str, Any]]:
        term = search.strip()
        p = f"%{term}%"
        teacher_clause = "" if teacher_id is None else " AND c.teacher_id=%s"
        params: list[Any] = [term, p, p, p]
        if teacher_id is not None:
            params.append(teacher_id)
        sql = f"""SELECT c.course_id,c.course_code,c.course_name,c.credits,c.teacher_id,
                       CONCAT(t.first_name,' ',t.last_name) AS teacher,
                       COUNT(DISTINCT e.student_id) AS enrolled,
                       ROUND(AVG(g.grade_value),2) AS avg_grade
                FROM courses c LEFT JOIN teachers t ON t.teacher_id=c.teacher_id
                LEFT JOIN enrollments e ON e.course_id=c.course_id
                LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
                WHERE (%s='' OR c.course_code LIKE %s OR c.course_name LIKE %s OR
                       COALESCE(CONCAT(t.first_name,' ',t.last_name),'') LIKE %s)
                {teacher_clause}
                GROUP BY c.course_id ORDER BY c.course_name"""
        if limit:
            sql += " LIMIT %s OFFSET %s"
            params += [limit, offset]
        return self.fetch_all(sql, tuple(params))

    def count(self, search: str = "", teacher_id: int | None = None) -> int:
        """Count courses, optionally scoped to one teacher (used for the
        teacher dashboard pagination metadata)."""
        term = search.strip()
        p = f"%{term}%"
        sql = """SELECT COUNT(*) AS total FROM courses c
               LEFT JOIN teachers t ON t.teacher_id=c.teacher_id
               WHERE (%s='' OR c.course_code LIKE %s OR c.course_name LIKE %s OR
                      COALESCE(CONCAT(t.first_name,' ',t.last_name),'') LIKE %s)"""
        params: list[Any] = [term, p, p, p]
        if teacher_id is not None:
            sql += " AND c.teacher_id=%s"
            params.append(teacher_id)
        row = self.fetch_one(sql, tuple(params))
        return int(row["total"]) if row else 0

    def get(self, course_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT * FROM courses WHERE course_id=%s", (course_id,))

    def create(self, data: dict[str, Any]) -> int:
        return self.execute(
            "INSERT INTO courses (course_code,course_name,credits,teacher_id) VALUES (%s,%s,%s,%s)",
            (data["course_code"], data["course_name"], data["credits"], data["teacher_id"]),
        )

    def update(self, course_id: int, data: dict[str, Any]) -> int:
        return self.execute(
            "UPDATE courses SET course_code=%s,course_name=%s,credits=%s,teacher_id=%s WHERE course_id=%s",
            (data["course_code"], data["course_name"], data["credits"], data["teacher_id"], course_id),
        )

    def delete(self, course_id: int) -> int:
        return self.execute("DELETE FROM courses WHERE course_id=%s", (course_id,))

    def analytics(self, course_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """SELECT c.course_id,c.course_code,c.course_name,
                      COUNT(DISTINCT e.student_id) enrollment_count,
                      ROUND(AVG(g.grade_value),2) average_grade,
                      MAX(g.grade_value) highest_grade,
                      MIN(g.grade_value) lowest_grade
               FROM courses c LEFT JOIN enrollments e ON e.course_id=c.course_id
               LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
               WHERE c.course_id=%s GROUP BY c.course_id""",
            (course_id,),
        )

    def students(self, course_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """SELECT e.enrollment_id,s.student_id,s.student_code,
                      CONCAT(s.first_name,' ',s.last_name) student_name,
                      s.email,e.enrollment_date,g.grade_value
               FROM enrollments e JOIN students s ON s.student_id=e.student_id
               LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
               WHERE e.course_id=%s ORDER BY g.grade_value IS NULL, g.grade_value DESC, s.last_name,s.first_name""",
            (course_id,),
        )

    def assigned_to(self, teacher_id: int, course_id: int) -> bool:
        row = self.fetch_one("SELECT course_id FROM courses WHERE course_id=%s AND teacher_id=%s", (course_id, teacher_id))
        return row is not None


class EnrollmentRepository(BaseRepository):
    def list_for_student(self, student_id: int, teacher_id: int | None = None) -> list[dict[str, Any]]:
        teacher_clause = "" if teacher_id is None else " AND c.teacher_id=%s"
        params = (student_id,) if teacher_id is None else (student_id, teacher_id)
        return self.fetch_all(
            f"""SELECT e.enrollment_id,c.course_id,c.course_code,c.course_name,
                      e.enrollment_date,g.grade_value
               FROM enrollments e JOIN courses c ON c.course_id=e.course_id
               LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
               WHERE e.student_id=%s {teacher_clause} ORDER BY c.course_name""",
            params,
        )

    def available_courses(self, student_id: int) -> list[tuple[int, str]]:
        rows = self.fetch_all(
            """SELECT c.course_id,c.course_name FROM courses c
               WHERE NOT EXISTS (SELECT 1 FROM enrollments e
                                 WHERE e.course_id=c.course_id AND e.student_id=%s)
               ORDER BY c.course_name""",
            (student_id,),
        )
        return [(r["course_id"], r["course_name"]) for r in rows]

    def get(self, enrollment_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """SELECT e.enrollment_id,e.student_id,e.course_id,c.teacher_id,
                      CONCAT(s.first_name,' ',s.last_name) AS student_name,
                      c.course_code
               FROM enrollments e JOIN courses c ON c.course_id=e.course_id
               JOIN students s ON s.student_id=e.student_id
               WHERE e.enrollment_id=%s""",
            (enrollment_id,),
        )

    def exists(self, student_id: int, course_id: int) -> bool:
        return self.fetch_one(
            "SELECT enrollment_id FROM enrollments WHERE student_id=%s AND course_id=%s",
            (student_id, course_id),
        ) is not None

    def create(self, student_id: int, course_id: int, enrollment_date: str) -> int:
        return self.execute(
            "INSERT INTO enrollments (student_id,course_id,enrollment_date) VALUES (%s,%s,%s)",
            (student_id, course_id, enrollment_date),
        )

    def delete(self, enrollment_id: int) -> int:
        return self.execute("DELETE FROM enrollments WHERE enrollment_id=%s", (enrollment_id,))


class GradeRepository(BaseRepository):
    def get(self, enrollment_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT grade_id,enrollment_id,grade_value,graded_date FROM grades WHERE enrollment_id=%s", (enrollment_id,))

    def upsert(self, enrollment_id: int, value: float, graded_date: str) -> int:
        return self.execute(
            """INSERT INTO grades (enrollment_id,grade_value,graded_date)
               VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE grade_value=VALUES(grade_value),graded_date=VALUES(graded_date)""",
            (enrollment_id, value, graded_date),
        )


class DashboardRepository(BaseRepository):
    def totals(self) -> dict[str, Any]:
        return self.fetch_one(
            """SELECT (SELECT COUNT(*) FROM students) students,
                      (SELECT COUNT(*) FROM teachers) teachers,
                      (SELECT COUNT(*) FROM courses) courses,
                      (SELECT COUNT(*) FROM enrollments) enrollments"""
        ) or {"students": 0, "teachers": 0, "courses": 0, "enrollments": 0}

    def grade_distribution(self, teacher_id: int | None = None) -> list[dict[str, Any]]:
        extra = "" if teacher_id is None else " AND c.teacher_id=%s"
        params: tuple[Any, ...] = () if teacher_id is None else (teacher_id,)
        return self.fetch_all(
            f"""SELECT CASE
                         WHEN g.grade_value >= 90 THEN 'A'
                         WHEN g.grade_value >= 80 THEN 'B'
                         WHEN g.grade_value >= 70 THEN 'C'
                         WHEN g.grade_value >= 60 THEN 'D'
                         ELSE 'F' END AS grade_band,
                       COUNT(*) AS total
                FROM grades g JOIN enrollments e ON e.enrollment_id=g.enrollment_id
                JOIN courses c ON c.course_id=e.course_id
                WHERE 1=1 {extra}
                GROUP BY grade_band ORDER BY grade_band""",
            params,
        )

    def recent_enrollments(self, teacher_id: int | None = None, limit: int = 8) -> list[dict[str, Any]]:
        extra = "" if teacher_id is None else " AND c.teacher_id=%s"
        params: tuple[Any, ...] = () if teacher_id is None else (teacher_id,)
        return self.fetch_all(
            f"""SELECT e.enrollment_date,s.student_code,
                       CONCAT(s.first_name,' ',s.last_name) student_name,
                       c.course_code,c.course_name
                FROM enrollments e JOIN students s ON s.student_id=e.student_id
                JOIN courses c ON c.course_id=e.course_id
                WHERE 1=1 {extra}
                ORDER BY e.enrollment_date DESC,e.enrollment_id DESC LIMIT {int(limit)}""",
            params,
        )

    def course_summary(self, teacher_id: int | None = None) -> list[dict[str, Any]]:
        extra = " WHERE c.teacher_id=%s" if teacher_id is not None else ""
        params: tuple[Any, ...] = () if teacher_id is None else (teacher_id,)
        return self.fetch_all(
            f"""SELECT c.course_code,c.course_name,COUNT(DISTINCT e.student_id) enrolled,
                       ROUND(AVG(g.grade_value),2) average_grade
                FROM courses c LEFT JOIN enrollments e ON e.course_id=c.course_id
                LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
                {extra} GROUP BY c.course_id ORDER BY enrolled DESC,c.course_name""",
            params,
        )



    def teacher_totals(self, teacher_id: int) -> dict[str, Any]:
        return self.fetch_one(
            """SELECT COUNT(DISTINCT c.course_id) courses,
                      COUNT(DISTINCT e.student_id) students,
                      COUNT(DISTINCT e.enrollment_id) enrollments
               FROM courses c LEFT JOIN enrollments e ON e.course_id=c.course_id
               WHERE c.teacher_id=%s""",
            (teacher_id,),
        ) or {"courses": 0, "students": 0, "enrollments": 0}

class UserRepository(BaseRepository):
    def list(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """SELECT u.id,u.username,u.role,u.is_active,u.teacher_id,u.created_at,
                      CONCAT(t.first_name,' ',t.last_name) teacher_name
               FROM users u LEFT JOIN teachers t ON t.teacher_id=u.teacher_id
               ORDER BY u.username"""
        )

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        return self.fetch_one(
            "SELECT id,username,password_hash,role,is_active,teacher_id FROM users WHERE username=%s",
            (username,),
        )

    def get(self, user_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT id,username,role,is_active,teacher_id FROM users WHERE id=%s", (user_id,))

    def create(self, username: str, password_hash: str, role: str, teacher_id: int | None) -> int:
        return self.execute(
            "INSERT INTO users (username,password_hash,role,teacher_id) VALUES (%s,%s,%s,%s)",
            (username, password_hash, role, teacher_id),
        )

    def set_active(self, user_id: int, is_active: bool) -> int:
        return self.execute("UPDATE users SET is_active=%s WHERE id=%s", (is_active, user_id))


class AuditLogRepository(BaseRepository):
    """Append-only access to audit_logs. No update/delete by design."""

    def record(
        self,
        connection,
        *,
        user_id: int | None,
        username: str,
        action: str,
        entity_type: str,
        entity_id: int | None,
        details: dict[str, Any] | None = None,
        status: str = "SUCCESS",
    ) -> None:
        """Write one audit row on the GIVEN connection so it commits or rolls
        back atomically with the operation it describes. status distinguishes
        successful changes (SUCCESS) from failures (FAILED, e.g. a database
        error) and rule rejections (REJECTED, e.g. permission denied)."""
        import json

        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO audit_logs
                   (user_id, username, action, entity_type, entity_id, status, details)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    user_id,
                    username,
                    action,
                    entity_type,
                    entity_id,
                    status,
                    json.dumps(details, default=str) if details else None,
                ),
            )

    def list(
        self,
        *,
        action: str = "",
        entity_type: str = "",
        username: str = "",
        status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if action.strip():
            clauses.append("action LIKE %s")
            params.append(f"%{action.strip()}%")
        if entity_type.strip():
            clauses.append("entity_type = %s")
            params.append(entity_type.strip())
        if username.strip():
            clauses.append("username LIKE %s")
            params.append(f"%{username.strip()}%")
        if status.strip():
            clauses.append("status = %s")
            params.append(status.strip().upper())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        return self.fetch_all(
            "SELECT * FROM audit_logs" + where + " ORDER BY created_at DESC, audit_id DESC LIMIT %s OFFSET %s",
            tuple(params),
        )

    def count(self, *, action: str = "", entity_type: str = "", username: str = "", status: str = "") -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if action.strip():
            clauses.append("action LIKE %s")
            params.append(f"%{action.strip()}%")
        if entity_type.strip():
            clauses.append("entity_type = %s")
            params.append(entity_type.strip())
        if username.strip():
            clauses.append("username LIKE %s")
            params.append(f"%{username.strip()}%")
        if status.strip():
            clauses.append("status = %s")
            params.append(status.strip().upper())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self.fetch_one("SELECT COUNT(*) AS total FROM audit_logs" + where, tuple(params))
        return int(row["total"]) if row else 0
