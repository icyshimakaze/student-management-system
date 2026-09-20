import { useState } from 'react'
import { ErrorAlert, Empty, Loading, Modal, Pagination, usePagedList } from '../ui'

const ENTITY_TYPES = ['', 'user', 'student', 'teacher', 'course', 'enrollment']
const STATUSES = ['', 'SUCCESS', 'FAILED', 'REJECTED']

// Map raw action codes (student.create) to the wording admins actually read.
const ACTION_LABELS = {
  'user.login': 'Signed in',
  'user.create': 'Created user',
  'user.activate': 'Activated user',
  'user.deactivate': 'Deactivated user',
  'student.create': 'Added student',
  'student.update': 'Updated student',
  'student.delete': 'Removed student',
  'student.import': 'Imported students (CSV)',
  'teacher.create': 'Added teacher',
  'teacher.update': 'Updated teacher',
  'teacher.delete': 'Removed teacher',
  'course.create': 'Added course',
  'course.update': 'Updated course',
  'course.delete': 'Removed course',
  'enrollment.create': 'Enrolled student',
  'enrollment.delete': 'Removed enrollment',
  'grade.update': 'Updated grade',
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action
}

function StatusBadge({ value }) {
  const cls = value === 'SUCCESS' ? 'ok' : value === 'FAILED' ? 'danger' : 'warn'
  const icon = value === 'SUCCESS' ? 'fa-check' : value === 'FAILED' ? 'fa-triangle-exclamation' : 'fa-ban'
  return (
    <span className={`badge ${cls}`}>
      <i className={`fa-solid ${icon}`} aria-hidden="true" /> {value}
    </span>
  )
}

function fmtDetails(details) {
  // Normalize to either { pairs: [[key, value], ...] } or { text }.
  if (!details) return null
  let parsed = details
  if (typeof details === 'string') {
    try {
      parsed = JSON.parse(details)
    } catch {
      return { text: details }
    }
  }
  if (Array.isArray(parsed)) return { pairs: parsed }
  if (typeof parsed === 'object' && parsed !== null) {
    return { pairs: Object.entries(parsed) }
  }
  return { text: String(parsed) }
}

function DetailModal({ row, onClose }) {
  const details = fmtDetails(row.details)
  const pairs = details?.pairs || []
  const reasonPair = pairs.find(([key]) => key === 'reason')
  const failed = row.status && row.status !== 'SUCCESS'
  return (
    <Modal title={`Audit event — ${actionLabel(row.action)}`} onClose={onClose}>
      <dl className="detail-grid">
        <dt>When</dt><dd>{String(row.created_at).replace('T', ' ').slice(0, 19)}</dd>
        <dt>User</dt><dd>{row.username}</dd>
        <dt>Action</dt><dd>{actionLabel(row.action)} <span className="muted">({row.action})</span></dd>
        <dt>Entity</dt>
        <dd>
          {row.entity_type}
          {row.entity_id !== null && row.entity_id !== undefined ? ` #${row.entity_id}` : ''}
        </dd>
        <dt>Status</dt>
        <dd><StatusBadge value={row.status || 'SUCCESS'} /></dd>
        {failed && reasonPair ? (
          <>
            <dt>Reason</dt>
            <dd className="reason">{reasonPair[1]}</dd>
          </>
        ) : null}
      </dl>
      {details && (details.text || pairs.some(([key]) => !(failed && key === 'reason'))) && (
        <>
          <h3 className="detail-heading">Change details</h3>
          {details.text ? (
            <p>{details.text}</p>
          ) : (
            <table className="detail-table">
              <tbody>
                {pairs
                  .filter(([key]) => !(failed && key === 'reason'))
                  .map(([key, value]) => (
                    <tr key={key}>
                      <th>{String(key).replaceAll('_', ' ')}</th>
                      <td>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Modal>
  )
}

export default function AuditLogsPage() {
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
  const [username, setUsername] = useState('')
  const [status, setStatus] = useState('')
  const [submitted, setSubmitted] = useState({ action: '', entity_type: '', username: '', status: '' })
  const [page, setPage] = useState(1)
  const [viewing, setViewing] = useState(null)
  // Build the query inside the resource string, but only from the *submitted*
  // filter values so typing never fires requests mid-edit.
  const filters = new URLSearchParams({
    action: submitted.action,
    entity_type: submitted.entity_type,
    username: submitted.username,
    status: submitted.status,
  }).toString()
  const { rows, meta, error, reload } = usePagedList(`audit-logs?${filters}`, '', page)

  function applyFilter(event) {
    event.preventDefault()
    setPage(1)
    setSubmitted({ action, entity_type: entityType, username, status })
    reload()
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Audit logs</h1>
          <div className="sub">Who changed what, and when — every database change is recorded</div>
        </div>
      </div>
      <ErrorAlert message={error} />

      <form className="toolbar" onSubmit={applyFilter}>
        <input
          type="search"
          aria-label="Filter by action"
          placeholder="Action (e.g. student)…"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        />
        <select
          aria-label="Filter by entity type"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t || 'all'} value={t}>
              {t === '' ? 'All entity types' : t}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {STATUSES.map((s) => (
            <option key={s || 'all'} value={s}>
              {s === '' ? 'All statuses' : s}
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
                <th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Status</th><th><span className="sr-only">View</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.audit_id} className={row.status === 'SUCCESS' ? '' : 'row-flagged'}>
                  <td>{String(row.created_at).replace('T', ' ').slice(0, 19)}</td>
                  <td>{row.username}</td>
                  <td>{actionLabel(row.action)}</td>
                  <td>
                    {row.entity_type}
                    {row.entity_id !== null && row.entity_id !== undefined ? (
                      <span className="muted"> #{row.entity_id}</span>
                    ) : null}
                  </td>
                  <td><StatusBadge value={row.status || 'SUCCESS'} /></td>
                  <td className="actions">
                    <button
                      className="btn small icon-only"
                      title="View action details"
                      aria-label={`View details of ${actionLabel(row.action)} by ${row.username}`}
                      onClick={() => setViewing(row)}
                    >
                      <i className="fa-solid fa-eye" aria-hidden="true" />
                    </button>
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

      {viewing && <DetailModal row={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}
