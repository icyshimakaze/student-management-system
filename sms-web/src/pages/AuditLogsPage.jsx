import { useState } from 'react'
import { ErrorAlert, Empty, Loading, Pagination, usePagedList } from '../ui'

const ENTITY_TYPES = ['', 'user', 'student', 'teacher', 'course', 'enrollment']

function fmtDetails(details) {
  if (!details) return <span className="muted">—</span>
  let parsed = details
  if (typeof details === 'string') {
    try {
      parsed = JSON.parse(details)
    } catch {
      return <span className="muted">{details}</span>
    }
  }
  const parts = Object.entries(parsed).map(([key, value]) => `${key}: ${value}`)
  return <span>{parts.join(' · ')}</span>
}

export default function AuditLogsPage() {
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
  const [username, setUsername] = useState('')
  const [submitted, setSubmitted] = useState({ action: '', entity_type: '', username: '' })
  const [page, setPage] = useState(1)
  // Build the query inside the resource string, but only from the *submitted*
  // filter values so typing never fires requests mid-edit.
  const filters = new URLSearchParams({
    action: submitted.action,
    entity_type: submitted.entity_type,
    username: submitted.username,
  }).toString()
  const { rows, meta, error, reload } = usePagedList(`audit-logs?${filters}`, '', page)

  function applyFilter(event) {
    event.preventDefault()
    setPage(1)
    setSubmitted({ action, entity_type: entityType, username })
    reload()
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Audit logs</h1>
          <div className="sub">Who changed what, and when</div>
        </div>
      </div>
      <ErrorAlert message={error} />

      <form className="toolbar" onSubmit={applyFilter}>
        <input
          type="search"
          aria-label="Filter by action"
          placeholder="Action (e.g. grade.update)…"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        />
        <select
          aria-label="Filter by entity type"
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value)
            setPage(1)
          }}
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t || 'all'} value={t}>
              {t === '' ? 'All entity types' : t}
            </option>
          ))}
        </select>
        <input
          type="search"
          aria-label="Filter by username"
          placeholder="Username…"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <button type="submit" className="btn">
          <i className="fa-solid fa-filter" aria-hidden="true" /> Apply
        </button>
      </form>

      {rows === null ? (
        <div className="card"><Loading /></div>
      ) : rows.length === 0 ? (
        <div className="card"><Empty icon="fa-clipboard-list">No audit events match.</Empty></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.audit_id}>
                  <td>{String(row.created_at).replace('T', ' ').slice(0, 19)}</td>
                  <td>{row.username}</td>
                  <td><span className="badge">{row.action}</span></td>
                  <td>
                    {row.entity_type}
                    {row.entity_id !== null && row.entity_id !== undefined ? (
                      <span className="muted"> #{row.entity_id}</span>
                    ) : null}
                  </td>
                  <td>{fmtDetails(row.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows !== null && rows.length > 0 && (
        <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} onPage={setPage} />
      )}
    </>
  )
}
