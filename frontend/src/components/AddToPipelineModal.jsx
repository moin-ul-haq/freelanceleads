import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { Modal, Button, Select, Input, Alert } from './ui'

export default function AddToPipelineModal({ lead, open, onClose, onAdded }) {
  const [stages, setStages] = useState([])
  const [stageId, setStageId] = useState('')
  const [dealValue, setDealValue] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
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
    try {
      const body = { lead: lead.id, stage: Number(stageId) }
      if (dealValue) body.deal_value = dealValue
      if (notes) body.notes = notes
      await api.post('/pipeline/leads/', body)
      onAdded?.()
      onClose()
    } catch (err) {
      setError(errorMessage(err, 'Could not add to pipeline'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Add to pipeline — ${lead?.name}`}>
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <Select label="Stage" value={stageId} onChange={(e) => setStageId(e.target.value)} required>
          {stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <Input label="Deal value (USD, optional)" type="number" min="0" step="0.01" value={dealValue} onChange={(e) => setDealValue(e.target.value)} />
        <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <Button type="submit" disabled={busy || !stageId} className="w-full">{busy ? 'Adding…' : 'Add to pipeline'}</Button>
      </form>
    </Modal>
  )
}
