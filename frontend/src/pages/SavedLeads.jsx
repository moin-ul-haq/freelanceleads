import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { PageHeader, Card, Spinner, ScoreBadge, EmptyState, Alert, Button } from '../components/ui'
import PitchModal from '../components/PitchModal'
import AddToPipelineModal from '../components/AddToPipelineModal'

export default function SavedLeads() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [pitchLead, setPitchLead] = useState(null)
  const [pipelineLead, setPipelineLead] = useState(null)

  function load() {
    api.get('/leads/saved/')
      .then((data) => setItems(data.results))
      .catch((err) => setError(errorMessage(err)))
  }

  useEffect(load, [])

  async function unsave(leadId) {
    try {
      await api.del(`/leads/${leadId}/save/`)
      setItems((xs) => xs.filter((x) => x.lead.id !== leadId))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!items && !error) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  return (
    <div>
      <PageHeader title="Saved Leads" subtitle="Your shortlist of promising businesses." />
      <Alert>{error}</Alert>

      {items?.length === 0 && (
        <EmptyState title="Nothing saved yet" subtitle="Star leads from search results to build your shortlist." />
      )}

      {items?.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card key={item.id} className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link to={`/leads/${item.lead.id}`} className="font-semibold text-slate-900 hover:text-indigo-700 hover:underline">
                    {item.lead.name}
                  </Link>
                  <p className="text-xs text-slate-400">
                    {item.lead.niche} · {item.lead.city}{item.lead.country ? `, ${item.lead.country}` : ''}
                  </p>
                </div>
                <ScoreBadge score={item.lead.opportunity_score} label={item.lead.score_label} />
              </div>

              <div className="mt-2 text-xs text-slate-500">
                {item.lead.rating != null && <span>★ {item.lead.rating} ({item.lead.review_count}) · </span>}
                {item.lead.website
                  ? <a href={item.lead.website} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">website ↗</a>
                  : <span className="text-red-600">no website</span>}
              </div>

              {item.notes && <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">{item.notes}</p>}

              <div className="mt-3 flex gap-2">
                <Button variant="secondary" className="flex-1 !px-2 !py-1.5 text-xs" onClick={() => setPitchLead(item.lead)}>🤖 Pitch</Button>
                <Button variant="secondary" className="flex-1 !px-2 !py-1.5 text-xs" onClick={() => setPipelineLead(item.lead)}>📋 Pipeline</Button>
                <Button variant="ghost" className="!px-2 !py-1.5 text-xs" onClick={() => unsave(item.lead.id)}>Remove</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <PitchModal lead={pitchLead} open={!!pitchLead} onClose={() => setPitchLead(null)} />
      <AddToPipelineModal lead={pipelineLead} open={!!pipelineLead} onClose={() => setPipelineLead(null)} />
    </div>
  )
}
