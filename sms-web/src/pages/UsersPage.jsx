import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorAlert, Empty, Modal, Loading, confirmDialog, fmtDate, fmtName } from '../ui'

function UserForm({ teachers, onSubmit, onCancel, busy }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('TEACHER')
  const [teacherId, setTeacherId] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    try {
      await onSubmit({
        username,
        password,
        role,
        teacher_id: role === 'TEACHER' ? Number(teacherId) : null,
      })
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <ErrorAlert message={error} />
      <div className="form-grid">
        <div className="field">
          <label htmlFor="uf-username">Username</label>
          <input id="uf-username" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
        </div>
        <div className="field">
          <label htmlFor="uf-password">Password (min 8 chars)</label>
          <input id="uf-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 required minLength={8} autoComplete="new-password" />
        </div>
        <div className="field">
          <label htmlFor="uf-role">Role</label>
          <select id="uf-role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="TEACHER">TEACHER</option>
            <option value="ADMIN">ADMIN</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="uf-teacher">Teacher profile</label>
          <select id="uf-teacher" value={teacherId} onChange={(e) => setTeacherId(e.target.value)}
                  required={role === 'TEACHER'} disabled={role === 'ADMIN'}>
            <option value="">{role === 'TEACHER' ? 'Select a teacher…' : '—'}</option>
            {teachers.map((t) => (
              <option key={t.teacher_id} value={t.teacher_id}>{fmtName(t)}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="modal-actions">
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary" disabled={busy}>
          <i className="fa-solid fa-user-plus" aria-hidden="true" /> Create user
        </button>
      </div>
    </form>
  )
}

export default function UsersPage() {
  const { session } = useAuth()
  const [rows, setRows] = useState(null)
  const [teachers, setTeachers] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    api.get('/users').then((data) => setRows(data.items ? data.items : data)).catch((err) => setError(err.message))
  }, [])

  useEffect(load, [load])

  useEffect(() => {
    api.get('/teachers?page_size=100').then((data) => setTeachers(data.items ? data.items : data)).catch(() => setTeachers([]))
  }, [])

  async function createUser(form) {
    setBusy(true)
    try {
      await api.post('/users', form)
      setAdding(false)
      load()
    } finally {
      setBusy(false)
    }
  }

  async function toggleActive(row) {
    const action = row.is_active ? 'deactivate' : 'activate'
    if (row.username === session.username) {
      setError('You cannot deactivate the account you are signed in with.')
      return
    }
    if (!confirmDialog(`${action.charAt(0).toUpperCase() + action.slice(1)} ${row.username}?`)) return
    try {
      await api.put(`/users/${row.id}/active`, { is_active: !row.is_active })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Users</h1>
        <button className="btn primary" onClick={() => setAdding(true)}>
          <i className="fa-solid fa-plus" aria-hidden="true" /> Create user
        </button>
      </div>
      <ErrorAlert message={error} />

      {rows === null ? (
        <div className="card"><Loading /></div>
      ) : rows.length === 0 ? (
        <div className="card"><Empty>No users yet.</Empty></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Username</th><th>Role</th><th>Status</th><th>Teacher</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.username}</td>
                  <td>{row.role}</td>
                  <td>
                    <span className={`badge ${row.is_active ? 'ok' : 'off'}`}>
                      <i className={`fa-solid ${row.is_active ? 'fa-circle-check' : 'fa-circle-xmark'}`} aria-hidden="true" />
                      {row.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>{row.teacher_name || <span className="muted">—</span>}</td>
                  <td>{fmtDate(row.created_at)}</td>
                  <td className="actions">
                    <span className="cell-actions">
                      <button className="btn small" onClick={() => toggleActive(row)} title={row.is_active ? 'Deactivate account' : 'Activate account'}>
                        <i className={`fa-solid ${row.is_active ? 'fa-user-slash' : 'fa-user-check'}`} aria-hidden="true" />
                        {row.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adding && (
        <Modal title="Create user" onClose={() => setAdding(false)}>
          <UserForm teachers={teachers} onSubmit={createUser} onCancel={() => setAdding(false)} busy={busy} />
        </Modal>
      )}
    </>
  )
}
