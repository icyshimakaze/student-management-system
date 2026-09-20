import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorAlert, Empty, Modal, Loading, Pagination, usePagedList, confirmDialog, fmtDate, fmtGrade, fmtName } from '../ui'

const EMPTY_FORM = {
  student_code: '',
  first_name: '',
  last_name: '',
  email: '',
  enrollment_date: new Date().toISOString().slice(0, 10),
}

function StudentForm({ initial, onSubmit, onCancel, busy, submitLabel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    setError('')
    Promise.resolve(onSubmit(form)).catch((err) => setError(err.message))
  }

  return (
    <form onSubmit={handleSubmit}>
      <ErrorAlert message={error} />
      <div className="form-grid">
        <div className="field">
          <label htmlFor="sf-code">Student ID</label>
          <input id="sf-code" value={form.student_code} onChange={(e) => set('student_code', e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="sf-date">Enrollment date</label>
          <input id="sf-date" type="date" value={form.enrollment_date} onChange={(e) => set('enrollment_date', e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="sf-first">First name</label>
          <input id="sf-first" value={form.first_name} onChange={(e) => set('first_name', e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="sf-last">Last name</label>
          <input id="sf-last" value={form.last_name} onChange={(e) => set('last_name', e.target.value)} required />
        </div>
        <div className="field full">
          <label htmlFor="sf-email">Email</label>
          <input id="sf-email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
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

function ProfileModal({ studentId, onClose }) {
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/students/${studentId}/profile`).then(setProfile).catch((err) => setError(err.message))
  }, [studentId])

  return (
    <Modal title="Student profile" onClose={onClose}>
      <ErrorAlert message={error} />
      {!profile && !error && <Loading />}
      {profile && profile.student && (
        <>
          <p>
            <strong>{fmtName(profile.student)}</strong>{' '}
            <span className="muted">({profile.student.student_code})</span>
            <br />
            {profile.student.email}
            <br />
            <span className="muted">Enrolled {fmtDate(profile.student.enrollment_date)}</span>
          </p>
          <p>
            Average grade:{' '}
            <strong>{profile.average_grade === null ? '—' : Number(profile.average_grade).toFixed(2)}</strong>
          </p>
          {profile.courses.length === 0 ? (
            <Empty>Not enrolled in any course.</Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Course</th><th>Enrolled</th><th>Grade</th></tr>
                </thead>
                <tbody>
                  {profile.courses.map((c) => (
                    <tr key={c.course_code}>
                      <td>{c.course_code} — {c.course_name}</td>
                      <td>{fmtDate(c.enrollment_date)}</td>
                      <td>{fmtGrade(c.grade_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <div className="modal-actions">
        <button className="btn" onClick={onClose}><i className="fa-solid fa-xmark" aria-hidden="true" /> Close</button>
      </div>
    </Modal>
  )
}

function EnrollmentsModal({ student, onClose, onChanged }) {
  const [rows, setRows] = useState(null)
  const [available, setAvailable] = useState([])
  const [error, setError] = useState('')
  const [gradeFor, setGradeFor] = useState(null) // {enrollment_id, course_name, current}
  const [gradeValue, setGradeValue] = useState('')
  const [gradeDate, setGradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [savingGrade, setSavingGrade] = useState(false)

  const load = useCallback(() => {
    api.get(`/students/${student.student_id}/enrollments`)
      .then(setRows)
      .catch((err) => setError(err.message))
    api.get(`/students/${student.student_id}/available-courses`)
      .then(setAvailable)
      .catch(() => setAvailable([]))
  }, [student.student_id])

  useEffect(load, [load])

  async function enroll(event) {
    const courseId = event.target.value
    if (!courseId) return
    event.target.value = ''
    try {
      await api.post(`/students/${student.student_id}/enrollments`, {
        course_id: Number(courseId),
        enrollment_date: new Date().toISOString().slice(0, 10),
      })
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeEnrollment(row) {
    if (!confirmDialog(`Remove the enrollment in ${row.course_name}? Any grade for it will also be removed.`)) return
    try {
      await api.delete(`/enrollments/${row.enrollment_id}`)
      load()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  function openGrade(row) {
    setGradeFor(row)
    setGradeValue(row.grade_value === null || row.grade_value === undefined ? '' : String(row.grade_value))
  }

  async function saveGrade(event) {
    event.preventDefault()
    setSavingGrade(true)
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
    } finally {
      setSavingGrade(false)
    }
  }

  return (
    <Modal title={`Enrollments — ${fmtName(student)}`} onClose={onClose}>
      <ErrorAlert message={error} />
      <div className="field" style={{ marginBottom: 14 }}>
        <label htmlFor="enroll-select">Enroll in a course</label>
        <select id="enroll-select" onChange={enroll} defaultValue="">
          <option value="">{available.length ? 'Select a course…' : 'No courses available'}</option>
          {available.map((c) => (
            <option key={c.course_id} value={c.course_id}>{c.course_name}</option>
          ))}
        </select>
      </div>
      {rows === null ? (
        <Loading />
      ) : rows.length === 0 ? (
        <Empty>No enrollments yet.</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Course</th><th>Enrolled</th><th>Grade</th><th><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.enrollment_id}>
                  <td>{r.course_code} — {r.course_name}</td>
                  <td>{fmtDate(r.enrollment_date)}</td>
                  <td>{fmtGrade(r.grade_value)}</td>
                  <td className="actions">
                    <span className="cell-actions">
                      <button className="btn small" onClick={() => openGrade(r)} title="Enter or update grade">
                        <i className="fa-solid fa-pen" aria-hidden="true" /> Grade
                      </button>
                      <button className="btn small danger" onClick={() => removeEnrollment(r)} title="Remove enrollment">
                        <i className="fa-solid fa-trash" aria-hidden="true" /> Remove
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {gradeFor && (
        <form onSubmit={saveGrade} style={{ marginTop: 18 }}>
          <h2>Grade for {gradeFor.course_name}</h2>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="grade-value">Grade (0–100)</label>
              <input
                id="grade-value"
                type="number" min="0" max="100" step="0.5" required
                value={gradeValue} onChange={(e) => setGradeValue(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="grade-date">Graded date</label>
              <input id="grade-date" type="date" value={gradeDate} onChange={(e) => setGradeDate(e.target.value)} />
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={() => setGradeFor(null)}>Cancel</button>
            <button type="submit" className="btn primary" disabled={savingGrade}>
              <i className="fa-solid fa-floppy-disk" aria-hidden="true" /> {savingGrade ? 'Saving…' : 'Save grade'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}

export default function StudentsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const { rows, meta, error, setError, reload: load } = usePagedList('students', search, page)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null) // student row
  const [profileId, setProfileId] = useState(null)
  const [enrollmentsFor, setEnrollmentsFor] = useState(null)

  async function createStudent(form) {
    setBusy(true)
    try {
      await api.post('/students', form)
      setAdding(false)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function updateStudent(form) {
    setBusy(true)
    try {
      await api.put(`/students/${editing.student_id}`, form)
      setEditing(null)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function deleteStudent(row) {
    if (!confirmDialog(`Delete ${fmtName(row)}? Their enrollments and grades will also be removed.`)) return
    try {
      await api.delete(`/students/${row.student_id}`)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Students</h1>
        <button className="btn primary" onClick={() => setAdding(true)}>
          <i className="fa-solid fa-plus" aria-hidden="true" /> Add student
        </button>
      </div>
      <ErrorAlert message={error} />

      <div className="toolbar">
        <span className="search-box">
          <i className="fa-solid fa-magnifying-glass" aria-hidden="true" />
          <input
            type="search"
            aria-label="Search students"
            placeholder="Search by name, student ID or email…"
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
        <div className="card"><Empty>No students match.</Empty></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student ID</th><th>Name</th><th>Email</th><th>Courses</th><th>Avg grade</th>
                <th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.student_id}>
                  <td>{row.student_code}</td>
                  <td>{fmtName(row)}</td>
                  <td>{row.email}</td>
                  <td>{row.courses || <span className="muted">—</span>}</td>
                  <td>{fmtGrade(row.avg_grade)}</td>
                  <td className="actions">
                    <span className="cell-actions">
                      <button className="btn small" onClick={() => setProfileId(row.student_id)} title="View profile">
                        <i className="fa-solid fa-user" aria-hidden="true" /> Profile
                      </button>
                      <button className="btn small" onClick={() => setEnrollmentsFor(row)} title="Manage enrollments and grades">
                        <i className="fa-solid fa-clipboard-list" aria-hidden="true" /> Enrollments
                      </button>
                      <button className="btn small" onClick={() => setEditing(row)} title="Edit student">
                        <i className="fa-solid fa-pen" aria-hidden="true" /> Edit
                      </button>
                      <button className="btn small danger" onClick={() => deleteStudent(row)} title="Delete student">
                        <i className="fa-solid fa-trash" aria-hidden="true" /> Delete
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows !== null && rows.length > 0 && (
        <Pagination
          page={meta.page}
          totalPages={meta.total_pages}
          total={meta.total}
          onPage={setPage}
        />
      )}

      {adding && (
        <Modal title="Add student" onClose={() => setAdding(false)}>
          <StudentForm initial={EMPTY_FORM} onSubmit={createStudent} onCancel={() => setAdding(false)} busy={busy} submitLabel="Create student" />
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit — ${fmtName(editing)}`} onClose={() => setEditing(null)}>
          <StudentForm
            initial={{
              student_code: editing.student_code,
              first_name: editing.first_name,
              last_name: editing.last_name,
              email: editing.email,
              enrollment_date: String(editing.enrollment_date).slice(0, 10),
            }}
            onSubmit={updateStudent}
            onCancel={() => setEditing(null)}
            busy={busy}
            submitLabel="Save changes"
          />
        </Modal>
      )}

      {profileId && <ProfileModal studentId={profileId} onClose={() => setProfileId(null)} />}
      {enrollmentsFor && (
        <EnrollmentsModal
          student={enrollmentsFor}
          onClose={() => setEnrollmentsFor(null)}
          onChanged={load}
        />
      )}
    </>
  )
}
