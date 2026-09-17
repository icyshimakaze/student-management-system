"""PyQt6 dialogs. Business validation remains authoritative in services."""
from __future__ import annotations

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout,
)
from validation import ValidationError, email, identifier, name, required


def _parse_qdate(value):
    if isinstance(value, QDate):
        return value
    parsed = QDate.fromString(str(value), "yyyy-MM-dd")
    return parsed if parsed.isValid() else QDate.currentDate()


class ValidatedDialog(QDialog):
    def show_validation_error(self, error: Exception) -> None:
        QMessageBox.warning(self, "Invalid information", str(error))


class StudentDialog(ValidatedDialog):
    def __init__(self, parent=None, student=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Student" if student else "Add Student")
        self.setMinimumWidth(380)
        self.student_code_input = QLineEdit()
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.email_input = QLineEdit()
        self.enrollment_date_input = QDateEdit()
        self.enrollment_date_input.setCalendarPopup(True)
        self.enrollment_date_input.setDate(QDate.currentDate())
        if student:
            for widget, key in [(self.student_code_input, "student_code"), (self.first_name_input, "first_name"), (self.last_name_input, "last_name"), (self.email_input, "email")]:
                widget.setText(str(student.get(key, "")))
            self.enrollment_date_input.setDate(_parse_qdate(student.get("enrollment_date")))
        form = QFormLayout()
        form.addRow("Student ID:", self.student_code_input)
        form.addRow("First name:", self.first_name_input)
        form.addRow("Last name:", self.last_name_input)
        form.addRow("Email:", self.email_input)
        form.addRow("Enrollment date:", self.enrollment_date_input)
        self._finish(form)

    def _on_accept(self):
        try:
            identifier(self.student_code_input.text(), "Student ID")
            name(self.first_name_input.text(), "First name")
            name(self.last_name_input.text(), "Last name")
            email(self.email_input.text())
            required(self.enrollment_date_input.date().toString("yyyy-MM-dd"), "Enrollment date")
        except ValidationError as error:
            self.show_validation_error(error)
            return
        self.accept()

    def get_data(self):
        return {"student_code": self.student_code_input.text().strip(), "first_name": self.first_name_input.text().strip(), "last_name": self.last_name_input.text().strip(), "email": self.email_input.text().strip(), "enrollment_date": self.enrollment_date_input.date().toString("yyyy-MM-dd")}

    def _finish(self, form):
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept); buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)


class TeacherDialog(ValidatedDialog):
    def __init__(self, parent=None, teacher=None):
        super().__init__(parent); self.setWindowTitle("Edit Teacher" if teacher else "Add Teacher"); self.setMinimumWidth(380)
        self.first_name_input=QLineEdit(); self.last_name_input=QLineEdit(); self.email_input=QLineEdit(); self.hire_date_input=QDateEdit(); self.hire_date_input.setCalendarPopup(True); self.hire_date_input.setDate(QDate.currentDate())
        if teacher:
            self.first_name_input.setText(teacher.get("first_name", "")); self.last_name_input.setText(teacher.get("last_name", "")); self.email_input.setText(teacher.get("email", "")); self.hire_date_input.setDate(_parse_qdate(teacher.get("hire_date")))
        form=QFormLayout(); form.addRow("First name:",self.first_name_input); form.addRow("Last name:",self.last_name_input); form.addRow("Email:",self.email_input); form.addRow("Hire date:",self.hire_date_input); self._finish(form)
    def _on_accept(self):
        try: name(self.first_name_input.text(),"First name"); name(self.last_name_input.text(),"Last name"); email(self.email_input.text())
        except ValidationError as error: self.show_validation_error(error); return
        self.accept()
    def get_data(self): return {"first_name":self.first_name_input.text().strip(),"last_name":self.last_name_input.text().strip(),"email":self.email_input.text().strip(),"hire_date":self.hire_date_input.date().toString("yyyy-MM-dd")}
    def _finish(self,form):
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self._on_accept); buttons.rejected.connect(self.reject); layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)


class CourseDialog(ValidatedDialog):
    def __init__(self,parent=None,teachers=None,course=None):
        super().__init__(parent); self.setWindowTitle("Edit Course" if course else "Add Course"); self.setMinimumWidth(400)
        self.course_name_input=QLineEdit(); self.course_code_input=QLineEdit(); self.credits_input=QSpinBox(); self.credits_input.setRange(1,6); self.credits_input.setValue(3); self.teacher_combo=QComboBox(); self.teacher_combo.addItem("— Unassigned —",None)
        for teacher_id,name_text in teachers or []: self.teacher_combo.addItem(name_text,teacher_id)
        if course:
            self.course_code_input.setText(course.get("course_code","")); self.course_name_input.setText(course.get("course_name","")); self.credits_input.setValue(int(course.get("credits",3))); idx=self.teacher_combo.findData(course.get("teacher_id")); self.teacher_combo.setCurrentIndex(idx if idx>=0 else 0)
        form=QFormLayout(); form.addRow("Course code:",self.course_code_input); form.addRow("Course name:",self.course_name_input); form.addRow("Credits:",self.credits_input); form.addRow("Teacher:",self.teacher_combo)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self._on_accept); buttons.rejected.connect(self.reject); layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
    def _on_accept(self):
        try: identifier(self.course_code_input.text(),"Course code"); required(self.course_name_input.text(),"Course name")
        except ValidationError as error: self.show_validation_error(error); return
        self.accept()
    def get_data(self): return {"course_code":self.course_code_input.text().strip(),"course_name":self.course_name_input.text().strip(),"credits":self.credits_input.value(),"teacher_id":self.teacher_combo.currentData()}


class EnrollDialog(QDialog):
    def __init__(self,parent=None,available_courses=None):
        super().__init__(parent); self.setWindowTitle("Enroll in Course"); self.setMinimumWidth(340); available_courses=available_courses or []; self.course_combo=QComboBox();
        for course_id,name_text in available_courses: self.course_combo.addItem(name_text,course_id)
        self.enrollment_date_input=QDateEdit(); self.enrollment_date_input.setCalendarPopup(True); self.enrollment_date_input.setDate(QDate.currentDate())
        form=QFormLayout()
        if available_courses: form.addRow("Course:",self.course_combo); form.addRow("Enrollment date:",self.enrollment_date_input)
        else: form.addRow(QLabel("This student is already enrolled in every course."))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        if not available_courses: buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
    def get_data(self): return {"course_id":self.course_combo.currentData(),"enrollment_date":self.enrollment_date_input.date().toString("yyyy-MM-dd")}


class GradeDialog(QDialog):
    def __init__(self,parent=None,current_grade=None):
        super().__init__(parent); self.setWindowTitle("Set Grade"); self.setMinimumWidth(300); self.grade_input=QDoubleSpinBox(); self.grade_input.setRange(0,100); self.grade_input.setDecimals(2); self.grade_input.setSingleStep(.5); self.graded_date_input=QDateEdit(); self.graded_date_input.setCalendarPopup(True); self.graded_date_input.setDate(QDate.currentDate())
        if current_grade is not None: self.grade_input.setValue(float(current_grade))
        form=QFormLayout(); form.addRow("Grade (0-100):",self.grade_input); form.addRow("Graded date:",self.graded_date_input); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
    def get_data(self): return {"grade_value":self.grade_input.value(),"graded_date":self.graded_date_input.date().toString("yyyy-MM-dd")}


class UserDialog(ValidatedDialog):
    def __init__(self,parent=None,teachers=None):
        super().__init__(parent); self.setWindowTitle("Create User"); self.setMinimumWidth(400); self.username_input=QLineEdit(); self.password_input=QLineEdit(); self.password_input.setEchoMode(QLineEdit.EchoMode.Password); self.role_combo=QComboBox(); self.role_combo.addItems(["ADMIN","TEACHER"]); self.teacher_combo=QComboBox(); self.teacher_combo.addItem("— Select teacher —",None)
        for teacher_id,name_text in teachers or []: self.teacher_combo.addItem(name_text,teacher_id)
        self.role_combo.currentTextChanged.connect(self._role_changed); self._role_changed(self.role_combo.currentText())
        form=QFormLayout(); form.addRow("Username:",self.username_input); form.addRow("Password:",self.password_input); form.addRow("Role:",self.role_combo); form.addRow("Teacher profile:",self.teacher_combo); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self._on_accept); buttons.rejected.connect(self.reject); layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
    def _role_changed(self,role): self.teacher_combo.setEnabled(role=="TEACHER")
    def _on_accept(self):
        try: identifier(self.username_input.text(),"Username"); required(self.password_input.text(),"Password")
        except ValidationError as error: self.show_validation_error(error); return
        self.accept()
    def get_data(self): return {"username":self.username_input.text().strip(),"password":self.password_input.text(),"role":self.role_combo.currentText(),"teacher_id":self.teacher_combo.currentData() if self.role_combo.currentText()=="TEACHER" else None}


class AboutDialog(QMessageBox):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("About"); self.setText("<b>Student Management System</b><br><br>PyQt6 desktop administration software backed by a normalized MySQL database.<br>Architecture: UI → Services → Repositories → MySQL.<br><br>See README.md and database/queries.sql for the implementation and SQL portfolio."); self.setStandardButtons(QMessageBox.StandardButton.Ok)
