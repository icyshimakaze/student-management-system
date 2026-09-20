"""Application entry point and authenticated window."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from PyQt6.QtGui import QAction, QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from config import DatabaseSettings
from db import DatabaseConnection
from dialogs import AboutDialog
from services import AuthService, ServiceBundle, Session, ValidationError
from tabs import AuditLogTab, CoursesTab, DashboardTab, StudentsTab, TeachersTab, UsersTab

LOGGER = logging.getLogger(__name__)


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__(); self.auth_service=auth_service; self.session: Session|None=None; self.setWindowTitle("Sign in — Student Management System"); self.setMinimumWidth(380)
        self.username=QLineEdit(); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.password.returnPressed.connect(self._sign_in)
        form=QFormLayout(); form.addRow("Username:",self.username); form.addRow("Password:",self.password); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self._sign_in); buttons.rejected.connect(self.reject); hint=QLabel("Sign in with an active administrator or teacher account."); hint.setObjectName("muted")
        lay=QVBoxLayout(self); lay.addWidget(hint); lay.addLayout(form); lay.addWidget(buttons)
    def _sign_in(self):
        try: self.session=self.auth_service.authenticate(self.username.text(),self.password.text())
        except (ValidationError,mysql.connector.Error) as error:
            LOGGER.info("Login rejected")
            QMessageBox.warning(self,"Unable to sign in",str(error) if isinstance(error,ValidationError) else "The authentication service is unavailable.")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self,db,session:Session):
        super().__init__(); self.db=db; self.session=session; self.services=ServiceBundle(db,session); self.setWindowTitle(f"Student Management System — {session.username} ({session.role})"); self.setMinimumSize(1100,700)
        file_menu=self.menuBar().addMenu("&Session"); logout=QAction("Log out",self); logout.triggered.connect(self.logout); file_menu.addAction(logout)
        help_menu=self.menuBar().addMenu("&Help"); about=QAction("About",self); about.triggered.connect(lambda:AboutDialog(self).exec()); help_menu.addAction(about)
        self.tabs=QTabWidget(); self.dashboard=DashboardTab(self.services,session.is_admin); self.tabs.addTab(self.dashboard,"Dashboard")
        if session.is_admin: self.tabs.addTab(StudentsTab(self.services),"Students")
        self.tabs.addTab(CoursesTab(self.services),"Courses")
        if session.is_admin:
            self.tabs.addTab(TeachersTab(self.services),"Teachers"); self.tabs.addTab(UsersTab(self.services),"Users"); self.tabs.addTab(AuditLogTab(self.services),"Audit Log")
        self.tabs.currentChanged.connect(self._refresh_tab); self.setCentralWidget(self.tabs); self.statusBar().showMessage(f"Signed in as {session.username} · {session.role}")
        self.showMaximized()
    def _refresh_tab(self,index):
        widget=self.tabs.widget(index)
        if hasattr(widget,"load_data"):
            try: widget.load_data()
            except Exception: LOGGER.exception("Could not refresh tab")
    def logout(self):
        self.close()
    def closeEvent(self,event):
        LOGGER.info("Application window closed for user_id=%s",self.session.user_id); event.accept()


def _resource_path(relative: str) -> Path:
    """Locate a bundled resource both in source trees and PyInstaller builds."""
    # PyInstaller onefile mode unpacks data files to sys._MEIPASS.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / relative


def load_stylesheet() -> str:
    try: return _resource_path("resources/app.qss").read_text(encoding="utf-8")
    except OSError: return ""


def load_app_icon() -> QIcon:
    """Application icon, bundled from the same brand asset as the web app."""
    icon = QIcon(str(_resource_path("resources/brand-icon.png")))
    if icon.isNull():
        LOGGER.warning("Brand icon resource not found; using default window icon")
    return icon


def _light_palette() -> QPalette:
    """Force a light palette so the app stays readable in Windows dark mode.

    The stylesheet assumes light surfaces; without this, system dark mode
    makes text white-on-white and table rows render as black patches.
    """
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f5f7fb"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1a2233"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#fafbfc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1a2233"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1a2233"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#e8eef8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1a2233"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1a2233"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a93a6"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#9aa2b1"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#9aa2b1"))
    return palette


def _log_file() -> Path:
    """Keep the log writable when the exe lives in a read-only folder."""
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "StudentManagementSystem"
        base.mkdir(parents=True, exist_ok=True)
        return base / "student_management.log"
    return Path("student_management.log")


def _env_file_path() -> Path:
    """Where the app persists user-provided settings in frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / ".env"
    return Path(__file__).parent / ".env"


class DatabaseSetupDialog(QDialog):
    """First-run helper: collect MySQL settings and save them to .env.

    Shown when the configured database is unreachable, so a non-technical
    user can point the app at any MySQL server without editing files.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to MySQL")
        self.setMinimumWidth(400)
        instruction = QLabel(
            "The app could not reach its MySQL database.\n"
            "Enter your MySQL server details below — they will be saved for future runs."
        )
        instruction.setWordWrap(True)
        self.host = QLineEdit(os.getenv("DB_HOST", "localhost"))
        self.port = QLineEdit(os.getenv("DB_PORT", "3306"))
        self.user = QLineEdit(os.getenv("DB_USER", "root"))
        self.password = QLineEdit(os.getenv("DB_PASSWORD", ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.database = QLineEdit(os.getenv("DB_NAME", "student_management"))
        form = QFormLayout()
        form.addRow("Host:", self.host)
        form.addRow("Port:", self.port)
        form.addRow("User:", self.user)
        form.addRow("Password:", self.password)
        form.addRow("Database:", self.database)
        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #b42318;")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_test)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(instruction)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)

    def _save_and_test(self) -> None:
        values = {
            "DB_HOST": self.host.text().strip(),
            "DB_PORT": self.port.text().strip() or "3306",
            "DB_USER": self.user.text().strip(),
            "DB_PASSWORD": self.password.text(),
            "DB_NAME": self.database.text().strip(),
        }
        if not values["DB_HOST"] or not values["DB_USER"] or not values["DB_NAME"]:
            self.error.setText("Host, user and database are required.")
            return
        test = DatabaseConnection(DatabaseSettings(**{
            "host": values["DB_HOST"],
            "port": int(values["DB_PORT"]),
            "user": values["DB_USER"],
            "password": values["DB_PASSWORD"],
            "name": values["DB_NAME"],
        }))
        try:
            connection = test.connect()
            connection.close()
        except mysql.connector.Error as error:
            LOGGER.info("Database setup dialog: connection test failed")
            self.error.setText(f"Could not connect: {error.msg if hasattr(error, 'msg') else error}")
            return
        # Persist for future launches; never logs the password.
        env_path = _env_file_path()
        lines = [f"{key}={value}\n" for key, value in values.items()]
        try:
            env_path.write_text("".join(lines), encoding="utf-8")
        except OSError:
            # Read-only install dir: fall back to per-user app data.
            base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "StudentManagementSystem"
            base.mkdir(parents=True, exist_ok=True)
            env_path = base / ".env"
            env_path.write_text("".join(lines), encoding="utf-8")
        # Re-read so the current session uses the saved values.
        load_dotenv(env_path, override=True)
        self.accept()


def main() -> None:
    logging.basicConfig(filename=_log_file(),level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    def _handle_unexpected(exc_type, exc_value, exc_tb):
        """Last-resort handler: log details, show a friendly message, never a raw traceback."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb); return
        LOGGER.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        try:
            box=QMessageBox(QMessageBox.Icon.Critical,"Unexpected error","Something went wrong and the application must close.\n\nTechnical details were written to the log file.")
            box.exec()
        except Exception:
            pass
    sys.excepthook=_handle_unexpected
    app=QApplication(sys.argv); app.setStyle("Fusion"); app.setPalette(_light_palette()); app.setStyleSheet(load_stylesheet()); app.setWindowIcon(load_app_icon())
    db=DatabaseConnection()
    try:
        connection=db.connect(); connection.close()
    except mysql.connector.Error:
        LOGGER.info("Initial database connectivity check failed; offering setup dialog")
        setup=DatabaseSetupDialog()
        if setup.exec()!=QDialog.DialogCode.Accepted:
            return
        db=DatabaseConnection()  # reload settings from the just-saved .env
        try:
            connection=db.connect(); connection.close()
        except mysql.connector.Error:
            LOGGER.exception("Database still unreachable after setup dialog")
            QMessageBox.critical(None,"Database Connection Failed","Could not connect to MySQL even with the provided settings. Please verify the server is running and reachable.")
            return
    login=LoginDialog(AuthService(db))
    if login.exec()!=QDialog.DialogCode.Accepted or login.session is None: return
    window=MainWindow(db,login.session); window.show(); sys.exit(app.exec())


if __name__=="__main__": main()
