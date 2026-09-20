import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import StudentsPage from './pages/StudentsPage.jsx'
import CoursesPage from './pages/CoursesPage.jsx'
import TeachersPage from './pages/TeachersPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import AuditLogsPage from './pages/AuditLogsPage.jsx'

function RequireAuth({ children, adminOnly = false }) {
  const { session, isAdmin } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />
  return children
}

function initials(name) {
  return name.slice(0, 2).toUpperCase()
}

function Sidebar() {
  const { session, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      <NavLink to="/" className="brand">
        <img className="brand-mark" src="/brand-icon.png" alt="" aria-hidden="true" />
        <span className="brand-name">Student Manager</span>
      </NavLink>

      <nav className="side-nav" aria-label="Main navigation">
        <div className="side-section">Overview</div>
        <NavLink to="/" end>
          <span className="icon-slot"><i className="fa-solid fa-house" aria-hidden="true" /></span>
          Dashboard
        </NavLink>
        <div className="side-section">Manage</div>
        <NavLink to="/courses">
          <span className="icon-slot"><i className="fa-solid fa-book-open" aria-hidden="true" /></span>
          Courses
        </NavLink>
        {isAdmin && (
          <NavLink to="/students">
            <span className="icon-slot"><i className="fa-solid fa-users" aria-hidden="true" /></span>
            Students
          </NavLink>
        )}
        {isAdmin && (
          <NavLink to="/teachers">
            <span className="icon-slot"><i className="fa-solid fa-chalkboard-user" aria-hidden="true" /></span>
            Teachers
          </NavLink>
        )}
        {isAdmin && (
          <NavLink to="/users">
            <span className="icon-slot"><i className="fa-solid fa-user-gear" aria-hidden="true" /></span>
            Users
          </NavLink>
        )}
        {isAdmin && (
          <NavLink to="/audit-logs">
            <span className="icon-slot"><i className="fa-solid fa-clipboard-list" aria-hidden="true" /></span>
            Audit logs
          </NavLink>
        )}
      </nav>

      <div className="side-user">
        <span className="avatar" aria-hidden="true">{initials(session.username)}</span>
        <span className="who">
          <div className="name">{session.username}</div>
          <div className="role">{session.role}</div>
        </span>
        <button className="btn ghost small" onClick={handleLogout} title="Sign out">
          <i className="fa-solid fa-right-from-bracket" aria-hidden="true" /> Log out
        </button>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <div className="shell">
                <Sidebar />
                <main className="content">
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/students" element={<RequireAuth adminOnly><StudentsPage /></RequireAuth>} />
                    <Route path="/courses" element={<CoursesPage />} />
                    <Route path="/teachers" element={<RequireAuth adminOnly><TeachersPage /></RequireAuth>} />
                    <Route path="/users" element={<RequireAuth adminOnly><UsersPage /></RequireAuth>} />
                    <Route path="/audit-logs" element={<RequireAuth adminOnly><AuditLogsPage /></RequireAuth>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </main>
              </div>
            </RequireAuth>
          }
        />
      </Routes>
    </AuthProvider>
  )
}
