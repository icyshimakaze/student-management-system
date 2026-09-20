-- =====================================================================
-- Analytical queries against student_management
-- Run schema.sql and seed_data.sql first.
-- Each query is commented with the SQL concept it demonstrates.
-- =====================================================================
USE student_management;

-- 1. INNER JOIN across three tables: every enrollment with the
--    student's name, course name, and the teacher assigned to it.
SELECT
    s.first_name, s.last_name,
    c.course_name,
    t.first_name AS teacher_first, t.last_name AS teacher_last
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN courses  c ON c.course_id  = e.course_id
JOIN teachers t ON t.teacher_id = c.teacher_id
ORDER BY s.last_name, c.course_name;

-- 2. LEFT JOIN: list every student, including those with zero
--    enrollments (e.g. Zoe Fontaine has none, and will show NULLs).
SELECT s.first_name, s.last_name, c.course_name
FROM students s
LEFT JOIN enrollments e ON e.student_id = s.student_id
LEFT JOIN courses c ON c.course_id = e.course_id
ORDER BY s.last_name;

-- 3. LEFT JOIN + IS NULL: find courses that currently have no
--    assigned teacher (Astronomy Basics, per the seed data).
SELECT c.course_name
FROM courses c
LEFT JOIN teachers t ON t.teacher_id = c.teacher_id
WHERE t.teacher_id IS NULL;

-- 4. Aggregate functions + GROUP BY: average and highest grade
--    per course.
SELECT
    c.course_name,
    ROUND(AVG(g.grade_value), 2) AS avg_grade,
    MAX(g.grade_value)           AS top_grade,
    COUNT(g.grade_id)            AS graded_students
FROM courses c
JOIN enrollments e ON e.course_id = c.course_id
JOIN grades g       ON g.enrollment_id = e.enrollment_id
GROUP BY c.course_id, c.course_name
ORDER BY avg_grade DESC;

-- 5. GROUP BY + HAVING: courses with more than 2 enrolled students.
SELECT c.course_name, COUNT(e.enrollment_id) AS num_students
FROM courses c
JOIN enrollments e ON e.course_id = c.course_id
GROUP BY c.course_id, c.course_name
HAVING COUNT(e.enrollment_id) > 2
ORDER BY num_students DESC;

-- 6. Subquery in WHERE: students whose grade on any course beat the
--    overall average grade across all courses.
SELECT DISTINCT s.first_name, s.last_name, g.grade_value
FROM students s
JOIN enrollments e ON e.student_id = s.student_id
JOIN grades g       ON g.enrollment_id = e.enrollment_id
WHERE g.grade_value > (SELECT AVG(grade_value) FROM grades)
ORDER BY g.grade_value DESC;

-- 7. Correlated subquery: courses whose own average grade is above
--    the average grade across all courses combined.
SELECT c.course_name,
       (SELECT ROUND(AVG(g.grade_value), 2)
        FROM enrollments e
        JOIN grades g ON g.enrollment_id = e.enrollment_id
        WHERE e.course_id = c.course_id) AS course_avg
FROM courses c
WHERE (SELECT AVG(g.grade_value)
       FROM enrollments e
       JOIN grades g ON g.enrollment_id = e.enrollment_id
       WHERE e.course_id = c.course_id)
      > (SELECT AVG(grade_value) FROM grades)
ORDER BY course_avg DESC;

-- 8. Window function (RANK): rank students within each course by grade,
--    without collapsing rows the way GROUP BY would.
SELECT
    c.course_name,
    s.first_name, s.last_name,
    g.grade_value,
    RANK() OVER (PARTITION BY c.course_id ORDER BY g.grade_value DESC) AS rank_in_course
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN courses  c ON c.course_id  = e.course_id
JOIN grades   g ON g.enrollment_id = e.enrollment_id
ORDER BY c.course_name, rank_in_course;

-- 9. Window function (running total): cumulative enrollment count
--    over time, useful for an "enrollments over time" chart.
SELECT
    enrollment_date,
    COUNT(*) AS enrollments_that_day,
    SUM(COUNT(*)) OVER (ORDER BY enrollment_date) AS running_total
FROM enrollments
GROUP BY enrollment_date
ORDER BY enrollment_date;

-- 10. Multi-table JOIN + GROUP BY: how many distinct students each
--     teacher currently teaches, across all of their courses.
SELECT
    t.first_name, t.last_name,
    COUNT(DISTINCT e.student_id) AS students_taught
FROM teachers t
JOIN courses c      ON c.teacher_id = t.teacher_id
JOIN enrollments e  ON e.course_id  = c.course_id
GROUP BY t.teacher_id, t.first_name, t.last_name
ORDER BY students_taught DESC;

-- 11. CASE expression: bucket numeric grades into letter grades.
SELECT
    s.first_name, s.last_name, c.course_name, g.grade_value,
    CASE
        WHEN g.grade_value >= 90 THEN 'A'
        WHEN g.grade_value >= 80 THEN 'B'
        WHEN g.grade_value >= 70 THEN 'C'
        WHEN g.grade_value >= 60 THEN 'D'
        ELSE 'F'
    END AS letter_grade
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN courses  c ON c.course_id  = e.course_id
JOIN grades   g ON g.enrollment_id = e.enrollment_id
ORDER BY letter_grade, g.grade_value DESC;

-- 12. NOT EXISTS: students who are not enrolled in any course.
SELECT s.first_name, s.last_name
FROM students s
WHERE NOT EXISTS (
    SELECT 1 FROM enrollments e WHERE e.student_id = s.student_id
);

-- 13. View: a reusable summary of each student's course load and
--     average grade, so this logic doesn't need to be rewritten
--     every time it's needed.
CREATE OR REPLACE VIEW student_performance AS
SELECT
    s.student_id,
    s.first_name,
    s.last_name,
    COUNT(DISTINCT e.course_id)      AS courses_taken,
    ROUND(AVG(g.grade_value), 2)     AS avg_grade
FROM students s
LEFT JOIN enrollments e ON e.student_id = s.student_id
LEFT JOIN grades g       ON g.enrollment_id = e.enrollment_id
GROUP BY s.student_id, s.first_name, s.last_name;

-- Example use of the view above:
SELECT * FROM student_performance ORDER BY avg_grade DESC;


-- 14. EXISTS: teachers with at least one assigned course.
SELECT t.teacher_id, t.first_name, t.last_name
FROM teachers t
WHERE EXISTS (SELECT 1 FROM courses c WHERE c.teacher_id=t.teacher_id)
ORDER BY t.last_name, t.first_name;

-- 15. View: reusable course statistics used by reporting screens.
CREATE OR REPLACE VIEW course_statistics AS
SELECT
    c.course_id,
    c.course_code,
    c.course_name,
    COUNT(DISTINCT e.student_id) AS enrolled_students,
    ROUND(AVG(g.grade_value),2) AS average_grade,
    MAX(g.grade_value) AS highest_grade,
    MIN(g.grade_value) AS lowest_grade
FROM courses c
LEFT JOIN enrollments e ON e.course_id=c.course_id
LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
GROUP BY c.course_id, c.course_code, c.course_name;

SELECT * FROM course_statistics ORDER BY average_grade DESC;

-- 16. Performance-oriented lookup: identifier search can use the
-- unique indexes on student_code and course_code for exact matches.
SELECT student_id, student_code, first_name, last_name
FROM students
WHERE student_code = 'STU-0001';

SELECT course_id, course_code, course_name, credits
FROM courses
WHERE course_code = 'BIO101';

-- 17. Audit trail: who changed what, ordered newest-first.
-- Uses idx_audit_created for the sort and idx_audit_action for filters.
SELECT created_at, username, action, entity_type, entity_id, details
FROM audit_logs
ORDER BY created_at DESC, audit_id DESC
LIMIT 20;

-- 18. Audit summary: most active users in the last 30 days.
SELECT username,
       COUNT(*) AS events,
       SUM(action LIKE 'student.%') AS student_changes,
       SUM(action LIKE 'grade.%')  AS grade_changes,
       SUM(action LIKE 'user.%')   AS user_changes
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY username
ORDER BY events DESC;

-- 19. Security review: failed and successful logins per user.
SELECT username,
       SUM(action = 'user.login')     AS logins,
       SUM(action = 'user.deactivate') AS deactivations
FROM audit_logs
WHERE action LIKE 'user.%'
GROUP BY username
HAVING logins > 0
ORDER BY logins DESC;
