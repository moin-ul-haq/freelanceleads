import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/leads', label: 'Find Leads', icon: '🔍' },
  { to: '/saved', label: 'Saved Leads', icon: '⭐' },
  { to: '/pipeline', label: 'Pipeline', icon: '📋' },
  { to: '/assistant', label: 'AI Assistant', icon: '🤖' },
  { to: '/outreach', label: 'Outreach', icon: '✉️' },
  { to: '/billing', label: 'Billing', icon: '💳' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">FL</div>
          <span className="text-base font-bold text-slate-900">FreelanceLeads</span>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <div className="mb-2 truncate text-sm font-medium text-slate-800">{user?.username}</div>
          <div className="mb-3 flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
              {user?.plan || 'free'} plan
            </span>
          </div>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="text-sm font-medium text-slate-500 hover:text-red-600"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
