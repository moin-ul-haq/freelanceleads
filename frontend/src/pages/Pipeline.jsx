import { useEffect, useRef, useState } from 'react'
import { api, errorMessage, getTokens } from '../api/client'
import { PageHeader, Card, Spinner, Alert, Button, Modal, Input } from '../components/ui'

export default function Pipeline() {
  const [board, setBoard] = useState(null)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(null) // pipeline lead id (styling only)
  const draggingRef = useRef(null) // authoritative — avoids stale state inside moveTo
  const [dragOverStage, setDragOverStage] = useState(null)
  const [editing, setEditing] = useState(null) // pipeline lead being edited

  function load() {
    Promise.allSettled([api.get('/pipeline/board/'), api.get('/pipeline/stats/')])
      .then(([b, s]) => {
        if (b.status === 'fulfilled') setBoard(b.value)
        else setError(errorMessage(b.reason))
        if (s.status === 'fulfilled') setStats(s.value)
      })
  }

  useEffect(load, [])

  async function moveTo(stageId) {
    const leadId = draggingRef.current
    draggingRef.current = null
    setDragging(null)
    setDragOverStage(null)
    if (!leadId) return

    const fromStage = board.find((s) => s.leads.some((l) => l.id === leadId))
    if (!fromStage || fromStage.id === stageId) return

    // optimistic update
    const lead = fromStage.leads.find((l) => l.id === leadId)
    setBoard((b) => b.map((s) => {
      if (s.id === fromStage.id) return { ...s, leads: s.leads.filter((l) => l.id !== leadId) }
      if (s.id === stageId) return { ...s, leads: [...s.leads, { ...lead, stage: stageId }] }
      return s
    }))

    try {
      await api.patch(`/pipeline/leads/${leadId}/stage/`, { stage_id: stageId })
      api.get('/pipeline/stats/').then(setStats).catch(() => {})
    } catch (err) {
      setError(errorMessage(err, 'Move failed'))
      load() // revert to server state
    }
  }

  async function removeLead(leadId) {
    try {
      await api.del(`/pipeline/leads/${leadId}/`)
      setEditing(null)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function exportCsv() {
    // fetch with auth header, then download
    const tokens = getTokens()
    const res = await fetch('/api/pipeline/export/csv/', {
      headers: { Authorization: `Bearer ${tokens?.access}` },
    })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'pipeline.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!board && !error) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  return (
    <div>
      <PageHeader title="Pipeline" subtitle="Drag deals between stages. Click a card to edit.">
        <Button variant="secondary" onClick={exportCsv}>⬇ Export CSV</Button>
      </PageHeader>

      <Alert>{error}</Alert>

      {stats && (
        <div className="mb-4 flex flex-wrap gap-4 text-sm text-slate-600">
          <span><strong className="text-slate-900">{stats.total_leads}</strong> deals</span>
          <span>value <strong className="text-slate-900">${Number(stats.total_deal_value ?? 0).toLocaleString()}</strong></span>
          <span>won <strong className="text-emerald-600">${Number(stats.won_value ?? 0).toLocaleString()}</strong></span>
          <span>conversion <strong className="text-slate-900">{stats.conversion_rate}%</strong></span>
        </div>
      )}

      <div className="flex gap-3 overflow-x-auto pb-4">
        {board?.map((stage) => (
          <div
            key={stage.id}
            onDragOver={(e) => { e.preventDefault(); setDragOverStage(stage.id) }}
            onDragLeave={() => setDragOverStage((s) => (s === stage.id ? null : s))}
            onDrop={() => moveTo(stage.id)}
            className={`flex w-64 shrink-0 flex-col rounded-xl border bg-slate-100/70 transition-colors ${
              dragOverStage === stage.id ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200'
            }`}
          >
            <div className="flex items-center justify-between px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: stage.color || '#94a3b8' }} />
                <span className="text-sm font-semibold text-slate-800">{stage.name}</span>
              </div>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">{stage.leads.length}</span>
            </div>

            <div className="lane flex-1 space-y-2 overflow-y-auto px-2 pb-2" style={{ maxHeight: '60vh', minHeight: 90 }}>
              {stage.leads.map((pl) => (
                <div
                  key={pl.id}
                  draggable
                  onDragStart={() => { draggingRef.current = pl.id; setDragging(pl.id) }}
                  onDragEnd={() => { draggingRef.current = null; setDragging(null); setDragOverStage(null) }}
                  onClick={() => setEditing(pl)}
                  className={`cursor-grab rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition hover:border-indigo-300 ${
                    dragging === pl.id ? 'opacity-50' : ''
                  }`}
                >
                  <p className="text-sm font-medium text-slate-900">{pl.lead_details?.name}</p>
                  <p className="text-xs text-slate-400">{pl.lead_details?.niche} · {pl.lead_details?.city}</p>
                  <div className="mt-1.5 flex items-center justify-between text-xs">
                    <span className="font-semibold text-emerald-600">
                      {pl.deal_value ? `$${Number(pl.deal_value).toLocaleString()}` : ''}
                    </span>
                    {pl.follow_up_date && <span className="text-amber-600">📅 {pl.follow_up_date}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <EditDealModal
        deal={editing}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load() }}
        onRemove={removeLead}
      />
    </div>
  )
}

function EditDealModal({ deal, onClose, onSaved, onRemove }) {
  const [dealValue, setDealValue] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (deal) {
      setDealValue(deal.deal_value ?? '')
      setFollowUp(deal.follow_up_date ?? '')
      setNotes(deal.notes ?? '')
      setError('')
    }
  }, [deal])

  if (!deal) return null

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    try {
      await api.patch(`/pipeline/leads/${deal.id}/`, {
        deal_value: dealValue === '' ? null : dealValue,
        follow_up_date: followUp || null,
        notes,
      })
      onSaved()
    } catch (err) {
      setError(errorMessage(err, 'Save failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} title={deal.lead_details?.name}>
      <form onSubmit={save} className="space-y-4">
        <Alert>{error}</Alert>
        <Input label="Deal value (USD)" type="number" min="0" step="0.01" value={dealValue} onChange={(e) => setDealValue(e.target.value)} />
        <Input label="Follow-up date" type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Notes</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
        </label>

        {deal.logs?.length > 0 && (
          <div className="max-h-28 overflow-y-auto rounded-lg bg-slate-50 p-2 text-xs text-slate-500">
            {deal.logs.slice(0, 8).map((log) => (
              <div key={log.id} className="py-0.5">· {log.action}</div>
            ))}
          </div>
        )}

        <div className="flex justify-between">
          <Button type="button" variant="danger" onClick={() => onRemove(deal.id)}>Remove</Button>
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</Button>
        </div>
      </form>
    </Modal>
  )
}
