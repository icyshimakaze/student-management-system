const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

let authToken = localStorage.getItem('token') || null
let onSessionExpired = null

export function setSession(token) {
  authToken = token
  if (token) localStorage.setItem('token', token)
  else localStorage.removeItem('token')
}

export function getSession() {
  return authToken
}

// The router registers a callback so any 401 can bounce the user to login.
export function setSessionExpiredHandler(fn) {
  onSessionExpired = fn
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`

  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error('Cannot reach the API server. Is it running?')
  }

  if (response.status === 401 && authToken && onSessionExpired) {
    onSessionExpired()
  }

  if (response.status === 204) return null
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${response.status})`
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return data
}

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
