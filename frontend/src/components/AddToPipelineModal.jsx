import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { Modal, Button, Select, Input, Alert } from './ui'

// Works for a single lead (`lead`) or a bulk selection (`leads` array).
export default function AddToPipelineModal({ lead, leads, open, onClose, onAdded }) {
  const targets = leads?.length ? leads : lead ? [lead] : []
  const [stages, setStages] = useState([])
  const [stageId, setStageId] = useState('')
  const [dealValue, setDealValue] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    api.get('/pipeline/stages/')
      .then((data) => {
        const list = Array.isArray(data) ? data : data.results || []
        setStages(list)
        if (list.length) setStageId(String(list[0].id))
      })
      .catch(() => {})
  }, [open])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    let added = 0
    let firstError = ''
    for (const t of targets) {
      try {
        const body = { lead: t.id, stage: Number(stageId) }
        if (dealValue) body.deal_value = dealValue
        if (notes) body.notes = notes
        await api.post('/pipeline/leads/', body)
        added += 1
      } catch (err) {
        if (!firstError) firstError = errorMessage(err)
      }
    }
    setBusy(false)
    if (added === targets.length) {
      onAdded?.(added)
      onClose()
    } else {
      setError(`Added ${added}/${targets.length}. ${firstError}`)
      if (added > 0) onAdded?.(added)
    }
  }

  const title = targets.length > 1
    ? `Add ${targets.length} leads to pipeline`
    : `Add to pipeline — ${targets[0]?.name || ''}`

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <Select label="Stage" value={stageId} onChange={(e) => setStageId(e.target.value)} required>
          {stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <Input label={`Deal value ${targets.length > 1 ? 'per lead ' : ''}(USD, optional)`} type="number" min="0" step="0.01" value={dealValue} onChange={(e) => setDealValue(e.target.value)} />
        <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <Button type="submit" disabled={busy || !stageId} className="w-full">
          {busy ? 'Adding…' : targets.length > 1 ? `Add ${targets.length} leads` : 'Add to pipeline'}
        </Button>
      </form>
    </Modal>
  )
}
