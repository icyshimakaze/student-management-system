// Auth context behavior: login stores the token, logout clears it, and a
// 401 from the API expires the session automatically.
import { render, screen, waitFor, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from '../auth'
import * as apiModule from '../api'

function Probe() {
  const { session, login, logout, isAdmin } = useAuth()
  return (
    <div>
      <div>session:{session ? session.username : 'none'}</div>
      <div>role:{session ? session.role : 'none'}</div>
      <div>admin:{String(isAdmin)}</div>
      <button onClick={() => login('admin_user', 'secret-pass')}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  )
}

vi.mock('../api', () => ({
  api: { login: vi.fn() },
  setSession: vi.fn(),
  getSession: vi.fn(() => null),
  setSessionExpiredHandler: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('AuthProvider', () => {
  it('stores session with role after successful login', async () => {
    apiModule.api.login.mockResolvedValue({ access_token: 'tok', role: 'ADMIN' })
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await act(async () => screen.getByText('login').click())
    await waitFor(() => expect(screen.getByText('session:admin_user')).toBeInTheDocument())
    expect(screen.getByText('role:ADMIN')).toBeInTheDocument()
    expect(screen.getByText('admin:true')).toBeInTheDocument()
  })

  it('clears the session on logout', async () => {
    apiModule.api.login.mockResolvedValue({ access_token: 'tok', role: 'TEACHER' })
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    await act(async () => screen.getByText('login').click())
    await waitFor(() => expect(screen.getByText('session:admin_user')).toBeInTheDocument())
    await act(async () => screen.getByText('logout').click())
    expect(screen.getByText('session:none')).toBeInTheDocument()
    expect(screen.getByText('admin:false')).toBeInTheDocument()
  })

  it('expires the session when the API reports 401', async () => {
    let expireCallback
    apiModule.setSessionExpiredHandler.mockImplementation((fn) => {
      expireCallback = fn
    })
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    // provider registered the expiry handler
    await waitFor(() => expect(expireCallback).toBeTypeOf('function'))
    apiModule.api.login.mockResolvedValue({ access_token: 'tok', role: 'ADMIN' })
    await act(async () => screen.getByText('login').click())
    await waitFor(() => expect(screen.getByText('session:admin_user')).toBeInTheDocument())
    await act(async () => expireCallback())
    expect(screen.getByText('session:none')).toBeInTheDocument()
  })
})
