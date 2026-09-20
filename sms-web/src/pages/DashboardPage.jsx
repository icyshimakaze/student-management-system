import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorAlert, Empty, Loading, fmtDate, fmtGrade } from '../ui'

const STATS = [
  { key: 'students', label: 'Students', icon: 'fa-users', tone: 'blue' },
  { key: 'teachers', label: 'Teachers', icon: 'fa-chalkboard-user', tone: 'green' },
  { key: 'courses', label: 'Courses', icon: 'fa-book-open', tone: 'violet' },
  { key: 'enrollments', label: 'Enrollments', icon: 'fa-user-graduate', tone: 'amber' },
]

export default function DashboardPage() {
  const { isAdmin } = useAuth()
  const [totals, setTotals] = useState(null)
  const [courses, setCourses] = useState([])
  const [recent, setRecent] = useState([])
  const [bands, setBands] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/recent-enrollments'),
      api.get('/dashboard/grade-distribution'),
    ])
      .then(([summary, enrollments, distribution]) => {
        setTotals(summary)
        setRecent(enrollments)
        setBands(distribution)
        return isAdmin ? api.get('/courses?page_size=100') : []
      })
      .then((courseRows) => isAdmin && setCourses(courseRows.items ? courseRows.items : courseRows))
      .catch((err) => setError(err.message))
  }, [isAdmin])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">{isAdmin ? 'School-wide overview' : 'Your courses at a glance'}</div>
        </div>
      </div>
      <ErrorAlert message={error} />

      {!totals && !error && <div className="card"><Loading label="Loading dashboard…" /></div>}

      {totals && (
        <div className="stat-grid">
          {STATS.map((s) => (
            <div className="stat" key={s.key}>
              <span className={`stat-icon ${s.tone}`}>
                <i className={`fa-solid ${s.icon}`} aria-hidden="true" />
              </span>
              <span>
                <div className="num">{totals[s.key]}</div>
                <div className="label">{s.label}</div>
              </span>
            </div>
          ))}
        </div>
      )}

      {isAdmin && (
        <div className="card">
          <h2>Course overview</h2>
          {courses.length === 0 ? (
            <Empty>No courses yet.</Empty>
          ) : (
            <div className="table-wrap" style={{ border: 0, boxShadow: 'none' }}>
              <table>
                <thead>
                  <tr><th>Course</th><th>Name</th><th>Enrolled</th><th>Average</th></tr>
                </thead>
                <tbody>
                  {courses.map((c) => (
                    <tr key={c.course_id}>
                      <td>{c.course_code}</td>
                      <td>{c.course_name}</td>
                      <td>{c.enrolled}</td>
                      <td>{fmtGrade(c.avg_grade)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="two-col">
        <div className="card">
          <h2>Recent enrollments</h2>
          {recent.length === 0 ? (
            <Empty>No enrollments yet.</Empty>
          ) : (
            <div className="table-wrap" style={{ border: 0, boxShadow: 'none' }}>
              <table>
                <thead>
                  <tr><th>Date</th><th>Student</th><th>Course</th></tr>
                </thead>
                <tbody>
                  {recent.map((r, i) => (
                    <tr key={i}>
                      <td>{fmtDate(r.enrollment_date)}</td>
                      <td>{r.student_name}</td>
                      <td>{r.course_code}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <h2>Grade distribution</h2>
          {bands.length === 0 ? (
            <Empty>No grades recorded yet.</Empty>
          ) : (
            <div className="table-wrap" style={{ border: 0, boxShadow: 'none' }}>
              <table>
                <thead>
                  <tr><th>Band</th><th>Students</th></tr>
                </thead>
                <tbody>
                  {bands.map((b) => (
                    <tr key={b.grade_band}>
                      <td><span className="badge band">{b.grade_band}</span></td>
                      <td>{b.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
