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
  const [managingStages, setManagingStages] = useState(false)

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
        <Button variant="secondary" onClick={() => setManagingStages(true)}>⚙ Manage stages</Button>
        <Button variant="secondary" onClick={exportCsv}>⬇ Export CSV</Button>
      </PageHeader>

      <Alert>{error}</Alert>

      <FollowUpsDue board={board} onOpen={setEditing} />

      {stats && (
        <div className="mb-4 flex flex-wrap gap-4 text-sm text-slate-600">
          <span><strong className="text-slate-900">{stats.total_leads}</strong> deals</span>
          <span>value <strong className="text-slate-900">${Number(stats.total_deal_value ?? 0).toLocaleString()}</strong></span>
          <span>won <strong className="text-emerald-600">${Number(stats.won_deal_value ?? 0).toLocaleString()}</strong></span>
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
                    {pl.follow_up_date && (
                      <span className={pl.follow_up_date <= todayStr() ? 'font-bold text-red-600' : 'text-amber-600'}>
                        📅 {pl.follow_up_date}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <EditDealModal
        deal={editing}
        stages={board || []}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load() }}
        onRemove={removeLead}
      />
      <ManageStagesModal open={managingStages} onClose={() => { setManagingStages(false); load() }} />
    </div>
  )
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function FollowUpsDue({ board, onOpen }) {
  if (!board) return null
  const due = board.flatMap((s) =>
    (s.system_key === 'closed_won' || s.system_key === 'closed_lost') ? [] :
    s.leads.filter((l) => l.follow_up_date && l.follow_up_date <= todayStr())
      .map((l) => ({ ...l, stageName: s.name }))
  )
  if (!due.length) return null
  return (
    <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
      <p className="mb-2 text-sm font-bold text-amber-800">
        ⏰ {due.length} follow-up{due.length > 1 ? "s" : ""} due today:
      </p>
      <div className="flex flex-wrap gap-2">
        {due.map((l) => (
          <button
            key={l.id}
            onClick={() => onOpen(l)}
            className="flex items-center gap-2 rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-sm hover:border-amber-400"
          >
            <span className="font-medium text-slate-900">{l.lead_details?.name}</span>
            <span className="text-xs text-slate-400">{l.stageName}</span>
            {l.deal_value > 0 && <span className="text-xs font-semibold text-emerald-600">${Number(l.deal_value).toLocaleString()}</span>}
            <span className={`text-xs ${l.follow_up_date < todayStr() ? 'font-bold text-red-600' : 'text-amber-600'}`}>
              {l.follow_up_date < todayStr() ? 'overdue' : 'today'}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

const STAGE_COLORS = ['#E2E8F0', '#FEF08A', '#93C5FD', '#C4B5FD', '#86EFAC', '#FCA5A5', '#FDBA74', '#F9A8D4']

function ManageStagesModal({ open, onClose }) {
  const [stages, setStages] = useState([])
  const [error, setError] = useState('')
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(STAGE_COLORS[0])

  function loadStages() {
    api.get('/pipeline/stages/')
      .then((d) => setStages(Array.isArray(d) ? d : d.results || []))
      .catch((err) => setError(errorMessage(err)))
  }
  useEffect(() => { if (open) { setError(''); loadStages() } }, [open])

  async function addStage(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/pipeline/stages/', { name: newName, color: newColor, order: stages.length + 1 })
      setNewName('')
      loadStages()
    } catch (err) { setError(errorMessage(err)) }
  }

  async function rename(stage) {
    const name = window.prompt('New stage name:', stage.name)
    if (!name || name === stage.name) return
    try { await api.patch(`/pipeline/stages/${stage.id}/`, { name }); loadStages() } catch (err) { setError(errorMessage(err)) }
  }

  async function remove(stage) {
    if (!window.confirm(`Delete stage "${stage.name}"? It must be empty.`)) return
    try { await api.del(`/pipeline/stages/${stage.id}/`); loadStages() } catch (err) { setError(errorMessage(err)) }
  }

  async function move(idx, dir) {
    const next = [...stages]
    const [item] = next.splice(idx, 1)
    next.splice(idx + dir, 0, item)
    setStages(next)
    try {
      await api.patch('/pipeline/stages/reorder/', { stages: next.map((s, i) => ({ id: s.id, order: i + 1 })) })
    } catch (err) { setError(errorMessage(err)); loadStages() }
  }

  return (
    <Modal open={open} onClose={onClose} title="Manage pipeline stages">
      <div className="space-y-4">
        <Alert>{error}</Alert>
        <div className="space-y-1.5">
          {stages.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <span className="h-3 w-3 rounded-full" style={{ background: s.color || '#94a3b8' }} />
              <span className="flex-1 font-medium text-slate-800">{s.name}</span>
              {s.system_key && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-400">system</span>}
              <button onClick={() => move(i, -1)} disabled={i === 0} className="px-1 text-slate-400 hover:text-slate-700 disabled:opacity-30">↑</button>
              <button onClick={() => move(i, 1)} disabled={i === stages.length - 1} className="px-1 text-slate-400 hover:text-slate-700 disabled:opacity-30">↓</button>
              <button onClick={() => rename(s)} className="text-xs text-slate-400 hover:text-indigo-600">rename</button>
              {!s.system_key && <button onClick={() => remove(s)} className="text-xs text-slate-400 hover:text-red-600">delete</button>}
            </div>
          ))}
        </div>

        <form onSubmit={addStage} className="space-y-2 rounded-lg bg-slate-50 p-3">
          <Input label="New stage name" value={newName} onChange={(e) => setNewName(e.target.value)} required placeholder="Negotiating" />
          <div className="flex items-center gap-1.5">
            {STAGE_COLORS.map((c) => (
              <button
                key={c} type="button" onClick={() => setNewColor(c)}
                className={`h-6 w-6 rounded-full border-2 ${newColor === c ? 'border-indigo-500' : 'border-transparent'}`}
                style={{ background: c }}
              />
            ))}
            <Button type="submit" className="ml-auto !py-1.5">+ Add stage</Button>
          </div>
        </form>
      </div>
    </Modal>
  )
}

function EditDealModal({ deal, stages, onClose, onSaved, onRemove }) {
  const [dealValue, setDealValue] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [notes, setNotes] = useState('')
  const [stageId, setStageId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (deal) {
      setDealValue(deal.deal_value ?? '')
      setFollowUp(deal.follow_up_date ?? '')
      setNotes(deal.notes ?? '')
      setStageId(String(deal.stage))
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
      if (stageId && String(deal.stage) !== stageId) {
        await api.patch(`/pipeline/leads/${deal.id}/stage/`, { stage_id: Number(stageId) })
      }
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
        {stages?.length > 0 && (
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Stage / status</span>
            <select
              value={stageId}
              onChange={(e) => setStageId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            >
              {stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        )}
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
