"""Typed Pydantic request/response contracts for the HTTP API.

Kept deliberately thin: these models validate HTTP input shape and give the
OpenAPI docs real types. Business-critical validation still lives in the
service layer so the desktop client shares the exact same rules.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(value: str, field: str) -> str:
    if not _DATE_RE.match(value):
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} is not a real calendar date") from error
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class StudentCreate(BaseModel):
    student_code: str = Field(min_length=2, max_length=30, examples=["STU-0001"])
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    enrollment_date: str

    @field_validator("enrollment_date")
    @classmethod
    def _date_ok(cls, value: str) -> str:
        return _valid_date(value, "Enrollment date")


class StudentUpdate(StudentCreate):
    pass


class TeacherCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    hire_date: str

    @field_validator("hire_date")
    @classmethod
    def _date_ok(cls, value: str) -> str:
        return _valid_date(value, "Hire date")


class TeacherUpdate(TeacherCreate):
    pass


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=2, max_length=30, examples=["BIO101"])
    course_name: str = Field(min_length=2, max_length=150)
    credits: int = Field(ge=1, le=6)
    teacher_id: int | None = None


class CourseUpdate(CourseCreate):
    pass


class EnrollmentCreate(BaseModel):
    course_id: int = Field(gt=0)
    enrollment_date: str

    @field_validator("enrollment_date")
    @classmethod
    def _date_ok(cls, value: str) -> str:
        return _valid_date(value, "Enrollment date")


class GradeUpdate(BaseModel):
    grade_value: float = Field(ge=0, le=100)
    graded_date: str

    @field_validator("graded_date")
    @classmethod
    def _date_ok(cls, value: str) -> str:
        return _valid_date(value, "Graded date")


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(pattern="^(ADMIN|TEACHER)$")
    teacher_id: int | None = None


class UserActiveUpdate(BaseModel):
    is_active: bool


class CsvPreviewRow(BaseModel):
    row: int
    student_code: str = ""
    error: str


class CsvImportResult(BaseModel):
    imported: int
    validated: int
    errors: list[CsvPreviewRow]


class Page(BaseModel, Generic[T]):
    """Standard pagination envelope for all list endpoints."""

    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=1)

    model_config = ConfigDict(from_attributes=True)

