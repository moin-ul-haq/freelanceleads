import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { Button, Alert } from '../components/ui'
import { AuthShell, AuthInput, PasswordInput } from './Login'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', password2: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e) {
    e.preventDefault()
    if (form.password !== form.password2) { setError('Passwords do not match'); return }
    setBusy(true)
    setError('')
    try {
      await register(form.first_name, form.last_name, form.email, form.password, form.password2)
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err, 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Free plan included — no credit card needed."
    >
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <div className="grid grid-cols-2 gap-3">
          <AuthInput label="First name" value={form.first_name} onChange={set('first_name')} autoFocus autoComplete="given-name" placeholder="Moin" />
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">Last name <span className="text-slate-400">(optional)</span></span>
            <input
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-50"
              value={form.last_name}
              onChange={(e) => set('last_name')(e.target.value)}
              autoComplete="family-name"
            />
          </label>
        </div>
        <AuthInput label="Work email" type="email" value={form.email} onChange={set('email')} autoComplete="email" placeholder="you@company.com" />
        <PasswordInput
          label="Password"
          value={form.password}
          onChange={set('password')}
          autoComplete="new-password"
          minLength={8}
          hint="At least 8 characters, not entirely numeric."
        />
        <PasswordInput label="Confirm password" value={form.password2} onChange={set('password2')} autoComplete="new-password" />
        <Button type="submit" disabled={busy} className="w-full !py-2.5">
          {busy ? 'Creating account…' : 'Create free account →'}
        </Button>
        <p className="text-center text-xs leading-relaxed text-slate-400">
          By creating an account you agree to our{' '}
          <Link to="/terms" className="text-indigo-600 hover:underline">Terms of Service</Link> and{' '}
          <Link to="/privacy" className="text-indigo-600 hover:underline">Privacy Policy</Link>.
        </p>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-indigo-600 hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  )
}
