"""PyQt6 screens. Widgets call services; SQL is intentionally absent here."""
from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from dialogs import CourseDialog, EnrollDialog, GradeDialog, StudentDialog, TeacherDialog, UserDialog
from services import ServiceBundle, PermissionDenied, ValidationError

LOGGER = logging.getLogger(__name__)


def show_error(parent: QWidget, error: Exception) -> None:
    if isinstance(error, (PermissionDenied, ValidationError)):
        QMessageBox.warning(parent, "Operation not allowed", str(error))
    else:
        LOGGER.exception("UI operation failed")
        QMessageBox.critical(parent, "Operation failed", "The operation could not be completed. Check the application log for technical details.")


def confirm(parent: QWidget, title: str, text: str) -> bool:
    return QMessageBox.question(parent, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


def configure_table(table: QTableWidget, stretch_columns: tuple[int, ...] = ()) -> None:
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    for col in stretch_columns:
        table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)


class DashboardTab(QWidget):
    def __init__(self, services: ServiceBundle, is_admin: bool):
        super().__init__(); self.services=services; self.is_admin=is_admin
        title=QLabel("Dashboard"); title.setObjectName("pageTitle")
        self.cards=QGridLayout(); self.card_values=[]
        for idx,label in enumerate(["Students","Teachers","Courses","Enrollments"]):
            box=QGroupBox(label); value=QLabel("—"); value.setObjectName("metricValue"); lay=QVBoxLayout(box); lay.addWidget(value); self.cards.addWidget(box,0,idx); self.card_values.append(value)
        self.course_table=QTableWidget(); self.course_table.setColumnCount(4); self.course_table.setHorizontalHeaderLabels(["Course","Name","Enrolled","Average grade"]); configure_table(self.course_table,(1,))
        self.recent_table=QTableWidget(); self.recent_table.setColumnCount(4); self.recent_table.setHorizontalHeaderLabels(["Date","Student","Course code","Course"]); configure_table(self.recent_table,(3,))
        self.grade_table=QTableWidget(); self.grade_table.setColumnCount(2); self.grade_table.setHorizontalHeaderLabels(["Grade band","Count"]); configure_table(self.grade_table)
        grid=QGridLayout(); grid.addWidget(self._section("Course overview",self.course_table),0,0); grid.addWidget(self._section("Recent enrollments",self.recent_table),0,1); grid.addWidget(self._section("Grade distribution",self.grade_table),0,2)
        layout=QVBoxLayout(self); layout.addWidget(title); layout.addLayout(self.cards); layout.addLayout(grid)
        self.load_data()
    def _section(self,title,widget):
        box=QGroupBox(title); lay=QVBoxLayout(box); lay.addWidget(widget); return box
    def load_data(self):
        totals=self.services.dashboard.summary()
        for i,key in enumerate(["students","teachers","courses","enrollments"]): self.card_values[i].setText(str(totals.get(key,0)))
        self._fill(self.course_table,self.services.dashboard.course_summary(),["course_code","course_name","enrolled","average_grade"],lambda v: "—" if v is None else str(v))
        self._fill(self.recent_table,self.services.dashboard.recent_enrollments(),["enrollment_date","student_name","course_code","course_name"])
        self._fill(self.grade_table,self.services.dashboard.grade_distribution(),["grade_band","total"])
    @staticmethod
    def _fill(table,rows,keys,formatter=str):
        table.setRowCount(0)
        for r,row in enumerate(rows):
            table.insertRow(r)
            for c,key in enumerate(keys): table.setItem(r,c,QTableWidgetItem(formatter(row.get(key))))


class StudentProfileDialog(QDialog):
    def __init__(self,parent,profile):
        super().__init__(parent); student=profile["student"]; self.setWindowTitle(f"Student Profile — {student['student_code']}"); self.setMinimumSize(650,420)
        info=QLabel(f"<b>{student['first_name']} {student['last_name']}</b> · {student['student_code']}<br>{student['email']}<br>Enrolled: {student['enrollment_date']}<br><b>Average grade:</b> {profile['average_grade'] if profile['average_grade'] is not None else '—'}")
        table=QTableWidget(); table.setColumnCount(5); table.setHorizontalHeaderLabels(["Course","Name","Enrolled","Grade","Graded"]); configure_table(table,(1,))
        for r,row in enumerate(profile["courses"]):
            table.insertRow(r); vals=[row["course_code"],row["course_name"],str(row["enrollment_date"]),"—" if row["grade_value"] is None else f"{float(row['grade_value']):.2f}","—" if row["graded_date"] is None else str(row["graded_date"])]
            for c,v in enumerate(vals): table.setItem(r,c,QTableWidgetItem(v))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept); lay=QVBoxLayout(self); lay.addWidget(info); lay.addWidget(table); lay.addWidget(buttons)


class EnrollmentManagerDialog(QDialog):
    def __init__(self,parent,services:ServiceBundle,student_id,student_name):
        super().__init__(parent); self.services=services; self.student_id=student_id; self.setWindowTitle(f"Enrollments — {student_name}"); self.setMinimumSize(600,380)
        self.table=QTableWidget(); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["Course","Code","Enrollment date","Grade"]); configure_table(self.table,(0,))
        enroll=QPushButton("Enroll in course"); grade=QPushButton("Set grade"); remove=QPushButton("Remove enrollment"); close=QPushButton("Close")
        enroll.clicked.connect(self.enroll); grade.clicked.connect(self.set_grade); remove.clicked.connect(self.remove); close.clicked.connect(self.accept)
        row=QHBoxLayout(); [row.addWidget(b) for b in (enroll,grade,remove)]; row.addStretch(); row.addWidget(close); lay=QVBoxLayout(self); lay.addWidget(self.table); lay.addLayout(row); self.load()
    def load(self):
        rows=self.services.enrollments.list_for_student(self.student_id); self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[row["course_name"],row["course_code"],str(row["enrollment_date"]),"—" if row["grade_value"] is None else f"{float(row['grade_value']):.2f}"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
            self.table.item(r,0).setData(Qt.ItemDataRole.UserRole,row["enrollment_id"])
    def selected(self):
        item=self.table.item(self.table.currentRow(),0) if self.table.currentRow()>=0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None
    def enroll(self):
        try: available=self.services.enrollments.available_courses(self.student_id)
        except Exception as e: show_error(self,e); return
        dialog=EnrollDialog(self,available)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try: data=dialog.get_data(); self.services.enrollments.create(self.student_id,int(data["course_id"]),data["enrollment_date"]); self.load()
        except Exception as e: show_error(self,e)
    def set_grade(self):
        enrollment_id=self.selected()
        if enrollment_id is None: QMessageBox.information(self,"No selection","Select an enrollment first."); return
        try: current=self.services.grades.get(int(enrollment_id)); dialog=GradeDialog(self,current.get("grade_value") if current else None)
        except Exception as e: show_error(self,e); return
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try: data=dialog.get_data(); self.services.grades.set_grade(int(enrollment_id),data["grade_value"],data["graded_date"]); self.load()
        except Exception as e: show_error(self,e)
    def remove(self):
        enrollment_id=self.selected()
        if enrollment_id is None: QMessageBox.information(self,"No selection","Select an enrollment first."); return
        if not confirm(self,"Remove enrollment","Remove this enrollment? Its grade will also be removed by the database relationship."): return
        try: self.services.enrollments.delete(int(enrollment_id)); self.load()
        except Exception as e: show_error(self,e)


class StudentsTab(QWidget):
    def __init__(self,services:ServiceBundle):
        super().__init__(); self.services=services
        self.search=QLineEdit(); self.search.setPlaceholderText("Search by name, student ID or email…"); self.search.returnPressed.connect(self.load_data)
        search_btn=QPushButton("Search"); clear_btn=QPushButton("Clear"); add=QPushButton("Add student"); edit=QPushButton("Edit"); delete=QPushButton("Delete"); profile=QPushButton("Profile"); enroll=QPushButton("Enrollments")
        search_btn.clicked.connect(self.load_data); clear_btn.clicked.connect(lambda: (self.search.clear(),self.load_data())); add.clicked.connect(self.add_student); edit.clicked.connect(self.edit_student); delete.clicked.connect(self.delete_student); profile.clicked.connect(self.profile); enroll.clicked.connect(self.enrollments)
        row=QHBoxLayout(); row.addWidget(self.search); row.addWidget(search_btn); row.addWidget(clear_btn); row.addStretch(); [row.addWidget(b) for b in (profile,enroll,add,edit,delete)]
        self.table=QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(["ID","Student ID","Name","Email","Courses","Avg grade"]); configure_table(self.table,(2,4))
        lay=QVBoxLayout(self); lay.addLayout(row); lay.addWidget(self.table); self.load_data()
    def load_data(self):
        try: rows=self.services.students.list(self.search.text())
        except Exception as e: show_error(self,e); return
        self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[str(row["student_id"]),row["student_code"],f"{row['first_name']} {row['last_name']}",row["email"],row["courses"] or "—","—" if row["avg_grade"] is None else f"{float(row['avg_grade']):.2f}"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
    def selected_id(self):
        item=self.table.item(self.table.currentRow(),0) if self.table.currentRow()>=0 else None; return int(item.text()) if item else None
    def add_student(self):
        d=StudentDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.students.create(d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def edit_student(self):
        student_id=self.selected_id()
        if student_id is None: QMessageBox.information(self,"No selection","Select a student first."); return
        try: d=StudentDialog(self,self.services.students.get(student_id))
        except Exception as e: show_error(self,e); return
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.students.update(student_id,d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def delete_student(self):
        student_id=self.selected_id()
        if student_id is None: QMessageBox.information(self,"No selection","Select a student first."); return
        if not confirm(self,"Delete student","This also removes dependent enrollments and grades. Continue?"): return
        try: self.services.students.delete(student_id); self.load_data()
        except Exception as e: show_error(self,e)
    def profile(self):
        student_id=self.selected_id()
        if student_id is None: QMessageBox.information(self,"No selection","Select a student first."); return
        try: StudentProfileDialog(self,self.services.students.profile(student_id)).exec()
        except Exception as e: show_error(self,e)
    def enrollments(self):
        student_id=self.selected_id()
        if student_id is None: QMessageBox.information(self,"No selection","Select a student first."); return
        item=self.table.item(self.table.currentRow(),2); name=item.text() if item else "Student"
        try: EnrollmentManagerDialog(self,self.services,student_id,name).exec(); self.load_data()
        except Exception as e: show_error(self,e)


class CourseAnalyticsDialog(QDialog):
    def __init__(self,parent,services:ServiceBundle,course_id):
        super().__init__(parent); self.services=services; self.course_id=course_id; self.setWindowTitle("Course Analytics"); self.setMinimumSize(620,400)
        self.info=QLabel(); self.students=QTableWidget(); self.students.setColumnCount(4); self.students.setHorizontalHeaderLabels(["Student","Student ID","Grade","Enrollment"]); configure_table(self.students,(0,))
        close=QPushButton("Close"); close.clicked.connect(self.accept); lay=QVBoxLayout(self); lay.addWidget(self.info); lay.addWidget(self.students); lay.addWidget(close); self.load()
    def load(self):
        data=self.services.courses.analytics(self.course_id); self.info.setText(f"<b>{data['course_code']} — {data['course_name']}</b><br>Enrolled: {data['enrollment_count']} · Average: {data['average_grade'] if data['average_grade'] is not None else '—'} · Highest: {data['highest_grade'] if data['highest_grade'] is not None else '—'} · Lowest: {data['lowest_grade'] if data['lowest_grade'] is not None else '—'}")
        rows=self.services.courses.students(self.course_id); self.students.setRowCount(0)
        for r,row in enumerate(rows):
            self.students.insertRow(r); vals=[row["student_name"],row["student_code"],"—" if row["grade_value"] is None else f"{float(row['grade_value']):.2f}",str(row["enrollment_date"])];
            for c,v in enumerate(vals): self.students.setItem(r,c,QTableWidgetItem(v))


class TeacherCourseStudentsDialog(QDialog):
    def __init__(self,parent,services:ServiceBundle,course_id,course_name):
        super().__init__(parent); self.services=services; self.course_id=course_id; self.setWindowTitle(f"Students — {course_name}"); self.setMinimumSize(650,400)
        self.table=QTableWidget(); self.table.setColumnCount(5); self.table.setHorizontalHeaderLabels(["Student","Student ID","Email","Enrollment","Grade"]); configure_table(self.table,(0,2))
        grade=QPushButton("Enter / update grade"); close=QPushButton("Close"); grade.clicked.connect(self.set_grade); close.clicked.connect(self.accept); row=QHBoxLayout(); row.addWidget(grade); row.addStretch(); row.addWidget(close); lay=QVBoxLayout(self); lay.addWidget(self.table); lay.addLayout(row); self.load()
    def load(self):
        rows=self.services.courses.students(self.course_id); self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[row["student_name"],row["student_code"],row["email"],str(row["enrollment_date"]),"—" if row["grade_value"] is None else f"{float(row['grade_value']):.2f}"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
            self.table.item(r,0).setData(Qt.ItemDataRole.UserRole,row["enrollment_id"])
    def set_grade(self):
        item=self.table.item(self.table.currentRow(),0) if self.table.currentRow()>=0 else None
        if not item: QMessageBox.information(self,"No selection","Select a student first."); return
        enrollment_id=int(item.data(Qt.ItemDataRole.UserRole))
        try: current=self.services.grades.get(enrollment_id); d=GradeDialog(self,current.get("grade_value") if current else None)
        except Exception as e: show_error(self,e); return
        if d.exec()!=QDialog.DialogCode.Accepted: return
        try: data=d.get_data(); self.services.grades.set_grade(enrollment_id,data["grade_value"],data["graded_date"]); self.load()
        except Exception as e: show_error(self,e)


class CoursesTab(QWidget):
    def __init__(self,services:ServiceBundle):
        super().__init__(); self.services=services; self.is_admin=services.students.session.is_admin
        self.search=QLineEdit(); self.search.setPlaceholderText("Search by course code, name or teacher…"); self.search.returnPressed.connect(self.load_data)
        sb=QPushButton("Search"); cb=QPushButton("Clear"); analytics=QPushButton("Analytics"); students=QPushButton("Students")
        sb.clicked.connect(self.load_data); cb.clicked.connect(lambda:(self.search.clear(),self.load_data())); analytics.clicked.connect(self.open_analytics); students.clicked.connect(self.open_students)
        row=QHBoxLayout(); row.addWidget(self.search); row.addWidget(sb); row.addWidget(cb); row.addStretch(); row.addWidget(analytics); row.addWidget(students)
        self.add_btn=QPushButton("Add course"); self.edit_btn=QPushButton("Edit"); self.delete_btn=QPushButton("Delete"); self.add_btn.clicked.connect(self.add_course); self.edit_btn.clicked.connect(self.edit_course); self.delete_btn.clicked.connect(self.delete_course)
        if self.is_admin: row.addWidget(self.add_btn); row.addWidget(self.edit_btn); row.addWidget(self.delete_btn)
        self.table=QTableWidget(); self.table.setColumnCount(7); self.table.setHorizontalHeaderLabels(["ID","Code","Course name","Credits","Teacher","Enrolled","Avg grade"]); configure_table(self.table,(2,4))
        lay=QVBoxLayout(self); lay.addLayout(row); lay.addWidget(self.table); self.load_data()
    def selected_id(self):
        item=self.table.item(self.table.currentRow(),0) if self.table.currentRow()>=0 else None; return int(item.text()) if item else None
    def load_data(self):
        try: rows=self.services.courses.list(self.search.text())
        except Exception as e: show_error(self,e); return
        self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[str(row["course_id"]),row["course_code"],row["course_name"],str(row["credits"]),row["teacher"] or "— Unassigned —",str(row["enrolled"]),"—" if row["avg_grade"] is None else f"{float(row['avg_grade']):.2f}"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
    def open_analytics(self):
        course_id=self.selected_id()
        if course_id is None: QMessageBox.information(self,"No selection","Select a course first."); return
        try: CourseAnalyticsDialog(self,self.services,course_id).exec()
        except Exception as e: show_error(self,e)
    def open_students(self):
        course_id=self.selected_id()
        if course_id is None: QMessageBox.information(self,"No selection","Select a course first."); return
        try:
            row=self.table.currentRow(); course_name=self.table.item(row,2).text(); dlg=TeacherCourseStudentsDialog(self,self.services,course_id,course_name) if not self.is_admin else CourseAnalyticsDialog(self,self.services,course_id); dlg.exec()
        except Exception as e: show_error(self,e)
    def add_course(self):
        try: d=CourseDialog(self,self.services.courses.teacher_choices())
        except Exception as e: show_error(self,e); return
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.courses.create(d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def edit_course(self):
        course_id=self.selected_id()
        if course_id is None: QMessageBox.information(self,"No selection","Select a course first."); return
        try: d=CourseDialog(self,self.services.courses.teacher_choices(),self.services.courses.get(course_id))
        except Exception as e: show_error(self,e); return
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.courses.update(course_id,d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def delete_course(self):
        course_id=self.selected_id()
        if course_id is None: QMessageBox.information(self,"No selection","Select a course first."); return
        if not confirm(self,"Delete course","This removes its enrollments and grades. Continue?"): return
        try: self.services.courses.delete(course_id); self.load_data()
        except Exception as e: show_error(self,e)


class TeachersTab(QWidget):
    def __init__(self,services:ServiceBundle):
        super().__init__(); self.services=services
        self.search=QLineEdit(); self.search.setPlaceholderText("Search teachers…"); self.search.returnPressed.connect(self.load_data); s=QPushButton("Search"); c=QPushButton("Clear"); add=QPushButton("Add teacher"); edit=QPushButton("Edit"); delete=QPushButton("Delete"); [b.clicked.connect(fn) for b,fn in [(s,self.load_data),(c,lambda:(self.search.clear(),self.load_data())),(add,self.add_teacher),(edit,self.edit_teacher),(delete,self.delete_teacher)]]
        row=QHBoxLayout(); row.addWidget(self.search); row.addWidget(s); row.addWidget(c); row.addStretch(); [row.addWidget(b) for b in (add,edit,delete)]
        self.table=QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(["ID","First name","Last name","Email","Hire date","Courses taught"]); configure_table(self.table,(3,))
        lay=QVBoxLayout(self); lay.addLayout(row); lay.addWidget(self.table); self.load_data()
    def selected(self):
        r=self.table.currentRow(); return int(self.table.item(r,0).text()) if r>=0 else None
    def load_data(self):
        try: rows=self.services.teachers.list(self.search.text())
        except Exception as e: show_error(self,e); return
        self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[str(row["teacher_id"]),row["first_name"],row["last_name"],row["email"],str(row["hire_date"]),str(row["courses_taught"])];
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
    def add_teacher(self):
        d=TeacherDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.teachers.create(d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def edit_teacher(self):
        teacher_id=self.selected()
        if teacher_id is None: QMessageBox.information(self,"No selection","Select a teacher first."); return
        try: d=TeacherDialog(self,self.services.teachers.get(teacher_id))
        except Exception as e: show_error(self,e); return
        if d.exec()==QDialog.DialogCode.Accepted:
            try: self.services.teachers.update(teacher_id,d.get_data()); self.load_data()
            except Exception as e: show_error(self,e)
    def delete_teacher(self):
        teacher_id=self.selected()
        if teacher_id is None: QMessageBox.information(self,"No selection","Select a teacher first."); return
        if not confirm(self,"Delete teacher","Assigned courses will become unassigned. Continue?"): return
        try: self.services.teachers.delete(teacher_id); self.load_data()
        except Exception as e: show_error(self,e)


class UsersTab(QWidget):
    def __init__(self,services:ServiceBundle):
        super().__init__(); self.services=services
        add=QPushButton("Create user"); toggle=QPushButton("Activate / deactivate"); add.clicked.connect(self.add_user); toggle.clicked.connect(self.toggle)
        self.table=QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(["ID","Username","Role","Active","Teacher","Created"]); configure_table(self.table,(1,4))
        row=QHBoxLayout(); row.addWidget(add); row.addWidget(toggle); row.addStretch(); lay=QVBoxLayout(self); lay.addLayout(row); lay.addWidget(self.table); self.load_data()
    def selected(self):
        r=self.table.currentRow(); return int(self.table.item(r,0).text()) if r>=0 else None
    def load_data(self):
        try: rows=self.services.users.list()
        except Exception as e: show_error(self,e); return
        self.table.setRowCount(0)
        for r,row in enumerate(rows):
            self.table.insertRow(r); vals=[str(row["id"]),row["username"],row["role"],"Yes" if row["is_active"] else "No",row["teacher_name"] or "—",str(row["created_at"])];
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
    def add_user(self):
        try: d=UserDialog(self,self.services.teachers.choices())
        except Exception as e: show_error(self,e); return
        if d.exec()==QDialog.DialogCode.Accepted:
            try: data=d.get_data(); self.services.users.create(**data); self.load_data()
            except Exception as e: show_error(self,e)
    def toggle(self):
        user_id=self.selected()
        if user_id is None: QMessageBox.information(self,"No selection","Select a user first."); return
        try:
            current=self.services.users.get(user_id); self.services.users.set_active(user_id,not bool(current["is_active"])); self.load_data()
        except Exception as e: show_error(self,e)
