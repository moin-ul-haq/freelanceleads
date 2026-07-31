import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { PageHeader, Card, Button, Alert, Spinner } from '../components/ui'

const LIMIT_LABELS = [
  ['search_limit', 'Lead searches / mo'],
  ['ai_pitch_limit', 'AI pitches / mo'],
  ['ai_chat_limit', 'AI chats / mo'],
  ['email_send_limit', 'Emails / mo'],
  ['saved_leads_limit', 'Saved leads'],
  ['bulk_search_limit', 'Bulk searches / mo'],
  ['team_seat_limit', 'Team seats'],
]

export default function Billing() {
  const { user } = useAuth()
  const [plans, setPlans] = useState(null)
  const [subscription, setSubscription] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busyPlan, setBusyPlan] = useState(null)

  useEffect(() => {
    api.get('/billing/plans/').then(setPlans).catch((err) => setError(errorMessage(err)))
    api.get('/billing/subscription/').then(setSubscription).catch(() => {})
    if (new URLSearchParams(window.location.search).get('upgrade') === 'success') {
      setInfo('Upgrade successful — welcome to your new plan! 🎉')
    }
  }, [])

  async function upgrade(planName) {
    setBusyPlan(planName)
    setError('')
    try {
      const data = await api.post('/billing/checkout/', { plan_name: planName })
      const url = data.session_url || data.checkout_url || data.url
      if (url) window.location.href = url
      else setError('Checkout session created but no redirect URL returned.')
    } catch (err) {
      setError(errorMessage(err, 'Checkout failed — is Stripe configured on the server?'))
    } finally {
      setBusyPlan(null)
    }
  }

  async function cancel() {
    if (!window.confirm('Cancel your subscription at the end of the current period?')) return
    setError('')
    try {
      await api.post('/billing/cancel/', { confirm: true })
      setInfo('Subscription will be cancelled at the end of the billing period.')
      api.get('/billing/subscription/').then(setSubscription).catch(() => {})
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!plans && !error) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  const currentPlan = user?.plan || 'free'

  return (
    <div>
      <PageHeader title="Billing" subtitle="Your plan, limits, and upgrades." />
      <Alert>{error}</Alert>
      <Alert kind="success">{info}</Alert>

      {subscription?.current_period_end && (
        <p className="mb-4 text-sm text-slate-500">
          Current period ends <strong>{String(subscription.current_period_end).slice(0, 10)}</strong>
          {subscription.status && <> · status <strong>{subscription.status}</strong></>}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {plans?.map((plan) => {
          const isCurrent = plan.name === currentPlan
          const highlight = plan.name === 'pro'
          return (
            <Card key={plan.id} className={`flex flex-col p-5 ${highlight ? 'border-indigo-300 ring-2 ring-indigo-100' : ''}`}>
              <div className="flex items-baseline justify-between">
                <h3 className="text-lg font-bold capitalize text-slate-900">{plan.name}</h3>
                {highlight && <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">Popular</span>}
              </div>
              <p className="mt-2 text-3xl font-extrabold text-slate-900">
                ${Number(plan.price_usd).toFixed(0)}
                <span className="text-sm font-medium text-slate-400">/mo</span>
              </p>

              <ul className="mt-4 flex-1 space-y-1.5 text-sm text-slate-600">
                {LIMIT_LABELS.map(([key, label]) =>
                  plan[key] !== undefined ? (
                    <li key={key} className="flex justify-between">
                      <span>{label}</span>
                      <span className="font-semibold text-slate-900">{plan[key] === -1 ? '∞' : plan[key]}</span>
                    </li>
                  ) : null
                )}
              </ul>

              {plan.features?.some((f) => f.is_enabled) && (
                <ul className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
                  {plan.features.filter((f) => f.is_enabled).map((f) => (
                    <li key={f.feature}>✓ {f.feature.replaceAll('_', ' ')}</li>
                  ))}
                </ul>
              )}

              <div className="mt-4">
                {isCurrent ? (
                  <div className="space-y-2">
                    <Button variant="secondary" disabled className="w-full">Current plan</Button>
                    {plan.name !== 'free' && (
                      <button onClick={cancel} className="w-full text-center text-xs text-slate-400 hover:text-red-600">
                        Cancel subscription
                      </button>
                    )}
                  </div>
                ) : plan.name === 'free' ? (
                  <Button variant="secondary" disabled className="w-full">—</Button>
                ) : (
                  <Button onClick={() => upgrade(plan.name)} disabled={busyPlan === plan.name} className="w-full">
                    {busyPlan === plan.name ? 'Redirecting…' : `Upgrade to ${plan.name}`}
                  </Button>
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
