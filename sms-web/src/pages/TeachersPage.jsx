import { useState } from 'react'
import { api } from '../api'
import { ErrorAlert, Empty, Modal, Loading, Pagination, usePagedList, confirmDialog, fmtDate, fmtName } from '../ui'

const EMPTY_FORM = { first_name: '', last_name: '', email: '', hire_date: new Date().toISOString().slice(0, 10) }

function TeacherForm({ initial, onSubmit, onCancel, busy, submitLabel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    try {
      await onSubmit(form)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <ErrorAlert message={error} />
      <div className="form-grid">
        <div className="field">
          <label>First name</label>
          <input value={form.first_name} onChange={(e) => set('first_name', e.target.value)} required />
        </div>
        <div className="field">
          <label>Last name</label>
          <input value={form.last_name} onChange={(e) => set('last_name', e.target.value)} required />
        </div>
        <div className="field full">
          <label>Email</label>
          <input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
        </div>
        <div className="field full">
          <label>Hire date</label>
          <input type="date" value={form.hire_date} onChange={(e) => set('hire_date', e.target.value)} required />
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

export default function TeachersPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const { rows, meta, error, setError, reload: load } = usePagedList('teachers', search, page)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)

  async function createTeacher(form) {
    setBusy(true)
    try {
      await api.post('/teachers', form)
      setAdding(false)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function updateTeacher(form) {
    setBusy(true)
    try {
      await api.put(`/teachers/${editing.teacher_id}`, form)
      setEditing(null)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function deleteTeacher(row) {
    if (!confirmDialog(`Delete ${fmtName(row)}? Their courses will become unassigned.`)) return
    try {
      await api.delete(`/teachers/${row.teacher_id}`)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Teachers</h1>
        <button className="btn primary" onClick={() => setAdding(true)}>
          <i className="fa-solid fa-plus" aria-hidden="true" /> Add teacher
        </button>
      </div>
      <ErrorAlert message={error} />

      <div className="toolbar">
        <span className="search-box">
          <i className="fa-solid fa-magnifying-glass" aria-hidden="true" />
          <input type="search" aria-label="Search teachers" placeholder="Search teachers…" value={search}
                 onChange={(e) => {
                   setSearch(e.target.value)
                   setPage(1)
                 }} />
        </span>
      </div>

      {rows === null ? (
        <div className="card"><Loading /></div>
      ) : rows.length === 0 ? (
        <div className="card"><Empty>No teachers match.</Empty></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Hire date</th><th>Courses taught</th><th><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.teacher_id}>
                  <td>{fmtName(row)}</td>
                  <td>{row.email}</td>
                  <td>{fmtDate(row.hire_date)}</td>
                  <td>{row.courses_taught}</td>
                  <td className="actions">
                    <span className="cell-actions">
                      <button className="btn small" onClick={() => setEditing(row)} title="Edit teacher">
                        <i className="fa-solid fa-pen" aria-hidden="true" /> Edit
                      </button>
                      <button className="btn small danger" onClick={() => deleteTeacher(row)} title="Delete teacher">
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
        <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} onPage={setPage} />
      )}

      {adding && (
        <Modal title="Add teacher" onClose={() => setAdding(false)}>
          <TeacherForm initial={EMPTY_FORM} onSubmit={createTeacher}
                       onCancel={() => setAdding(false)} busy={busy} submitLabel="Create teacher" />
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit — ${fmtName(editing)}`} onClose={() => setEditing(null)}>
          <TeacherForm
            initial={{
              first_name: editing.first_name,
              last_name: editing.last_name,
              email: editing.email,
              hire_date: String(editing.hire_date).slice(0, 10),
            }}
            onSubmit={updateTeacher}
            onCancel={() => setEditing(null)}
            busy={busy}
            submitLabel="Save changes"
          />
        </Modal>
      )}
    </>
  )
}
