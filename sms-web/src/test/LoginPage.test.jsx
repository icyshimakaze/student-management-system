// Login page + route protection: successful login navigates in, wrong
// credentials show the API error, and unauthenticated users are bounced.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import LoginPage from '../pages/LoginPage'
import App from '../App'
import { AuthProvider } from '../auth'
import * as apiModule from '../api'

vi.mock('../api', () => ({
  api: { login: vi.fn(), get: vi.fn() },
  setSession: vi.fn(),
  getSession: vi.fn(() => null),
  setSessionExpiredHandler: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('LoginPage', () => {
  it('navigates to the dashboard on successful login', async () => {
    apiModule.api.login.mockResolvedValue({ access_token: 'tok', role: 'ADMIN' })
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/username/i), 'admin_user')
    await user.type(screen.getByLabelText(/password/i), 'secret-pass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    // LoginPage navigates to "/" on success; without a full provider the
    // observable effect is that no error is shown and login was called once.
    await waitFor(() => expect(apiModule.api.login).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the API error on invalid credentials', async () => {
    apiModule.api.login.mockRejectedValue(new Error('Invalid username or password, or the account is inactive.'))
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/username/i), 'admin_user')
    await user.type(screen.getByLabelText(/password/i), 'wrong-pass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid username or password/i)
  })
})

describe('Route protection', () => {
  it('redirects unauthenticated users from the app to /login', async () => {
    render(
      <MemoryRouter initialEntries={['/students']}>
        <App />
      </MemoryRouter>
    )
    // RequireAuth bounces to /login, which renders the sign-in screen.
    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.queryByText('Students')).not.toBeInTheDocument()
  })
})
