import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'

const FEATURES = [
  {
    icon: '🔍',
    title: 'Find local leads instantly',
    text: 'Type a niche + city — get 20+ real businesses from Google Maps with phone, website, rating and address in seconds.',
  },
  {
    icon: '🎯',
    title: 'Opportunity scoring (0-100)',
    text: 'Every lead is auto-audited: no website, no SSL, slow pages, missing SEO, weak reviews. High score = easy pitch.',
  },
  {
    icon: '📧',
    title: 'Emails found for you',
    text: 'We crawl each business website and contact pages to dig out real email addresses — no manual hunting.',
  },
  {
    icon: '🤖',
    title: 'AI-written pitches',
    text: "Claude-quality cold emails referencing the exact problems we found on their site. Pick a tone, hit generate, send.",
  },
  {
    icon: '📋',
    title: 'Built-in CRM pipeline',
    text: 'Drag deals through New → Contacted → Won. Deal values, follow-up reminders, activity log, CSV export.',
  },
  {
    icon: '✉️',
    title: 'Outreach campaigns',
    text: 'Multi-step email sequences from your own Gmail/SMTP, open tracking, and a unified inbox for replies.',
  },
]

const STEPS = [
  ['Search', 'Enter "plumber + Toronto". We pull live data from Google Maps and audit every business website automatically.'],
  ['Pick winners', 'Sort by opportunity score — businesses with no website, broken SEO, or bad reviews are your easiest clients.'],
  ['Pitch & close', 'Generate a personalized AI pitch, email or WhatsApp them, and track the deal in your pipeline until it closes.'],
]

const LIMIT_LABELS = [
  ['search_limit', 'lead searches / mo'],
  ['ai_pitch_limit', 'AI pitches / mo'],
  ['email_send_limit', 'outreach emails / mo'],
  ['saved_leads_limit', 'saved leads'],
]

export default function Landing() {
  const { user } = useAuth()
  const [plans, setPlans] = useState([])

  useEffect(() => {
    api.get('/billing/plans/').then((d) => setPlans(Array.isArray(d) ? d : [])).catch(() => {})
  }, [])

  const primaryCta = user
    ? { to: '/dashboard', label: 'Open dashboard →' }
    : { to: '/register', label: 'Start free — no card needed' }

  return (
    <div className="min-h-full bg-white text-slate-900">
      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">FL</div>
            <span className="text-base font-bold">FreelanceLeads</span>
          </div>
          <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 sm:flex">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#how" className="hover:text-slate-900">How it works</a>
            <a href="#pricing" className="hover:text-slate-900">Pricing</a>
          </nav>
          <div className="flex items-center gap-2">
            {user ? (
              <Link to="/dashboard" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                Dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                  Sign in
                </Link>
                <Link to="/register" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_0%,#eef2ff_0%,transparent_70%)]" />
        <div className="relative mx-auto max-w-6xl px-6 pb-16 pt-20 text-center">
          <p className="mx-auto mb-4 w-fit rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
            For freelancers & agencies who sell websites, SEO and marketing
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            Find local businesses that <span className="text-indigo-600">desperately need</span> your services
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
            Search any niche in any city. Get scored leads with audited websites, real email addresses,
            and AI-written pitches — then close them with the built-in CRM.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to={primaryCta.to} className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700">
              {primaryCta.label}
            </Link>
            <a href="#how" className="rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              See how it works
            </a>
          </div>

          {/* Product mock */}
          <div className="mx-auto mt-14 max-w-4xl rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl shadow-slate-200">
            <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
              <div className="mb-3 flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-red-300" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
              </div>
              <div className="overflow-hidden rounded-lg border border-slate-200 bg-white text-left text-sm">
                <div className="grid grid-cols-[1fr_90px_90px_1fr] gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <span>Business</span><span>Score</span><span>Website</span><span>Email</span>
                </div>
                {[
                  ['Flyy City Barbershop', 85, 'hot', 'none', 'searching…'],
                  ['Iron Religion Gym', 55, 'warm', 'visit ↗', 'ironreligiongym@gmail.com'],
                  ['Bespoke BarberPub', 40, 'warm', 'visit ↗', 'info@bespokepub.com'],
                ].map(([name, score, label, site, email]) => (
                  <div key={name} className="grid grid-cols-[1fr_90px_90px_1fr] items-center gap-2 border-b border-slate-50 px-4 py-2.5">
                    <span className="font-medium">{name}</span>
                    <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-semibold ${label === 'hot' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                      {score} · {label}
                    </span>
                    <span className={site === 'none' ? 'w-fit rounded bg-red-50 px-1.5 text-xs font-medium text-red-600' : 'text-xs text-indigo-600'}>{site}</span>
                    <span className={`truncate text-xs ${email.includes('…') ? 'text-amber-600' : 'font-medium text-emerald-700'}`}>{email}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center text-3xl font-bold">Everything between "I need clients" and "invoice paid"</h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-slate-600">
          One dashboard replaces your lead scraper, email finder, cold-email writer and CRM.
        </p>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-2xl border border-slate-200 p-6 transition hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-50">
              <div className="text-2xl">{f.icon}</div>
              <h3 className="mt-3 font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="border-y border-slate-100 bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-center text-3xl font-bold">Three steps to your next client</h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map(([title, text], i) => (
              <div key={title} className="relative rounded-2xl bg-white p-6 shadow-sm">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">{i + 1}</div>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center text-3xl font-bold">Simple pricing</h2>
        <p className="mt-3 text-center text-slate-600">Start free. Upgrade when the leads start paying for themselves.</p>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {(plans.length ? plans : FALLBACK_PLANS).map((plan) => {
            const popular = plan.name === 'pro'
            return (
              <div
                key={plan.name}
                className={`relative flex flex-col rounded-2xl border p-6 ${popular ? 'border-indigo-300 shadow-xl shadow-indigo-100' : 'border-slate-200'}`}
              >
                {popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white">
                    Most popular
                  </span>
                )}
                <h3 className="text-lg font-bold capitalize">{plan.name}</h3>
                <p className="mt-2 text-4xl font-extrabold">
                  ${Number(plan.price_usd).toFixed(0)}
                  <span className="text-sm font-medium text-slate-400">/mo</span>
                </p>
                <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-600">
                  {LIMIT_LABELS.map(([key, label]) =>
                    plan[key] !== undefined ? (
                      <li key={key} className="flex items-center gap-2">
                        <span className="text-indigo-600">✓</span>
                        <span><strong className="text-slate-900">{plan[key] === -1 ? 'Unlimited' : plan[key]}</strong> {label}</span>
                      </li>
                    ) : null
                  )}
                </ul>
                <Link
                  to={user ? '/billing' : '/register'}
                  className={`mt-6 rounded-xl px-4 py-2.5 text-center text-sm font-semibold ${
                    popular ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {plan.name === 'free' ? 'Start free' : `Get ${plan.name}`}
                </Link>
              </div>
            )
          })}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="border-t border-slate-100 bg-gradient-to-b from-white to-indigo-50">
        <div className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold">Your next client is already on Google Maps</h2>
          <p className="mt-3 text-slate-600">Find them before another freelancer does.</p>
          <Link to={primaryCta.to} className="mt-8 inline-block rounded-xl bg-indigo-600 px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700">
            {primaryCta.label}
          </Link>
        </div>
      </section>

      <footer className="border-t border-slate-100">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-sm text-slate-400">
          <span>© {new Date().getFullYear()} FreelanceLeads</span>
          <div className="flex gap-5">
            <a href="#features" className="hover:text-slate-600">Features</a>
            <a href="#pricing" className="hover:text-slate-600">Pricing</a>
            <Link to="/login" className="hover:text-slate-600">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

const FALLBACK_PLANS = [
  { name: 'free', price_usd: 0, search_limit: 10, ai_pitch_limit: 5, email_send_limit: 10, saved_leads_limit: 20 },
  { name: 'pro', price_usd: 29, search_limit: 100, ai_pitch_limit: 100, email_send_limit: 2000, saved_leads_limit: -1 },
  { name: 'max', price_usd: 99, search_limit: 1500, ai_pitch_limit: -1, email_send_limit: -1, saved_leads_limit: -1 },
]
