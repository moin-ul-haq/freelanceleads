import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Card, PageHeader, Spinner } from '../components/ui'

const ACTION_LABELS = {
  search: 'Lead searches',
  ai_pitch: 'AI pitches',
  ai_chat: 'AI chats',
  email_send: 'Emails sent',
  backlink_search: 'Backlink searches',
  bulk_search: 'Bulk searches',
}

export default function Dashboard() {
  const { user } = useAuth()
  const [usage, setUsage] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([api.get('/billing/usage/'), api.get('/pipeline/stats/')])
      .then(([u, s]) => {
        if (u.status === 'fulfilled') setUsage(u.value)
        if (s.status === 'fulfilled') setStats(s.value)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user?.username} 👋`}
        subtitle="Here's how your lead generation is going this month."
      >
        <Link to="/leads" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          🔍 Find new leads
        </Link>
      </PageHeader>

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Leads in pipeline" value={stats.total_leads ?? 0} />
          <Stat label="Pipeline value" value={`$${Number(stats.total_deal_value ?? 0).toLocaleString()}`} />
          <Stat label="Won value" value={`$${Number(stats.won_value ?? 0).toLocaleString()}`} accent />
          <Stat label="Conversion rate" value={`${stats.conversion_rate ?? 0}%`} />
        </div>
      )}

      <Card className="p-5">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-base font-semibold text-slate-900">Monthly usage</h2>
          {usage?.reset_date && (
            <span className="text-xs text-slate-400">Period started {usage.reset_date} · {usage.plan} plan</span>
          )}
        </div>
        {usage?.usage?.length ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {usage.usage.map((u) => <UsageBar key={u.action} item={u} />)}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            No usage yet this month — run your first <Link className="text-indigo-600 hover:underline" to="/leads">lead search</Link> to get started.
          </p>
        )}
      </Card>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <QuickLink to="/leads" emoji="🔍" title="Search leads" text="Find local businesses by niche + city, scored by opportunity." />
        <QuickLink to="/pipeline" emoji="📋" title="Work your pipeline" text="Drag deals through stages and track deal value." />
        <QuickLink to="/assistant" emoji="🤖" title="Ask the AI" text="Get help with pitches, pricing, and objection handling." />
      </div>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ? 'text-emerald-600' : 'text-slate-900'}`}>{value}</p>
    </Card>
  )
}

function UsageBar({ item }) {
  const unlimited = item.limit === -1
  const pct = unlimited ? 0 : Math.min(100, Math.round((item.count / Math.max(item.limit, 1)) * 100))
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium text-slate-700">{ACTION_LABELS[item.action] || item.action}</span>
        <span className={item.is_exhausted ? 'font-semibold text-red-600' : 'text-slate-500'}>
          {unlimited ? `${item.count} / ∞` : `${item.count} / ${item.limit}`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${item.is_exhausted ? 'bg-red-500' : pct > 75 ? 'bg-amber-500' : 'bg-indigo-500'}`}
          style={{ width: unlimited ? '4%' : `${pct}%` }}
        />
      </div>
    </div>
  )
}

function QuickLink({ to, emoji, title, text }) {
  return (
    <Link to={to} className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-300 hover:shadow">
      <div className="text-xl">{emoji}</div>
      <p className="mt-2 text-sm font-semibold text-slate-900 group-hover:text-indigo-700">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{text}</p>
    </Link>
  )
}
