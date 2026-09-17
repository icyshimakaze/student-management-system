"""Application entry point and authenticated window."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import mysql.connector
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout

from db import DatabaseConnection
from dialogs import AboutDialog
from services import AuthService, ServiceBundle, Session, ValidationError
from tabs import DashboardTab, CoursesTab, StudentsTab, TeachersTab, UsersTab

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
            self.tabs.addTab(TeachersTab(self.services),"Teachers"); self.tabs.addTab(UsersTab(self.services),"Users")
        self.tabs.currentChanged.connect(self._refresh_tab); self.setCentralWidget(self.tabs); self.statusBar().showMessage(f"Signed in as {session.username} · {session.role}")
    def _refresh_tab(self,index):
        widget=self.tabs.widget(index)
        if hasattr(widget,"load_data"):
            try: widget.load_data()
            except Exception: LOGGER.exception("Could not refresh tab")
    def logout(self):
        self.close()
    def closeEvent(self,event):
        LOGGER.info("Application window closed for user_id=%s",self.session.user_id); event.accept()


def load_stylesheet() -> str:
    path=Path(__file__).with_name("resources") / "app.qss"
    try: return path.read_text(encoding="utf-8")
    except OSError: return ""


def main() -> None:
    logging.basicConfig(filename="student_management.log",level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app=QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(load_stylesheet())
    db=DatabaseConnection()
    try:
        connection=db.connect(); connection.close()
    except mysql.connector.Error:
        LOGGER.exception("Initial database connectivity check failed")
        QMessageBox.critical(None,"Database Connection Failed","Could not connect to MySQL. Check that MySQL is running and DB_* values in .env are correct.")
        return
    login=LoginDialog(AuthService(db))
    if login.exec()!=QDialog.DialogCode.Accepted or login.session is None: return
    window=MainWindow(db,login.session); window.show(); sys.exit(app.exec())


if __name__=="__main__": main()
