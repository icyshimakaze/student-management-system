"""Central business validation used by services and optional UI feedback."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,29}$")
NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .'-]{1,99}$")


class ValidationError(ValueError):
    """Raised when supplied business data is not acceptable."""


def required(value: str | None, label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{label} is required.")
    return value


def email(value: str | None) -> str:
    value = required(value, "Email").lower()
    if not EMAIL_RE.fullmatch(value):
        raise ValidationError("Enter a valid email address.")
    return value


def identifier(value: str | None, label: str) -> str:
    value = required(value, label)
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValidationError(f"{label} must be 3-30 characters and use letters, numbers, '_' or '-'.")
    return value


def name(value: str | None, label: str) -> str:
    value = required(value, label)
    if not NAME_RE.fullmatch(value):
        raise ValidationError(f"{label} contains unsupported characters or is too long.")
    return value


def credits(value: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Credits must be a whole number between 1 and 6.") from exc
    if not 1 <= value <= 6:
        raise ValidationError("Credits must be between 1 and 6.")
    return value


def grade(value: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Grade must be a number between 0 and 100.") from exc
    if not 0 <= value <= 100:
        raise ValidationError("Grade must be between 0 and 100.")
    return round(value, 2)
