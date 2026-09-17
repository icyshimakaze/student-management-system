from repositories import BaseRepository


class FakeCursor:
    def __init__(self): self.calls=[]; self.lastrowid=123; self.closed=False
    def execute(self,sql,params): self.calls.append((sql,params))
    def close(self): self.closed=True


class FakeConnection:
    def __init__(self): self.cursor_obj=FakeCursor(); self.commits=0; self.rollbacks=0; self.closed=False
    def cursor(self,**kwargs): return self.cursor_obj
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closed=True


class FakeDB:
    def __init__(self, connection): self.connection=connection
    def connect(self): return self.connection


def test_execute_uses_parameterized_sql_and_commits():
    conn=FakeConnection(); repo=BaseRepository(FakeDB(conn))
    row_id=repo.execute("DELETE FROM students WHERE student_id=%s",(9,))
    assert row_id == 123
    assert conn.cursor_obj.calls == [("DELETE FROM students WHERE student_id=%s",(9,))]
    assert conn.commits == 1 and conn.rollbacks == 0


def test_transaction_rolls_back_on_failure():
    conn=FakeConnection(); repo=BaseRepository(FakeDB(conn))
    try:
        with repo.transaction() as (_, cursor):
            cursor.execute("UPDATE students SET email=%s WHERE student_id=%s",("x@example.com",1))
            raise RuntimeError("boom")
    except RuntimeError: pass
    assert conn.commits == 0 and conn.rollbacks == 1
