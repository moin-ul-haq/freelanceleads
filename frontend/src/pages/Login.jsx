import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { Button, Alert } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Log in to your FreelanceLeads workspace."
    >
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <AuthInput label="Email" type="email" value={email} onChange={setEmail} autoFocus autoComplete="email" placeholder="you@company.com" />
        <PasswordInput label="Password" value={password} onChange={setPassword} autoComplete="current-password" />
        <Button type="submit" disabled={busy} className="w-full !py-2.5">
          {busy ? 'Signing in…' : 'Sign in →'}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        New to FreelanceLeads?{' '}
        <Link to="/register" className="font-semibold text-indigo-600 hover:underline">Create a free account</Link>
      </p>
    </AuthShell>
  )
}

/* ── shared split-screen shell ─────────────────────────────── */

const PROOF_POINTS = [
  ['🔍', 'Scored local leads from any niche + city in seconds'],
  ['📧', 'Real emails found and deliverability-verified'],
  ['🤖', 'AI pitches and one-page demo sites per lead'],
  ['📋', 'Pipeline, outreach sequences and reply inbox built in'],
]

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-full">
      {/* Brand panel */}
      <div className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-slate-950 p-10 text-white lg:flex">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_60%_at_20%_0%,#312e81_0%,transparent_60%),radial-gradient(60%_50%_at_100%_100%,#1e1b4b_0%,transparent_60%)]" />
        <Link to="/" className="relative flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500 text-sm font-bold">FL</span>
          <span className="text-lg font-bold">FreelanceLeads</span>
        </Link>

        <div className="relative">
          <h2 className="max-w-md text-3xl font-bold leading-tight">
            Your next client is already on Google Maps.
          </h2>
          <ul className="mt-8 space-y-4">
            {PROOF_POINTS.map(([icon, text]) => (
              <li key={text} className="flex items-start gap-3 text-[15px] text-slate-300">
                <span className="mt-0.5">{icon}</span> {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">
          © {new Date().getFullYear()} FreelanceLeads ·{' '}
          <Link to="/privacy" className="hover:text-slate-300">Privacy</Link> ·{' '}
          <Link to="/terms" className="hover:text-slate-300">Terms</Link>
        </p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center bg-white px-6 py-10">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold text-white">FL</span>
            <span className="text-lg font-bold text-slate-900">FreelanceLeads</span>
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
          {footer}
        </div>
      </div>
    </div>
  )
}

export function AuthInput({ label, value, onChange, ...props }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      <input
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-50"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        {...props}
      />
    </label>
  )
}

export function PasswordInput({ label, value, onChange, hint, ...props }) {
  const [visible, setVisible] = useState(false)
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 pr-11 text-sm text-slate-900 placeholder-slate-400 transition focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-50"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          placeholder="••••••••"
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-400 hover:text-slate-600"
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? '🙈' : '👁️'}
        </button>
      </div>
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}
