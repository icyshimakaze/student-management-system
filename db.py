"""Database connection handling for the Student Management System."""
import mysql.connector

from config import DatabaseSettings


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
