import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close dialog"
            title="Close"
          >
            <i className="fa-solid fa-xmark" aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function ErrorAlert({ message }) {
  if (!message) return null
  return (
    <div className="alert error" role="alert">
      {message}
    </div>
  )
}

export function Empty({ icon = 'fa-inbox', children }) {
  return (
    <div className="empty">
      <span className="empty-icon" aria-hidden="true">
        <i className={`fa-solid ${icon}`} />
      </span>
      {children}
    </div>
  )
}

export function Loading({ label = 'Loading…' }) {
  return <Empty>{label}</Empty>
}

export function Tooltip({ label, children }) {
  return (
    <span className="tip" tabIndex={0} aria-label={label} title={label}>
      {children}
    </span>
  )
}

export function fmtDate(value) {
  return value ? String(value).slice(0, 10) : '—'
}

export function fmtGrade(value) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(2)
}

export function fmtName(row) {
  return `${row.first_name} ${row.last_name}`
}

// Reuse the browser dialog for destructive actions — simple and native.
export function confirmDialog(message) {
  return window.confirm(message)
}

export function Pagination({ page, totalPages, total, onPage }) {
  if (totalPages <= 1) return null
  return (
    <div className="pagination">
      <span className="page-info">
        Page {page} of {totalPages} · {total} record{total === 1 ? '' : 's'}
      </span>
      <span className="page-buttons">
        <button className="btn small" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          <i className="fa-solid fa-chevron-left" aria-hidden="true" /> Prev
        </button>
        <button className="btn small" onClick={() => onPage(page + 1)} disabled={page >= totalPages}>
          Next <i className="fa-solid fa-chevron-right" aria-hidden="true" />
        </button>
      </span>
    </div>
  )
}

// Shared loader for paginated list endpoints ({items,...} envelope).
// Returns { rows, meta, load, setRows } — setRows lets callers refresh after edits.
export function usePagedList(resource, search, page, pageSize = 20) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    const params = new URLSearchParams({ search, page: String(page), page_size: String(pageSize) })
    // `resource` may already carry its own query (e.g. "audit-logs?action=...")
    // — join with & instead of adding a second ? in that case.
    const sep = resource.includes('?') ? '&' : '?'
    api
      .get(`/${resource}${sep}${params}`)
      .then(setData)
      .catch((err) => setError(err.message))
  }, [resource, search, page, pageSize])
  useEffect(() => {
    load()
  }, [load])
  return {
    rows: data ? data.items : null,
    meta: data, // null until first load
    error,
    setError,
    reload: load,
  }
}
