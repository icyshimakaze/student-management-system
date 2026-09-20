import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ErrorAlert } from '../ui'

export default function LoginPage() {
  const { session, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to="/" replace />

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <img className="brand-mark" src="/brand-icon.png" alt="" aria-hidden="true" />
        <h1>Welcome back</h1>
        <p className="sub">Sign in with your administrator or teacher account.</p>
        <ErrorAlert message={error} />
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button className="btn primary" disabled={busy || !username || !password}>
            {busy ? (
              'Signing in…'
            ) : (
              <>
                <i className="fa-solid fa-right-to-bracket" aria-hidden="true" /> Sign in
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
