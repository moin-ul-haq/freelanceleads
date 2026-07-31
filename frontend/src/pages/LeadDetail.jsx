import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { PageHeader, Card, Button, Spinner, Alert, ScoreBadge } from '../components/ui'
import PitchModal from '../components/PitchModal'
import AddToPipelineModal from '../components/AddToPipelineModal'
import GenerateSiteModal from '../components/GenerateSiteModal'

const EMAIL_STATUS = {
  deliverable: { label: '✓ deliverable', cls: 'bg-emerald-100 text-emerald-700' },
  risky: { label: '⚠ risky (catch-all)', cls: 'bg-amber-100 text-amber-700' },
  undeliverable: { label: '✗ undeliverable', cls: 'bg-red-100 text-red-700' },
  unknown: { label: '? unverified', cls: 'bg-slate-100 text-slate-500' },
}

export default function LeadDetail() {
  const { id } = useParams()
  const [lead, setLead] = useState(null)
  const [error, setError] = useState('')
  const [showPitch, setShowPitch] = useState(false)
  const [showPipeline, setShowPipeline] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [site, setSite] = useState(null)
  const [showSiteWizard, setShowSiteWizard] = useState(false)

  function load() {
    api.get(`/leads/${id}/`).then(setLead).catch((err) => setError(errorMessage(err)))
  }
  useEffect(load, [id])

  // While the audit is still running, refresh every 3s so results fill in live
  useEffect(() => {
    if (!lead || lead.audit_done) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [lead?.audit_done, id])

  async function verifyEmail() {
    setVerifying(true)
    try {
      const res = await api.post(`/leads/${lead.id}/verify-email/`)
      setLead((l) => ({ ...l, email_status: res.email_status }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setVerifying(false)
    }
  }

  async function toggleSave() {
    try {
      if (lead.is_saved) await api.del(`/leads/${lead.id}/save/`)
      else await api.post(`/leads/${lead.id}/save/`, {})
      setLead((l) => ({ ...l, is_saved: !l.is_saved }))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (error) return <div><Alert>{error}</Alert></div>
  if (!lead) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  const wa = lead.phone ? `https://wa.me/${lead.phone.replace(/[^\d]/g, '')}` : null

  const checks = [
    ['Website', lead.has_website, lead.website || 'No website found'],
    ['SSL certificate', lead.has_ssl, lead.has_ssl ? 'Secure (HTTPS)' : 'HTTP only — security warning shown to visitors'],
    ['Meta title', lead.has_meta_title, 'Search engines need this to rank the page'],
    ['Meta description', lead.has_meta_desc, 'Shown as the snippet in Google results'],
    ['Schema markup', lead.has_schema, 'Structured data for rich results'],
    ['Social media links', lead.has_social, 'FB / Instagram / X / LinkedIn presence'],
  ]

  return (
    <div>
      <PageHeader
        title={lead.name}
        subtitle={`${lead.niche} · ${lead.city}${lead.state ? `, ${lead.state}` : ''}${lead.country ? `, ${lead.country}` : ''}`}
      >
        <Button variant="secondary" onClick={toggleSave}>{lead.is_saved ? '⭐ Saved' : '☆ Save'}</Button>
        <Button variant="secondary" onClick={() => setShowPipeline(true)}>📋 Add to pipeline</Button>
        <Button variant="secondary" onClick={() => setShowSiteWizard(true)}>🌐 Build site</Button>
        <Button onClick={() => setShowPitch(true)}>🤖 Generate pitch</Button>
      </PageHeader>

      {site && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
          <span className="text-sm font-semibold text-emerald-800">🌐 Demo site ready:</span>
          <a href={site.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-emerald-700 underline">
            {site.url}
          </a>
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={() => navigator.clipboard.writeText(site.url)}>Copy link</Button>
            <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={() => setShowSiteWizard(true)}>Regenerate</Button>
          </div>
        </div>
      )}

      <Link to="/leads" className="mb-4 inline-block text-sm text-indigo-600 hover:underline">← Back to search</Link>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Opportunity */}
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">Opportunity</h3>
          <div className="flex items-center gap-3">
            <div className="relative flex h-20 w-20 items-center justify-center">
              <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#e2e8f0" strokeWidth="3.5" />
                <circle
                  cx="18" cy="18" r="15.9" fill="none"
                  stroke={lead.score_label === 'hot' ? '#ef4444' : lead.score_label === 'warm' ? '#f59e0b' : '#0ea5e9'}
                  strokeWidth="3.5" strokeLinecap="round"
                  strokeDasharray={`${lead.opportunity_score} ${100 - lead.opportunity_score}`}
                />
              </svg>
              <span className="absolute text-lg font-bold text-slate-900">{lead.opportunity_score}</span>
            </div>
            <div>
              <ScoreBadge score={lead.opportunity_score} label={lead.score_label} />
              {!lead.audit_done && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-600">
                  <Spinner className="h-3 w-3" /> audit running…
                </p>
              )}
            </div>
          </div>
          {lead.reasons?.length > 0 && (
            <ul className="mt-4 space-y-1.5 text-sm text-slate-600">
              {lead.reasons.map((r, i) => <li key={i}>⚠️ {r}</li>)}
            </ul>
          )}
        </Card>

        {/* Contact */}
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">Contact</h3>
          <dl className="space-y-2.5 text-sm">
            <ContactRow label="Email">
              {lead.email ? (
                <span className="flex flex-wrap items-center gap-2">
                  <a href={`mailto:${lead.email}`} className="font-medium text-indigo-600 hover:underline">{lead.email}</a>
                  {EMAIL_STATUS[lead.email_status] && (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${EMAIL_STATUS[lead.email_status].cls}`}>
                      {EMAIL_STATUS[lead.email_status].label}
                    </span>
                  )}
                  <button
                    onClick={verifyEmail}
                    disabled={verifying}
                    className="text-xs text-slate-400 underline hover:text-indigo-600"
                  >
                    {verifying ? 'checking…' : 'verify'}
                  </button>
                </span>
              ) : (
                <span className="text-slate-400">{lead.audit_done ? 'not found' : 'searching…'}</span>
              )}
            </ContactRow>
            <ContactRow label="Phone">
              {lead.phone || <span className="text-slate-400">—</span>}
            </ContactRow>
            <ContactRow label="WhatsApp">
              {wa
                ? <a href={wa} target="_blank" rel="noreferrer" className="font-medium text-emerald-600 hover:underline">Open chat ↗</a>
                : <span className="text-slate-400">—</span>}
            </ContactRow>
            <ContactRow label="Website">
              {lead.website
                ? <a href={lead.website} target="_blank" rel="noreferrer" className="break-all text-indigo-600 hover:underline">{lead.website} ↗</a>
                : <span className="font-medium text-red-600">none</span>}
            </ContactRow>
            <ContactRow label="Address">{lead.address || <span className="text-slate-400">—</span>}</ContactRow>
            <ContactRow label="Rating">
              {lead.rating != null ? `★ ${lead.rating} (${lead.review_count} reviews)` : <span className="text-slate-400">—</span>}
            </ContactRow>
          </dl>
        </Card>

        {/* Audit checklist */}
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">
            Website audit {lead.pagespeed_score != null && <span className="ml-1 text-xs font-normal text-slate-400">PageSpeed: {lead.pagespeed_score}/100</span>}
          </h3>
          <ul className="space-y-2">
            {checks.map(([label, ok, hint]) => (
              <li key={label} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`}>
                  {ok ? '✓' : '✕'}
                </span>
                <span>
                  <span className={ok ? 'text-slate-700' : 'font-medium text-slate-900'}>{label}</span>
                  {!ok && <span className="block text-xs text-slate-400">{hint}</span>}
                </span>
              </li>
            ))}
          </ul>
          {!lead.audit_done && <p className="mt-3 text-xs text-amber-600">Checks update automatically as the audit completes.</p>}
        </Card>
      </div>

      <PitchModal lead={showPitch ? lead : null} open={showPitch} onClose={() => setShowPitch(false)} />
      <AddToPipelineModal lead={showPipeline ? lead : null} open={showPipeline} onClose={() => setShowPipeline(false)} />
      <GenerateSiteModal
        lead={lead}
        open={showSiteWizard}
        onClose={() => setShowSiteWizard(false)}
        onGenerated={setSite}
      />
    </div>
  )
}

function ContactRow({ label, children }) {
  return (
    <div className="flex gap-3">
      <dt className="w-20 shrink-0 text-slate-400">{label}</dt>
      <dd className="min-w-0 flex-1 text-slate-700">{children}</dd>
    </div>
  )
}
