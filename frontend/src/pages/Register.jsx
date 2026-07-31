import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { Button, Input, Alert } from '../components/ui'
import { AuthShell } from './Login'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '', password2: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (form.password !== form.password2) { setError('Passwords do not match'); return }
    setBusy(true)
    setError('')
    try {
      await register(form.username, form.email, form.password, form.password2)
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err, 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Start finding local business clients today">
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <Input label="Username" value={form.username} onChange={set('username')} required autoFocus />
        <Input label="Email" type="email" value={form.email} onChange={set('email')} required />
        <Input label="Password" type="password" value={form.password} onChange={set('password')} required minLength={8} />
        <Input label="Confirm password" type="password" value={form.password2} onChange={set('password2')} required />
        <Button type="submit" disabled={busy} className="w-full">{busy ? 'Creating…' : 'Create account'}</Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        Already registered? <Link to="/login" className="font-medium text-indigo-600 hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  )
}
