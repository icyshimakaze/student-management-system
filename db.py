"""Database connection handling for the Student Management System."""
import contextlib

import mysql.connector

from config import DatabaseSettings

# mysql-connector loads error-message translations with dynamic imports that
# PyInstaller cannot detect (see StudentManagementSystem.spec hiddenimports).
# On top of bundling the locale modules, force the import here so a failure is
# loud at startup instead of crashing deep inside error handling at runtime.
with contextlib.suppress(ImportError):
    from mysql.connector.locales import eng  # noqa: F401


class DatabaseConnection:
    """Create short-lived MySQL connections from environment configuration."""

    def __init__(self, settings: DatabaseSettings | None = None):
        self.settings = settings or DatabaseSettings()

    def connect(self):
        return mysql.connector.connect(
            host=self.settings.host,
            port=self.settings.port,
            user=self.settings.user,
            password=self.settings.password,
            database=self.settings.name,
            autocommit=False,
        )
