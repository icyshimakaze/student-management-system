"""Configuration loaded from the environment; no credentials live in source."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _safe_port(raw: str | None) -> int:
    """Parse DB_PORT tolerantly; a bad value must not crash startup."""
    try:
        port = int(raw or "3306")
    except ValueError:
        port = 3306
    return port if 1 <= port <= 65535 else 3306


@dataclass(frozen=True)
class DatabaseSettings:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = _safe_port(os.getenv("DB_PORT"))
    user: str = os.getenv("DB_USER", "root")
    password: str = os.getenv("DB_PASSWORD", "")
    name: str = os.getenv("DB_NAME", "student_management")
