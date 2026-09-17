"""Create an initial user from the terminal without storing its password."""
from getpass import getpass

from db import DatabaseConnection
from repositories import UserRepository, TeacherRepository
from validation import ValidationError, identifier, required
import bcrypt


def main():
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
        try: teacher_id = int(raw)
        except ValueError: raise SystemExit("Teacher ID must be an integer.")
        if not TeacherRepository(DatabaseConnection()).exists(teacher_id): raise SystemExit("Teacher ID does not exist.")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    UserRepository(DatabaseConnection()).create(username,password_hash,role,teacher_id)
    print("User created successfully.")


if __name__ == "__main__":
    try: main()
    except ValidationError as error: raise SystemExit(str(error))
