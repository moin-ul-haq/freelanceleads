import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { PageHeader, Card, Button, Input, Alert, Spinner, ScoreBadge, EmptyState } from '../components/ui'
import PitchModal from '../components/PitchModal'
import AddToPipelineModal from '../components/AddToPipelineModal'
import BulkPitchModal from '../components/BulkPitchModal'

// Survives navigation (lead detail → back) and page reloads within the tab,
// so search results never disappear when the user comes back.
const SEARCH_CACHE_KEY = 'fl_last_search'

function loadCachedSearch() {
  try { return JSON.parse(sessionStorage.getItem(SEARCH_CACHE_KEY)) || null } catch { return null }
}

// "toronto, miami , dallas" → ["toronto", "miami", "dallas"]
function parseCities(raw) {
  return raw.split(',').map((c) => c.trim()).filter(Boolean).slice(0, 10)
}

export default function LeadSearch() {
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
  const [selected, setSelected] = useState(new Set())
  const [bulkPipelineOpen, setBulkPipelineOpen] = useState(false)
  const [bulkPitchOpen, setBulkPitchOpen] = useState(false)
  const [bulkMsg, setBulkMsg] = useState('')
  const pollRef = useRef(null)

  const auditsPending = results?.some((r) => !r.audit_done)
  const selectedLeads = results?.filter((r) => selected.has(r.id)) || []

  // Keep the cache in sync with whatever is on screen
  useEffect(() => {
    if (!results) return
    try {
      sessionStorage.setItem(SEARCH_CACHE_KEY, JSON.stringify({ niche, city, country, results, meta }))
    } catch { /* storage full — not critical */ }
  }, [results, meta, niche, city, country])

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
          return u ? { ...u, is_saved: r.is_saved } : r
        }))
      } catch { /* transient poll errors are fine */ }
    }, 3000)
    return () => clearInterval(pollRef.current)
  }, [auditsPending, results])

  async function search(opts = {}) {
    const cities = parseCities(city)
    if (!niche.trim() || !cities.length) return
    setBusy(true)
    setError('')
    setBulkMsg('')
    try {
      const body = { niche: niche.trim(), ...opts }
      if (cities.length === 1) body.city = cities[0]
      else body.cities = cities
      if (country.trim()) body.country = country.trim()
      const data = await api.post('/leads/search/', body)
      setResults(data.results)
      setMeta(data)
      setSelected(new Set())
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

  async function bulkSave() {
    setBulkMsg('')
    let saved = 0
    for (const lead of selectedLeads.filter((l) => !l.is_saved)) {
      try {
        await api.post(`/leads/${lead.id}/save/`, {})
        saved += 1
      } catch { /* keep going */ }
    }
    setResults((rs) => rs.map((r) => (selected.has(r.id) ? { ...r, is_saved: true } : r)))
    setBulkMsg(`Saved ${saved} leads ⭐`)
  }

  return (
    <div>
      <PageHeader
        title="Find Leads"
        subtitle="Search local businesses by niche and city — scored 0-100 by how much they need your help."
      />

      <Card className="mb-6 p-5">
        <form onSubmit={(e) => { e.preventDefault(); search() }} className="grid gap-3 sm:grid-cols-[1fr_1.2fr_180px_auto]">
          <Input label="Niche" placeholder="plumber" value={niche} onChange={(e) => setNiche(e.target.value)} required />
          <Input label="City (comma-separate for multiple)" placeholder="toronto, miami, dallas" value={city} onChange={(e) => setCity(e.target.value)} required />
          <Input label="Country (optional)" placeholder="canada" value={country} onChange={(e) => setCountry(e.target.value)} />
          <div className="flex items-end">
            <Button type="submit" disabled={busy} className="h-[38px] w-full sm:w-auto">
              {busy ? <Spinner className="h-4 w-4 text-white" /> : 'Search'}
            </Button>
          </div>
        </form>
        <p className="mt-2 text-xs text-slate-400">
          Up to 10 cities per search — each city uses one search credit.
        </p>
      </Card>

      <Alert>{error}</Alert>
      <Alert kind="success">{bulkMsg}</Alert>

      {meta && !error && (
        <div className="mb-3 mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <span className="flex items-center gap-2">
            {meta.count} leads · source: <span className="font-medium">{meta.source}</span>
            {meta.cities_searched?.length > 1 && ` · cities: ${meta.cities_searched.join(', ')}`}
            {auditsPending && (
              <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                <Spinner className="h-3 w-3" /> auditing websites & finding emails…
              </span>
            )}
            {meta.cities_skipped?.length > 0 && ` · skipped: ${meta.cities_skipped.join(', ')}`}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => search({ load_more: true })} disabled={busy}>Load more</Button>
            <Button variant="secondary" onClick={() => search({ refresh: true })} disabled={busy}>Refresh data</Button>
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="sticky top-2 z-10 mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 shadow-sm">
          <span className="text-sm font-semibold text-indigo-800">{selected.size} selected</span>
          <div className="ml-auto flex flex-wrap gap-2">
            <Button variant="secondary" className="!py-1.5 text-xs" onClick={bulkSave}>⭐ Save all</Button>
            <Button variant="secondary" className="!py-1.5 text-xs" onClick={() => setBulkPipelineOpen(true)}>📋 Add to pipeline</Button>
            <Button className="!py-1.5 text-xs" onClick={() => setBulkPitchOpen(true)}>🤖 Generate pitches</Button>
            <Button variant="ghost" className="!py-1.5 text-xs" onClick={() => setSelected(new Set())}>Clear</Button>
          </div>
        </div>
      )}

      {results && results.length === 0 && !error && (
        <EmptyState title="No leads found" subtitle="Try a different niche or city." />
      )}

      {results?.length > 0 && (
        <LeadsTable
          leads={results}
          selected={selected}
          onSelect={setSelected}
          onSave={toggleSaved}
          onPitch={setPitchLead}
          onPipeline={setPipelineLead}
        />
      )}

      <PitchModal lead={pitchLead} open={!!pitchLead} onClose={() => setPitchLead(null)} />
      <AddToPipelineModal lead={pipelineLead} open={!!pipelineLead} onClose={() => setPipelineLead(null)} />
      <AddToPipelineModal
        leads={selectedLeads}
        open={bulkPipelineOpen}
        onClose={() => setBulkPipelineOpen(false)}
        onAdded={(n) => setBulkMsg(`Added ${n} leads to pipeline 📋`)}
      />
      <BulkPitchModal leads={selectedLeads} open={bulkPitchOpen} onClose={() => setBulkPitchOpen(false)} />
    </div>
  )
}

export function LeadsTable({ leads, selected, onSelect, onSave, onPitch, onPipeline }) {
  const selectable = !!onSelect
  const allSelected = selectable && leads.length > 0 && leads.every((l) => selected.has(l.id))

  function toggleAll() {
    onSelect(allSelected ? new Set() : new Set(leads.map((l) => l.id)))
  }

  function toggleOne(id) {
    onSelect((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              {selectable && (
                <th className="w-10 px-3 py-3">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all" />
                </th>
              )}
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
              <tr key={lead.id} className={`hover:bg-slate-50 ${selected?.has(lead.id) ? 'bg-indigo-50/40' : ''}`}>
                {selectable && (
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(lead.id)}
                      onChange={() => toggleOne(lead.id)}
                      aria-label={`Select ${lead.name}`}
                    />
                  </td>
                )}
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
