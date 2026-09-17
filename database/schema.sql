-- =====================================================================
-- student_management: normalized relational schema
-- =====================================================================
-- Used by both the desktop app (main.py) and the analytical queries in
-- queries.sql. One schema, one source of truth.
--
-- Entities: teachers -> courses -> enrollments <- students
--                                       |
--                                     grades
-- =====================================================================

CREATE DATABASE IF NOT EXISTS student_management;
USE student_management;

CREATE TABLE IF NOT EXISTS teachers (
    teacher_id   INT AUTO_INCREMENT PRIMARY KEY,
    first_name   VARCHAR(100) NOT NULL,
    last_name    VARCHAR(100) NOT NULL,
    email        VARCHAR(255) NOT NULL UNIQUE,
    hire_date    DATE NOT NULL,
    KEY idx_teachers_name (last_name, first_name)
);

CREATE TABLE IF NOT EXISTS students (
    student_id       INT AUTO_INCREMENT PRIMARY KEY,
    student_code     VARCHAR(30) NOT NULL UNIQUE,
    first_name       VARCHAR(100) NOT NULL,
    last_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(255) NOT NULL UNIQUE,
    enrollment_date  DATE NOT NULL,
    KEY idx_students_name (last_name, first_name)
);

CREATE TABLE IF NOT EXISTS courses (
    course_id    INT AUTO_INCREMENT PRIMARY KEY,
    course_code  VARCHAR(30) NOT NULL UNIQUE,
    course_name  VARCHAR(150) NOT NULL,
    credits      TINYINT NOT NULL CHECK (credits BETWEEN 1 AND 6),
    teacher_id   INT,
    CONSTRAINT fk_courses_teacher
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        ON DELETE SET NULL,
    KEY idx_courses_teacher (teacher_id)
);

-- Junction table resolving the many-to-many relationship between
-- students and courses.
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id    INT AUTO_INCREMENT PRIMARY KEY,
    student_id       INT NOT NULL,
    course_id        INT NOT NULL,
    enrollment_date  DATE NOT NULL,
    CONSTRAINT fk_enrollments_student
        FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course
        FOREIGN KEY (course_id) REFERENCES courses(course_id)
        ON DELETE CASCADE,
    -- A student can only enroll in the same course once.
    CONSTRAINT uq_student_course UNIQUE (student_id, course_id),
    KEY idx_enrollments_student (student_id),
    KEY idx_enrollments_course (course_id)
);

CREATE TABLE IF NOT EXISTS grades (
    grade_id       INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_id  INT NOT NULL UNIQUE,
    grade_value    DECIMAL(5,2) NOT NULL CHECK (grade_value BETWEEN 0 AND 100),
    graded_date    DATE NOT NULL,
    CONSTRAINT fk_grades_enrollment
        FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('ADMIN', 'TEACHER') NOT NULL,
    teacher_id INT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE SET NULL
);

