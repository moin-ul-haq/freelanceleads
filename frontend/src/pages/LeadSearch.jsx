import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { PageHeader, Card, Button, Input, Alert, Spinner, ScoreBadge, EmptyState } from '../components/ui'
import PitchModal from '../components/PitchModal'
import AddToPipelineModal from '../components/AddToPipelineModal'

// Survives navigation (lead detail → back) and page reloads within the tab,
// so search results never disappear when the user comes back.
const SEARCH_CACHE_KEY = 'fl_last_search'

function loadCachedSearch() {
  try { return JSON.parse(sessionStorage.getItem(SEARCH_CACHE_KEY)) || null } catch { return null }
}

export default function LeadSearch() {
  const { user } = useAuth()
  const cached = useRef(loadCachedSearch()).current
  const [niche, setNiche] = useState(cached?.niche || '')
  const [city, setCity] = useState(cached?.city || '')
  const [country, setCountry] = useState(cached?.country || '')
  const [results, setResults] = useState(cached?.results || null)
  const [meta, setMeta] = useState(cached?.meta || null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pitchLead, setPitchLead] = useState(null)
  const [pipelineLead, setPipelineLead] = useState(null)
  const pollRef = useRef(null)

  // Keep the cache in sync with whatever is on screen
  useEffect(() => {
    if (!results) return
    try {
      sessionStorage.setItem(SEARCH_CACHE_KEY, JSON.stringify({ niche, city, country, results, meta }))
    } catch { /* storage full — not critical */ }
  }, [results, meta, niche, city, country])

  const isFree = (user?.plan || 'free') === 'free'
  const auditsPending = results?.some((r) => !r.audit_done)

  // Poll audit progress (no quota cost) so scores + emails fill in live
  useEffect(() => {
    if (!auditsPending) return
    pollRef.current = setInterval(async () => {
      try {
        const ids = results.filter((r) => !r.audit_done).map((r) => r.id)
        if (!ids.length) return
        const data = await api.post('/leads/status/', { lead_ids: ids })
        const updated = new Map(data.results.map((r) => [r.id, r]))
        setResults((rs) => rs.map((r) => {
          const u = updated.get(r.id)
          // keep local is_saved state — status endpoint recomputes it anyway
          return u ? { ...u, is_saved: r.is_saved } : r
        }))
      } catch { /* transient poll errors are fine */ }
    }, 3000)
    return () => clearInterval(pollRef.current)
  }, [auditsPending, results])

  async function search(opts = {}) {
    if (!niche.trim() || !city.trim()) return
    setBusy(true)
    setError('')
    try {
      const body = { niche: niche.trim(), city: city.trim(), ...opts }
      if (country.trim()) body.country = country.trim()
      const data = await api.post('/leads/search/', body)
      setResults(data.results)
      setMeta(data)
      if (data.skipped_reason && !data.results.length) setError(data.skipped_reason)
    } catch (err) {
      setError(errorMessage(err, 'Search failed'))
    } finally {
      setBusy(false)
    }
  }

  function toggleSaved(lead) {
    const call = lead.is_saved
      ? api.del(`/leads/${lead.id}/save/`)
      : api.post(`/leads/${lead.id}/save/`, {})
    call
      .then(() => setResults((rs) => rs.map((r) => (r.id === lead.id ? { ...r, is_saved: !r.is_saved } : r))))
      .catch((err) => setError(errorMessage(err)))
  }

  return (
    <div>
      <PageHeader
        title="Find Leads"
        subtitle="Search local businesses by niche and city — scored 0-100 by how much they need your help."
      />

      <Card className="mb-6 p-5">
        <form onSubmit={(e) => { e.preventDefault(); search() }} className="grid gap-3 sm:grid-cols-[1fr_1fr_180px_auto]">
          <Input label="Niche" placeholder="plumber" value={niche} onChange={(e) => setNiche(e.target.value)} required />
          <Input label="City" placeholder="toronto" value={city} onChange={(e) => setCity(e.target.value)} required />
          <Input label="Country (optional)" placeholder="canada" value={country} onChange={(e) => setCountry(e.target.value)} />
          <div className="flex items-end">
            <Button type="submit" disabled={busy} className="h-[38px] w-full sm:w-auto">
              {busy ? <Spinner className="h-4 w-4 text-white" /> : 'Search'}
            </Button>
          </div>
        </form>
      </Card>

      <Alert>{error}</Alert>

      {meta && !error && (
        <div className="mb-3 mt-4 flex items-center justify-between text-sm text-slate-500">
          <span className="flex items-center gap-2">
            {meta.count} leads · source: <span className="font-medium">{meta.source}</span>
            {auditsPending && (
              <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                <Spinner className="h-3 w-3" /> auditing websites & finding emails…
              </span>
            )}
            {meta.cities_skipped?.length > 0 && ` · skipped: ${meta.cities_skipped.join(', ')}`}
          </span>
          {!isFree && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => search({ load_more: true })} disabled={busy}>Load more</Button>
              <Button variant="secondary" onClick={() => search({ refresh: true })} disabled={busy}>Refresh data</Button>
            </div>
          )}
        </div>
      )}

      {results && results.length === 0 && !error && (
        <EmptyState title="No leads found" subtitle="Try a different niche or city." />
      )}

      {results?.length > 0 && (
        <LeadsTable
          leads={results}
          onSave={toggleSaved}
          onPitch={setPitchLead}
          onPipeline={setPipelineLead}
        />
      )}

      <PitchModal lead={pitchLead} open={!!pitchLead} onClose={() => setPitchLead(null)} />
      <AddToPipelineModal lead={pipelineLead} open={!!pipelineLead} onClose={() => setPipelineLead(null)} />
    </div>
  )
}

export function LeadsTable({ leads, onSave, onPitch, onPipeline }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Business</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Rating</th>
              <th className="px-4 py-3">Website</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {leads.map((lead) => (
              <tr key={lead.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link to={`/leads/${lead.id}`} className="group block">
                    <div className="font-medium text-slate-900 group-hover:text-indigo-700 group-hover:underline">{lead.name}</div>
                    <div className="text-xs text-slate-400">{lead.city}{lead.country ? `, ${lead.country}` : ''}</div>
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <ScoreBadge score={lead.opportunity_score} label={lead.score_label} />
                  {!lead.audit_done && (
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-amber-600">
                      <Spinner className="h-2.5 w-2.5" /> auditing…
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {lead.rating != null ? `★ ${lead.rating} (${lead.review_count})` : '—'}
                </td>
                <td className="px-4 py-3">
                  {lead.website ? (
                    <a href={lead.website} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">
                      visit ↗
                    </a>
                  ) : (
                    <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-600">none</span>
                  )}
                </td>
                <td className="max-w-[200px] px-4 py-3">
                  {lead.email ? (
                    <a href={`mailto:${lead.email}`} className="block truncate font-medium text-emerald-700 hover:underline" title={lead.email}>
                      {lead.email}
                    </a>
                  ) : lead.audit_done ? (
                    <span className="text-xs text-slate-400">not found</span>
                  ) : (
                    <span className="text-xs text-amber-600">searching…</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">{lead.phone || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1.5">
                    <IconBtn title={lead.is_saved ? 'Unsave' : 'Save'} onClick={() => onSave(lead)}>
                      {lead.is_saved ? '⭐' : '☆'}
                    </IconBtn>
                    <IconBtn title="Generate AI pitch" onClick={() => onPitch(lead)}>🤖</IconBtn>
                    <IconBtn title="Add to pipeline" onClick={() => onPipeline(lead)}>📋</IconBtn>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function IconBtn({ children, ...props }) {
  return (
    <button
      className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm hover:border-indigo-300 hover:bg-indigo-50"
      type="button"
      {...props}
    >
      {children}
    </button>
  )
}
