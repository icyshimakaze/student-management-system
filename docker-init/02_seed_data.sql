-- Fictional demonstration data. Loaded automatically by docker-compose
-- after 01_schema.sql on first startup. Same data as database/seed_data.sql.
INSERT INTO teachers (first_name,last_name,email,hire_date) VALUES
('Alan','Grant','alan.grant@school.edu','2015-08-01'),('Ellie','Sattler','ellie.sattler@school.edu','2017-01-15'),('Ian','Malcolm','ian.malcolm@school.edu','2012-09-01');
INSERT INTO courses (course_code,course_name,credits,teacher_id) VALUES
('BIO101','Biology 101',4,1),('GEN201','Advanced Genetics',3,2),('MAT210','Chaos Theory',3,3),('AST100','Astronomy Basics',2,NULL);
INSERT INTO students (student_code,first_name,last_name,email,enrollment_date) VALUES
('STU-0001','Maya','Chen','maya.chen@student.edu','2023-09-01'),('STU-0002','Liam','Okafor','liam.okafor@student.edu','2023-09-01'),('STU-0003','Sofia','Rossi','sofia.rossi@student.edu','2024-01-15'),('STU-0004','Zoe','Fontaine','zoe.fontaine@student.edu','2025-01-15');
INSERT INTO enrollments (student_id,course_id,enrollment_date) VALUES (1,1,'2023-09-05'),(1,3,'2023-09-05'),(2,1,'2023-09-05'),(2,2,'2023-09-05'),(3,2,'2024-01-20');
INSERT INTO grades (enrollment_id,grade_value,graded_date) VALUES (1,88.5,'2023-12-15'),(2,76,'2023-12-15'),(3,91,'2023-12-15'),(4,84.5,'2023-12-15');
-- Create users safely after seeding with: python scripts/create_user.py
