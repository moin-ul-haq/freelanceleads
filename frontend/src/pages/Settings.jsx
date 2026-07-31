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

function TeamCard() {
  const [team, setTeam] = useState(null)
  const [members, setMembers] = useState([])
  const [name, setName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [msg, setMsg] = useState({})

  function load() {
    api.get('/auth/team/')
      .then((t) => {
        setTeam(t)
        if (t) api.get('/auth/team/members/').then((m) => setMembers(Array.isArray(m) ? m : m.results || [])).catch(() => {})
      })
      .catch(() => setTeam(null))
  }
  useEffect(load, [])

  async function createTeam(e) {
    e.preventDefault()
    setMsg({})
    try {
      await api.post('/auth/team/', { name })
      setMsg({ ok: 'Team created.' })
      load()
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    }
  }

  async function invite(e) {
    e.preventDefault()
    setMsg({})
    try {
      await api.post('/auth/team/invite/', { email: inviteEmail })
      setInviteEmail('')
      setMsg({ ok: 'Member invited.' })
      load()
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    }
  }

  async function removeMember(seatId) {
    setMsg({})
    try {
      await api.del(`/auth/team/members/${seatId}/`)
      load()
    } catch (err) {
      setMsg({ err: errorMessage(err) })
    }
  }

  return (
    <Card className="p-5 lg:col-span-2">
      <h2 className="mb-4 text-base font-semibold text-slate-900">Team</h2>
      <Alert>{msg.err}</Alert>
      <Alert kind="success">{msg.ok}</Alert>

      {!team ? (
        <form onSubmit={createTeam} className="mt-2 flex max-w-md items-end gap-2">
          <div className="flex-1">
            <Input label="Team name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="My agency" />
          </div>
          <Button type="submit">Create team</Button>
        </form>
      ) : (
        <div className="mt-2 space-y-4">
          <p className="text-sm text-slate-600">
            Team: <strong className="text-slate-900">{team.name}</strong>
            <span className="ml-2 text-xs text-slate-400">Team members share the owner's quota pool.</span>
          </p>

          <div className="space-y-1.5">
            {members.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <span>{m.user_email || m.email || m.user?.email || m.user} <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{m.role}</span></span>
                {m.role !== 'owner' && (
                  <button onClick={() => removeMember(m.id)} className="text-xs text-slate-400 hover:text-red-600">Remove</button>
                )}
              </div>
            ))}
          </div>

          <form onSubmit={invite} className="flex max-w-md items-end gap-2">
            <div className="flex-1">
              <Input label="Invite by email" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required placeholder="teammate@example.com" />
            </div>
            <Button type="submit">Invite</Button>
          </form>
        </div>
      )}
    </Card>
  )
}
