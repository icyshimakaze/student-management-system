import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorAlert, Empty, Modal, Loading, Pagination, usePagedList, confirmDialog, fmtDate, fmtGrade, fmtName } from '../ui'

const EMPTY_FORM = { course_code: '', course_name: '', credits: 3, teacher_id: null }

function CourseForm({ initial, teachers, onSubmit, onCancel, busy, submitLabel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    try {
      await onSubmit({ ...form, credits: Number(form.credits) })
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <ErrorAlert message={error} />
      <div className="form-grid">
        <div className="field">
          <label>Course code</label>
          <input value={form.course_code} onChange={(e) => set('course_code', e.target.value)} required />
        </div>
        <div className="field">
          <label>Credits (1–6)</label>
          <input type="number" min="1" max="6" value={form.credits}
                 onChange={(e) => set('credits', e.target.value)} required />
        </div>
        <div className="field full">
          <label>Course name</label>
          <input value={form.course_name} onChange={(e) => set('course_name', e.target.value)} required />
        </div>
        <div className="field full">
          <label htmlFor="cf-teacher">Teacher</label>
          <select id="cf-teacher" value={form.teacher_id ?? ''} onChange={(e) => set('teacher_id', e.target.value || null)}>
            <option value="">— Unassigned —</option>
            {teachers.map((t) => (
              <option key={t.teacher_id} value={t.teacher_id}>{fmtName(t)}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="modal-actions">
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>            <button type="submit" className="btn primary" disabled={busy}>
              <i className="fa-solid fa-floppy-disk" aria-hidden="true" /> {submitLabel}
            </button>
      </div>
    </form>
  )
}

function AnalyticsModal({ course, isTeacherAccount, onClose, onChanged }) {
  const [analytics, setAnalytics] = useState(null)
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [gradeFor, setGradeFor] = useState(null)
  const [gradeValue, setGradeValue] = useState('')
  const [gradeDate, setGradeDate] = useState(new Date().toISOString().slice(0, 10))

  const load = useCallback(() => {
    api.get(`/courses/${course.course_id}/analytics`).then(setAnalytics).catch((err) => setError(err.message))
    api.get(`/courses/${course.course_id}/students`).then(setRows).catch((err) => setError(err.message))
  }, [course.course_id])

  useEffect(load, [load])

  async function saveGrade(event) {
    event.preventDefault()
    try {
      await api.put(`/enrollments/${gradeFor.enrollment_id}/grade`, {
        grade_value: Number(gradeValue),
        graded_date: gradeDate,
      })
      setGradeFor(null)
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Modal title={`${course.course_code} — ${course.course_name}`} onClose={onClose}>
      <ErrorAlert message={error} />
      {analytics && (
        <p>
          Enrolled: <strong>{analytics.enrollment_count}</strong> · Average:{' '}
          <strong>{fmtGrade(analytics.average_grade)}</strong> · Highest:{' '}
          <strong>{fmtGrade(analytics.highest_grade)}</strong> · Lowest:{' '}
          <strong>{fmtGrade(analytics.lowest_grade)}</strong>
        </p>
      )}
      {rows.length === 0 ? (
        <Empty>No students enrolled.</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Student</th><th>Email</th><th>Enrolled</th><th>Grade</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.enrollment_id}>
                  <td>{r.student_name}</td>
                  <td>{r.email}</td>
                  <td>{fmtDate(r.enrollment_date)}</td>
                  <td>{fmtGrade(r.grade_value)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn small"
                      title="Enter or update grade"
                      onClick={() => {
                        setGradeFor(r)
                        setGradeValue(r.grade_value === null || r.grade_value === undefined ? '' : String(r.grade_value))
                      }}
                    >
                      <i className="fa-solid fa-pen" aria-hidden="true" /> Grade
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {gradeFor && (
        <form onSubmit={saveGrade} style={{ marginTop: 18 }}>
          <h2>Grade for {gradeFor.student_name}</h2>
          <div className="form-grid">
            <div className="field">
              <label>Grade (0–100)</label>
              <input type="number" min="0" max="100" step="0.5" required
                     value={gradeValue} onChange={(e) => setGradeValue(e.target.value)} />
            </div>
            <div className="field">
              <label>Graded date</label>
              <input type="date" value={gradeDate} onChange={(e) => setGradeDate(e.target.value)} />
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={() => setGradeFor(null)}>Cancel</button>
            <button type="submit" className="btn primary">Save grade</button>
          </div>
        </form>
      )}
      {isTeacherAccount && (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          You can grade students in your own courses only — enforced by the server.
        </p>
      )}
    </Modal>
  )
}

export default function CoursesPage() {
  const { isAdmin } = useAuth()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const { rows, meta, error, setError, reload: load } = usePagedList('courses', search, page)
  const [teachers, setTeachers] = useState([])
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [analyticsFor, setAnalyticsFor] = useState(null)

  useEffect(() => {
    if (isAdmin) {
      api
        .get('/teachers?page_size=100')
        .then((data) => setTeachers(data.items ? data.items : data))
        .catch(() => setTeachers([]))
    }
  }, [isAdmin])

  async function createCourse(form) {
    setBusy(true)
    try {
      await api.post('/courses', form)
      setAdding(false)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function updateCourse(form) {
    setBusy(true)
    try {
      await api.put(`/courses/${editing.course_id}`, form)
      setEditing(null)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function deleteCourse(row) {
    if (!confirmDialog(`Delete ${row.course_name}? Its enrollments and grades will also be removed.`)) return
    try {
      await api.delete(`/courses/${row.course_id}`)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Courses</h1>
        {isAdmin && (
          <button className="btn primary" onClick={() => setAdding(true)}>
            <i className="fa-solid fa-plus" aria-hidden="true" /> Add course
          </button>
        )}
      </div>
      <ErrorAlert message={error} />

      <div className="toolbar">
        <span className="search-box">
          <i className="fa-solid fa-magnifying-glass" aria-hidden="true" />
          <input
            type="search"
            aria-label="Search courses"
            placeholder="Search by course code, name or teacher…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </span>
      </div>

      {rows === null ? (
        <div className="card"><Loading /></div>
      ) : rows.length === 0 ? (
        <div className="card"><Empty>No courses match.</Empty></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Code</th><th>Name</th><th>Credits</th><th>Teacher</th><th>Enrolled</th><th>Avg</th><th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.course_id}>
                  <td>{row.course_code}</td>
                  <td>{row.course_name}</td>
                  <td>{row.credits}</td>
                  <td>{row.teacher || <span className="muted">Unassigned</span>}</td>
                  <td>{row.enrolled}</td>
                  <td>{fmtGrade(row.avg_grade)}</td>
                  <td className="actions">
                    <span className="cell-actions">
                      <button className="btn small" onClick={() => setAnalyticsFor(row)} title="View roster and analytics">
                        <i className="fa-solid fa-chart-column" aria-hidden="true" /> Students &amp; analytics
                      </button>
                      {isAdmin && (
                        <>
                          <button className="btn small" onClick={() => setEditing(row)} title="Edit course">
                            <i className="fa-solid fa-pen" aria-hidden="true" /> Edit
                          </button>
                          <button className="btn small danger" onClick={() => deleteCourse(row)} title="Delete course">
                            <i className="fa-solid fa-trash" aria-hidden="true" /> Delete
                          </button>
                        </>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows !== null && rows.length > 0 && (
        <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} onPage={setPage} />
      )}

      {adding && (
        <Modal title="Add course" onClose={() => setAdding(false)}>
          <CourseForm
            initial={EMPTY_FORM}
            teachers={teachers}
            onSubmit={createCourse}
            onCancel={() => setAdding(false)}
            busy={busy}
            submitLabel="Create course"
          />
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit — ${editing.course_name}`} onClose={() => setEditing(null)}>
          <CourseForm
            initial={{
              course_code: editing.course_code,
              course_name: editing.course_name,
              credits: editing.credits,
              teacher_id: editing.teacher_id ?? null,
            }}
            teachers={teachers}
            onSubmit={updateCourse}
            onCancel={() => setEditing(null)}
            busy={busy}
            submitLabel="Save changes"
          />
        </Modal>
      )}

      {analyticsFor && (
        <AnalyticsModal
          course={analyticsFor}
          isTeacherAccount={!isAdmin}
          onClose={() => setAnalyticsFor(null)}
          onChanged={load}
        />
      )}
    </>
  )
}
