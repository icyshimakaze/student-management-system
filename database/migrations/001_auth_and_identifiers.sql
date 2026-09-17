-- One-time upgrade for an existing student_management database. Take a backup first.
ALTER TABLE students ADD COLUMN student_code VARCHAR(30) NULL UNIQUE AFTER student_id;
ALTER TABLE courses ADD COLUMN course_code VARCHAR(30) NULL UNIQUE AFTER course_id;
UPDATE students SET student_code = CONCAT('STU-', LPAD(student_id, 4, '0')) WHERE student_code IS NULL;
UPDATE courses SET course_code = CONCAT('CRS-', LPAD(course_id, 4, '0')) WHERE course_code IS NULL;
ALTER TABLE students MODIFY student_code VARCHAR(30) NOT NULL;
ALTER TABLE courses MODIFY course_code VARCHAR(30) NOT NULL;
CREATE TABLE IF NOT EXISTS users (
 id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL, role ENUM('ADMIN','TEACHER') NOT NULL,
 teacher_id INT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_users_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE SET NULL
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_courses_teacher ON courses(teacher_id);
CREATE INDEX idx_students_name ON students(last_name, first_name);
CREATE INDEX idx_teachers_name ON teachers(last_name, first_name);
