"""Create the initial user in the Dockerized development database.

Prompts for credentials with getpass so no password lands in the shell
history or in source. Run after `docker compose up -d`:

    python scripts/create_docker_user.py
"""
import sys
from getpass import getpass
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import DatabaseConnection
from repositories import TeacherRepository, UserRepository
from validation import ValidationError, identifier, required


def main() -> None:
    db = DatabaseConnection()
    username = identifier(input("Username: "), "Username")
    password = required(getpass("Password: "), "Password")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters long.")
    role = input("Role (ADMIN/TEACHER): ").strip().upper()
    if role not in {"ADMIN", "TEACHER"}:
        raise SystemExit("Role must be ADMIN or TEACHER.")
    teacher_id = None
    if role == "TEACHER":
        raw = input("Teacher ID: ").strip()
        try:
            teacher_id = int(raw)
        except ValueError:
            raise SystemExit("Teacher ID must be an integer.")
        if not TeacherRepository(db).exists(teacher_id):
            raise SystemExit("Teacher ID does not exist.")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    UserRepository(db).create(username, password_hash, role, teacher_id)
    print("User created successfully.")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as error:
        raise SystemExit(str(error))
