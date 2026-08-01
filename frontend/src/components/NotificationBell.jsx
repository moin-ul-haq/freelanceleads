import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const TYPE_ICONS = { open: '👀', reply: '💬', inquiry: '📬', bounce: '⚠️', system: 'ℹ️' }

function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const panelRef = useRef(null)
  const navigate = useNavigate()

  async function refresh() {
    try {
      const d = await api.get('/auth/notifications/')
      setItems(d.results)
      setUnread(d.unread_count)
    } catch { /* transient */ }
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 30000)
    return () => clearInterval(t)
  }, [])

  // close on outside click
  useEffect(() => {
    if (!open) return
    const onClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  async function openPanel() {
    setOpen((o) => !o)
    if (!open && unread > 0) {
      try {
        await api.post('/auth/notifications/', { all: true })
        setUnread(0)
      } catch { /* transient */ }
    }
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={openPanel}
        className="relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100"
      >
        <span className="text-base leading-none">🔔</span>
        Notifications
        {unread > 0 && (
          <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-2 max-h-96 w-80 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-900">
            Notifications
          </div>
          {items.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-slate-400">
              Nothing yet — opens, replies and inquiries will show up here.
            </p>
          )}
          {items.map((n) => (
            <button
              key={n.id}
              onClick={() => { setOpen(false); if (n.link) navigate(n.link) }}
              className={`block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50 ${!n.is_read ? 'bg-indigo-50/50' : ''}`}
            >
              <p className="flex items-start gap-2 text-sm font-medium text-slate-900">
                <span>{TYPE_ICONS[n.type] || 'ℹ️'}</span>
                <span className="flex-1">{n.title}</span>
              </p>
              {n.body && <p className="mt-0.5 line-clamp-2 pl-6 text-xs text-slate-500">{n.body}</p>}
              <p className="mt-1 pl-6 text-[11px] text-slate-400">{timeAgo(n.created_at)}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
