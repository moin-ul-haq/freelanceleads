import { useEffect, useState } from 'react'
import { api, errorMessage, getTokens, setTokens } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { PageHeader, Card, Button, Input, Alert } from '../components/ui'

export default function Settings() {
  return (
    <div>
      <PageHeader title="Settings" subtitle="Profile, security, and team." />
      <div className="grid gap-5 lg:grid-cols-2">
        <ProfileCard />
        <PasswordCard />
        <TeamCard />
      </div>
    </div>
  )
}

function ProfileCard() {
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({ first_name: '', last_name: '', username: '' })
  const [msg, setMsg] = useState({})

  useEffect(() => {
    if (user) setForm({ first_name: user.first_name || '', last_name: user.last_name || '', username: user.username || '' })
  }, [user])

  async function save(e) {
    e.preventDefault()
    setMsg({})
    try {
      await api.patch('/auth/me/', form)
      await refreshUser()
      setMsg({ ok: 'Profile updated.' })
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    }
  }

  return (
    <Card className="p-5">
      <h2 className="mb-4 text-base font-semibold text-slate-900">Profile</h2>
      <form onSubmit={save} className="space-y-3">
        <Alert>{msg.err}</Alert>
        <Alert kind="success">{msg.ok}</Alert>
        <div className="grid grid-cols-2 gap-3">
          <Input label="First name" value={form.first_name} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} />
          <Input label="Last name" value={form.last_name} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} />
        </div>
        <Input label="Username" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
        <Input label="Email" value={user?.email || ''} disabled className="bg-slate-50 text-slate-400" />
        <Button type="submit">Save profile</Button>
      </form>
    </Card>
  )
}

function PasswordCard() {
  const [form, setForm] = useState({ old_password: '', new_password: '' })
  const [msg, setMsg] = useState({})

  async function save(e) {
    e.preventDefault()
    setMsg({})
    try {
      const tokens = getTokens()
      const data = await api.post('/auth/change-password/', { ...form, refresh: tokens?.refresh })
      // Old refresh token is blacklisted server-side — store new tokens if returned
      if (data?.tokens) setTokens(data.tokens)
      else if (data?.access) setTokens({ ...tokens, ...data })
      setForm({ old_password: '', new_password: '' })
      setMsg({ ok: 'Password changed.' })
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    }
  }

  return (
    <Card className="p-5">
      <h2 className="mb-4 text-base font-semibold text-slate-900">Change password</h2>
      <form onSubmit={save} className="space-y-3">
        <Alert>{msg.err}</Alert>
        <Alert kind="success">{msg.ok}</Alert>
        <Input label="Current password" type="password" value={form.old_password} onChange={(e) => setForm((f) => ({ ...f, old_password: e.target.value }))} required />
        <Input label="New password" type="password" value={form.new_password} onChange={(e) => setForm((f) => ({ ...f, new_password: e.target.value }))} required minLength={8} />
        <Button type="submit">Update password</Button>
      </form>
    </Card>
  )
}

const ROLE_STYLES = {
  owner: 'bg-indigo-100 text-indigo-700',
  admin: 'bg-sky-100 text-sky-700',
  member: 'bg-slate-100 text-slate-600',
}

function TeamCard() {
  const { user, refreshUser } = useAuth()
  const [team, setTeam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [seatLimit, setSeatLimit] = useState(null)
  const [name, setName] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [newName, setNewName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState({})

  function load() {
    api.get('/auth/team/')
      .then((t) => setTeam(t))
      .catch(() => setTeam(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // seat limit comes from the owner's plan
    api.get('/billing/plans/')
      .then((plans) => {
        const mine = (Array.isArray(plans) ? plans : []).find((p) => p.name === (user?.plan || 'free'))
        if (mine && mine.team_seat_limit !== undefined) setSeatLimit(mine.team_seat_limit)
      })
      .catch(() => {})
  }, [user?.plan])

  const seats = team?.seats || []
  const mySeat = seats.find((s) => s.user?.id === user?.id)
  const canManage = mySeat && ['owner', 'admin'].includes(mySeat.role)
  const isOwner = mySeat?.role === 'owner'
  const seatsUsed = team?.seat_count ?? seats.length
  const limitLabel = seatLimit == null ? '' : seatLimit === -1 ? ' / ∞' : ` / ${seatLimit}`
  const seatsFull = seatLimit != null && seatLimit !== -1 && seatsUsed >= seatLimit

  async function run(fn, okMsg) {
    setBusy(true)
    setMsg({})
    try {
      await fn()
      if (okMsg) setMsg({ ok: okMsg })
      load()
      refreshUser?.()
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const createTeam = (e) => { e.preventDefault(); run(() => api.post('/auth/team/', { name }), 'Team created — you are the owner.') }
  const rename = (e) => {
    e.preventDefault()
    run(async () => { await api.patch('/auth/team/', { name: newName }); setRenaming(false) }, 'Team renamed.')
  }
  const invite = (e) => {
    e.preventDefault()
    run(async () => { await api.post('/auth/team/invite/', { email: inviteEmail }); setInviteEmail('') }, 'Member added to the team.')
  }
  const removeMember = (seat) => {
    if (!window.confirm(`Remove ${seat.user?.email} from the team?`)) return
    run(() => api.del(`/auth/team/members/${seat.id}/`), 'Member removed.')
  }
  const leaveTeam = () => {
    if (!window.confirm('Leave this team? You will go back to your own free quota.')) return
    run(() => api.post('/auth/team/leave/'), 'You left the team.')
  }
  const disband = () => {
    if (!window.confirm('Disband the team? All members lose access to the shared quota pool. This cannot be undone.')) return
    run(() => api.del('/auth/team/'), 'Team disbanded.')
  }

  return (
    <Card className="p-5 lg:col-span-2">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Team</h2>
        {team && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${seatsFull ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
            {seatsUsed}{limitLabel} seats
          </span>
        )}
      </div>
      <Alert>{msg.err}</Alert>
      <Alert kind="success">{msg.ok}</Alert>

      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : !team ? (
        <div className="mt-1 space-y-4">
          <p className="max-w-xl text-sm text-slate-500">
            Create a team to work with others — teammates share your plan's quota pool
            (searches, AI pitches, email sends) and see their own leads and pipelines.
            Seat limits depend on your plan.
          </p>
          <form onSubmit={createTeam} className="flex max-w-md items-end gap-2">
            <div className="flex-1">
              <Input label="Team name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="My agency" />
            </div>
            <Button type="submit" disabled={busy}>Create team</Button>
          </form>
        </div>
      ) : (
        <div className="mt-1 space-y-5">
          {/* name + rename */}
          <div className="flex flex-wrap items-center gap-3">
            {renaming ? (
              <form onSubmit={rename} className="flex items-end gap-2">
                <Input value={newName} onChange={(e) => setNewName(e.target.value)} required className="!py-1.5" />
                <Button type="submit" disabled={busy} className="!py-1.5">Save</Button>
                <Button type="button" variant="ghost" className="!py-1.5" onClick={() => setRenaming(false)}>Cancel</Button>
              </form>
            ) : (
              <>
                <span className="text-lg font-bold text-slate-900">{team.name}</span>
                {isOwner && (
                  <button onClick={() => { setNewName(team.name); setRenaming(true) }} className="text-xs text-slate-400 underline hover:text-indigo-600">
                    rename
                  </button>
                )}
              </>
            )}
            <span className="text-xs text-slate-400">
              Members share the owner's quota pool ({user?.plan || 'free'} plan).
            </span>
          </div>

          {/* members */}
          <div className="space-y-1.5">
            {seats.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-sm">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-sm font-bold uppercase text-indigo-600">
                    {(s.user?.username || s.user?.email || '?')[0]}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-900">
                      {s.user?.username}
                      {s.user?.id === user?.id && <span className="ml-1.5 text-xs font-normal text-slate-400">(you)</span>}
                    </p>
                    <p className="truncate text-xs text-slate-400">{s.user?.email}</p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {s.joined_at && <span className="hidden text-xs text-slate-400 sm:inline">joined {String(s.joined_at).slice(0, 10)}</span>}
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${ROLE_STYLES[s.role] || ROLE_STYLES.member}`}>
                    {s.role}
                  </span>
                  {canManage && s.role !== 'owner' && s.user?.id !== user?.id && (
                    <button onClick={() => removeMember(s)} disabled={busy} className="text-xs text-slate-400 hover:text-red-600">
                      Remove
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* invite */}
          {canManage && (
            <div>
              <form onSubmit={invite} className="flex max-w-md items-end gap-2">
                <div className="flex-1">
                  <Input
                    label="Add member by email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    required
                    placeholder="teammate@example.com"
                    disabled={seatsFull}
                  />
                </div>
                <Button type="submit" disabled={busy || seatsFull}>Add</Button>
              </form>
              <p className="mt-1 text-xs text-slate-400">
                {seatsFull
                  ? 'All seats are used — upgrade your plan for more seats.'
                  : 'They must already have a FreelanceLeads account with this email.'}
              </p>
            </div>
          )}

          {/* danger zone */}
          <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
            {isOwner ? (
              <Button variant="danger" onClick={disband} disabled={busy}>Disband team</Button>
            ) : (
              <Button variant="secondary" onClick={leaveTeam} disabled={busy}>Leave team</Button>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
