"""Shared integration-test helpers.

These tests need a reachable MySQL server configured through TEST_DB_*
environment variables (see .env.example for the full list). When no server
answers, the whole integration suite skips itself so that running
`pytest` on a machine without MySQL stays green.
"""
from __future__ import annotations

import os
from pathlib import Path

import mysql.connector
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_DB = {
    "host": os.getenv("TEST_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("TEST_DB_PORT", "3306")),
    "user": os.getenv("TEST_DB_USER", "root"),
    "password": os.getenv("TEST_DB_PASSWORD", ""),
    "database": os.getenv("TEST_DB_NAME", "student_management_test"),
}

# MySQL treats TEST_DB_PASSWORD="" as "no password", which matches what a
# plain env var default gives us.
if TEST_DB["password"] == "":
    TEST_DB["password"] = os.getenv("TEST_DB_PASSWORD", "")


def _connect(database: str | None = None):
    cfg = dict(TEST_DB)
    if database is not None:
        cfg["database"] = database
    return mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=database,
        autocommit=False,
    )


def mysql_available() -> bool:
    try:
        connection = _connect(None)
    except mysql.connector.Error:
        return False
    connection.close()
    return True


def _split_sql_statements(sql: str) -> list[str]:
    """Split a .sql script into statements for cursor.execute().

    schema.sql and seed_data.sql only contain full-line comments and no
    semicolons inside string literals, so dropping comment/blank lines and
    splitting on ';' is sufficient. mysql-connector-python does not accept
    multi-statement scripts in cursor.execute()."""
    lines = [
        line for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def load_schema(database: str) -> None:
    """Apply schema.sql + seed_data.sql to the given database."""
    schema_sql = (PROJECT_ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    schema_sql = "\n".join(
        line for line in schema_sql.splitlines()
        if not line.strip().upper().startswith(("CREATE DATABASE", "USE "))
    )
    seed_sql = (PROJECT_ROOT / "database" / "seed_data.sql").read_text(encoding="utf-8")
    connection = _connect(None)
    try:
        cursor = connection.cursor()
        cursor.execute(f"DROP DATABASE IF EXISTS {database}")
        cursor.execute(f"CREATE DATABASE {database} CHARACTER SET utf8mb4")
        cursor.close()
        connection.commit()
    finally:
        connection.close()
    connection = _connect(database)
    try:
        cursor = connection.cursor()
        for statement in _split_sql_statements(schema_sql) + _split_sql_statements(seed_sql):
            cursor.execute(statement)
        cursor.close()
        connection.commit()
    finally:
        connection.close()


# One shared, freshly-initialized database per pytest session.
@pytest.fixture(scope="session")
def test_db():
    if not mysql_available():
        pytest.skip("No reachable MySQL server for integration tests; set TEST_DB_* to enable them")
    load_schema(TEST_DB["database"])
    yield TEST_DB["database"]


@pytest.fixture()
def db(test_db):
    """A connection wrapper matching the app's DatabaseConnection interface."""
    class _DB:
        def connect(self):
            return _connect(test_db)

    return _DB()


@pytest.fixture()
def unique_code():
    """Unique student codes so parallel/repeat runs never hit the UNIQUE constraint."""
    counter = {"n": 0}

    def _next(prefix: str = "IT-STU") -> str:
        counter["n"] += 1
        return f"{prefix}-{os.getpid()}-{counter['n']:04d}"

    return _next
