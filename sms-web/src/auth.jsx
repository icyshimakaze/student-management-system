import { createContext, useContext, useEffect, useState } from 'react'
import { api, setSession, getSession, setSessionExpiredHandler } from './api'

const AuthContext = createContext(null)

function decodeRole(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return { role: payload.role, username: payload.username }
  } catch {
    return { role: null, username: null }
  }
}

export function AuthProvider({ children }) {
  const [session, setSessionState] = useState(() => {
    const token = getSession()
    return token ? { token, ...decodeRole(token) } : null
  })

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setSession(null)
      setSessionState(null)
    })
  }, [])

  async function login(username, password) {
    const data = await api.login(username, password)
    setSession(data.access_token)
    setSessionState({ token: data.access_token, role: data.role, username })
    return data
  }

  function logout() {
    setSession(null)
    setSessionState(null)
  }

  return (
    <AuthContext.Provider value={{ session, login, logout, isAdmin: session?.role === 'ADMIN' }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
