import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { PageHeader, Card, Button, Input, Select, Alert, Spinner, EmptyState, Modal } from '../components/ui'

const TABS = ['Campaigns', 'Inbox', 'Email Accounts']

export default function Outreach() {
  const [tab, setTab] = useState('Campaigns')

  return (
    <div>
      <PageHeader title="Outreach" subtitle="Email campaigns, replies, and connected sending accounts." />

      <div className="mb-5 flex gap-1 rounded-lg bg-slate-100 p-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
              tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Campaigns' && <CampaignsTab />}
      {tab === 'Inbox' && <InboxTab />}
      {tab === 'Email Accounts' && <AccountsTab />}
    </div>
  )
}

/* ── Campaigns ─────────────────────────────────────────────── */

function CampaignsTab() {
  const [campaigns, setCampaigns] = useState(null)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [selected, setSelected] = useState(null)

  function load() {
    api.get('/outreach/campaigns/')
      .then((d) => setCampaigns(Array.isArray(d) ? d : d.results || []))
      .catch((err) => setError(errorMessage(err)))
  }
  useEffect(load, [])

  if (!campaigns && !error) return <Center><Spinner className="h-7 w-7" /></Center>

  return (
    <div>
      <Alert>{error}</Alert>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreating(true)}>+ New campaign</Button>
      </div>

      {campaigns?.length === 0 && (
        <EmptyState
          title="No campaigns yet"
          subtitle="Create a campaign, add email steps, then enroll saved leads that have an email address."
        >
          <Button onClick={() => setCreating(true)}>Create campaign</Button>
        </EmptyState>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {campaigns?.map((c) => (
          <Card key={c.id} className="cursor-pointer p-4 transition hover:border-indigo-300" >
            <button className="w-full text-left" onClick={() => setSelected(c)}>
              <div className="flex items-center justify-between">
                <p className="font-semibold text-slate-900">{c.name}</p>
                <StatusPill status={c.status} />
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {c.steps?.length || 0} steps · {c.enrolled_count ?? 0} leads enrolled
              </p>
            </button>
          </Card>
        ))}
      </div>

      <CreateCampaignModal open={creating} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load() }} />
      {selected && (
        <CampaignDetailModal
          campaign={selected}
          onClose={() => setSelected(null)}
          onChanged={() => { load() }}
        />
      )}
    </div>
  )
}

function StatusPill({ status }) {
  const styles = {
    active: 'bg-emerald-100 text-emerald-700',
    paused: 'bg-amber-100 text-amber-700',
    draft: 'bg-slate-100 text-slate-600',
  }
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${styles[status] || styles.draft}`}>{status}</span>
}

function CreateCampaignModal({ open, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.post('/outreach/campaigns/', { name })
      setName('')
      onCreated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New campaign">
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <Input label="Campaign name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="Toronto plumbers — March" />
        <Button type="submit" disabled={busy} className="w-full">{busy ? 'Creating…' : 'Create'}</Button>
      </form>
    </Modal>
  )
}

function CampaignDetailModal({ campaign, onClose, onChanged }) {
  const [detail, setDetail] = useState(campaign)
  const [analytics, setAnalytics] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [step, setStep] = useState({ step_order: (campaign.steps?.length || 0) + 1, delay_days: 0, subject_template: '', body_template: '' })
  const [savedLeads, setSavedLeads] = useState([])
  const [checked, setChecked] = useState(new Set())

  function reload() {
    api.get(`/outreach/campaigns/${campaign.id}/`).then(setDetail).catch(() => {})
    api.get(`/outreach/campaigns/${campaign.id}/analytics/`).then(setAnalytics).catch(() => {})
  }

  useEffect(() => {
    reload()
    api.get('/leads/saved/')
      .then((d) => setSavedLeads((d.results || []).filter((s) => s.lead)))
      .catch(() => {})
  }, [campaign.id])

  async function addStep(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/outreach/campaigns/steps/', { campaign_id: campaign.id, ...step })
      setStep({ step_order: (detail.steps?.length || 0) + 2, delay_days: 3, subject_template: '', body_template: '' })
      setInfo('Step added.')
      reload()
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function enroll() {
    setError('')
    setInfo('')
    try {
      const res = await api.post(`/outreach/campaigns/${campaign.id}/enroll/`, { lead_ids: [...checked] })
      setInfo(`Enrolled ${res.count} leads${res.skipped?.length ? ` · skipped ${res.skipped.length} (no email)` : ''}.`)
      setChecked(new Set())
      reload()
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function setStatus(status) {
    setError('')
    try {
      await api.patch(`/outreach/campaigns/${campaign.id}/`, { status })
      reload()
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal open onClose={onClose} title={detail.name} wide>
      <div className="space-y-5">
        <Alert>{error}</Alert>
        <Alert kind="success">{info}</Alert>

        <div className="flex items-center justify-between">
          <StatusPill status={detail.status} />
          <div className="flex gap-2">
            {detail.status !== 'active' && <Button onClick={() => setStatus('active')}>▶ Launch</Button>}
            {detail.status === 'active' && <Button variant="secondary" onClick={() => setStatus('paused')}>⏸ Pause</Button>}
            <Button
              variant="danger"
              onClick={async () => {
                if (!window.confirm('Delete this campaign and its history?')) return
                try { await api.del(`/outreach/campaigns/${campaign.id}/`); onChanged(); onClose() } catch (err) { setError(errorMessage(err)) }
              }}
            >
              Delete
            </Button>
          </div>
        </div>

        {analytics && (
          <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center text-xs sm:grid-cols-6">
            <Metric label="Enrolled" value={analytics.total_enrolled} />
            <Metric label="Sent" value={analytics.total_sent} />
            <Metric label="Opened" value={analytics.total_opened} />
            <Metric label="Open rate" value={`${analytics.open_rate ?? 0}%`} />
            <Metric label="Reply rate" value={`${analytics.reply_rate ?? 0}%`} />
            <Metric label="Bounced" value={analytics.bounced ?? 0} />
          </div>
        )}

        <section>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Email steps</h4>
          {detail.steps?.length ? (
            <ol className="space-y-2">
              {detail.steps.map((s) => (
                <li key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-2.5 text-sm">
                  <span>
                    <span className="font-medium">Step {s.step_order}</span>
                    <span className="text-slate-400"> · wait {s.delay_days}d · </span>
                    <span className="text-slate-600">{s.subject_template}</span>
                  </span>
                  <button
                    onClick={async () => {
                      if (!window.confirm(`Delete step ${s.step_order}?`)) return
                      try { await api.del(`/outreach/campaigns/steps/${s.id}/`); reload(); onChanged() } catch (err) { setError(errorMessage(err)) }
                    }}
                    className="text-xs text-slate-400 hover:text-red-600"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ol>
          ) : <p className="text-sm text-slate-400">No steps yet — add the first email below.</p>}

          <form onSubmit={addStep} className="mt-3 space-y-2 rounded-lg bg-slate-50 p-3">
            <div className="grid grid-cols-2 gap-2">
              <Input label="Step order" type="number" min="1" value={step.step_order} onChange={(e) => setStep((s) => ({ ...s, step_order: Number(e.target.value) }))} />
              <Input label="Delay (days)" type="number" min="0" value={step.delay_days} onChange={(e) => setStep((s) => ({ ...s, delay_days: Number(e.target.value) }))} />
            </div>
            <Input label="Subject" placeholder="Quick question about {{business_name}}" value={step.subject_template} onChange={(e) => setStep((s) => ({ ...s, subject_template: e.target.value }))} required />
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Body</span>
              <textarea
                rows={4}
                required
                value={step.body_template}
                onChange={(e) => setStep((s) => ({ ...s, body_template: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                placeholder="Hi {{business_name}}, I noticed…"
              />
            </label>
            <Button type="submit" variant="secondary">+ Add step</Button>
          </form>
        </section>

        <section>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Enroll saved leads</h4>
          {savedLeads.length === 0 && <p className="text-sm text-slate-400">No saved leads — star some leads first.</p>}
          {savedLeads.length > 0 && (
            <>
              <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
                {savedLeads.map((s) => {
                  const hasEmail = !!s.lead.email
                  return (
                    <label key={s.lead.id} className={`flex items-center gap-2 rounded px-2 py-1 text-sm ${hasEmail ? 'hover:bg-slate-50' : 'opacity-50'}`}>
                      <input
                        type="checkbox"
                        disabled={!hasEmail}
                        checked={checked.has(s.lead.id)}
                        onChange={(e) => {
                          setChecked((prev) => {
                            const next = new Set(prev)
                            e.target.checked ? next.add(s.lead.id) : next.delete(s.lead.id)
                            return next
                          })
                        }}
                      />
                      <span className="flex-1">{s.lead.name}</span>
                      <span className="text-xs text-slate-400">{hasEmail ? s.lead.email || 'has email' : 'no email'}</span>
                    </label>
                  )
                })}
              </div>
              <Button className="mt-2" onClick={enroll} disabled={checked.size === 0}>
                Enroll {checked.size || ''} selected
              </Button>
            </>
          )}
        </section>
      </div>
    </Modal>
  )
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="text-sm font-bold text-slate-900">{value ?? 0}</p>
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  )
}

/* ── Inbox ─────────────────────────────────────────────────── */

function InboxTab() {
  const [replies, setReplies] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/outreach/inbox/')
      .then((d) => setReplies(Array.isArray(d) ? d : d.results || []))
      .catch((err) => setError(errorMessage(err)))
  }, [])

  if (!replies && !error) return <Center><Spinner className="h-7 w-7" /></Center>

  return (
    <div>
      <Alert>{error}</Alert>
      {replies?.length === 0 && (
        <EmptyState title="Inbox is empty" subtitle="Replies to your campaigns will appear here, matched to the lead automatically." />
      )}
      <div className="space-y-2">
        {replies?.map((r) => (
          <Card key={r.id} className="p-4">
            <div className="flex items-baseline justify-between">
              <p className="text-sm font-semibold text-slate-900">{r.lead_name || r.from_email}</p>
              <span className="text-xs text-slate-400">{r.received_at?.slice(0, 10)}</span>
            </div>
            <p className="text-xs text-slate-400">{r.from_email} · {r.campaign_name}</p>
            <p className="mt-1 text-sm font-medium text-slate-700">{r.subject}</p>
            <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-slate-500">{r.body}</p>
          </Card>
        ))}
      </div>
    </div>
  )
}

/* ── Email accounts ────────────────────────────────────────── */

function AccountsTab() {
  const [accounts, setAccounts] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [showSmtp, setShowSmtp] = useState(false)
  const [form, setForm] = useState({
    email_address: '', provider: 'custom',
    smtp_host: '', smtp_port: 587, smtp_username: '', smtp_password: '',
    imap_host: '', imap_port: 993, imap_username: '', imap_password: '',
  })

  function load() {
    api.get('/outreach/accounts/')
      .then((d) => setAccounts(Array.isArray(d) ? d : d.results || []))
      .catch((err) => setError(errorMessage(err)))
  }
  useEffect(load, [])

  async function connectGoogle() {
    setError('')
    try {
      const { auth_url } = await api.get('/outreach/google/auth-url/')
      window.location.href = auth_url
    } catch (err) {
      setError(errorMessage(err, 'Google OAuth is not configured on the server (GOOGLE_CLIENT_ID/SECRET).'))
    }
  }

  async function addSmtp(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/outreach/accounts/', form)
      setInfo('Account connected.')
      setShowSmtp(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  if (!accounts && !error) return <Center><Spinner className="h-7 w-7" /></Center>

  return (
    <div>
      <Alert>{error}</Alert>
      <Alert kind="success">{info}</Alert>

      <div className="mb-4 flex gap-2">
        <Button onClick={connectGoogle}>Connect Gmail</Button>
        <Button variant="secondary" onClick={() => setShowSmtp(true)}>+ Custom SMTP/IMAP</Button>
      </div>

      {accounts?.length === 0 && (
        <EmptyState title="No sending accounts" subtitle="Connect Gmail or a custom SMTP account to launch campaigns from your own address." />
      )}

      <div className="space-y-2">
        {accounts?.map((a) => (
          <Card key={a.id} className="flex items-center justify-between p-4">
            <div>
              <p className="text-sm font-semibold text-slate-900">{a.email_address}</p>
              <p className="text-xs text-slate-400">{a.provider} · connected {a.created_at?.slice(0, 10)}</p>
            </div>
            <span className="flex items-center gap-3">
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">connected</span>
              <button
                onClick={async () => {
                  if (!window.confirm(`Disconnect ${a.email_address}? Stored tokens are deleted.`)) return
                  try { await api.del(`/outreach/accounts/${a.id}/`); load() } catch (err) { setError(errorMessage(err)) }
                }}
                className="text-xs text-slate-400 hover:text-red-600"
              >
                Disconnect
              </button>
            </span>
          </Card>
        ))}
      </div>

      <Modal open={showSmtp} onClose={() => setShowSmtp(false)} title="Custom SMTP / IMAP account" wide>
        <form onSubmit={addSmtp} className="space-y-3">
          <Input label="Email address" type="email" value={form.email_address} onChange={set('email_address')} required />
          <div className="grid grid-cols-2 gap-3">
            <Input label="SMTP host" value={form.smtp_host} onChange={set('smtp_host')} required placeholder="smtp.example.com" />
            <Input label="SMTP port" type="number" value={form.smtp_port} onChange={set('smtp_port')} required />
            <Input label="SMTP username" value={form.smtp_username} onChange={set('smtp_username')} required />
            <Input label="SMTP password" type="password" value={form.smtp_password} onChange={set('smtp_password')} required />
            <Input label="IMAP host" value={form.imap_host} onChange={set('imap_host')} placeholder="imap.example.com" />
            <Input label="IMAP port" type="number" value={form.imap_port} onChange={set('imap_port')} />
            <Input label="IMAP username" value={form.imap_username} onChange={set('imap_username')} />
            <Input label="IMAP password" type="password" value={form.imap_password} onChange={set('imap_password')} />
          </div>
          <Button type="submit" className="w-full">Connect account</Button>
        </form>
      </Modal>
    </div>
  )
}

function Center({ children }) {
  return <div className="flex justify-center py-16">{children}</div>
}
