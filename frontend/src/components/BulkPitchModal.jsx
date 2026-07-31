import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Modal, Button, Select, Input, Alert, Spinner } from './ui'
import { splitPitch } from './PitchModal'

const TONES = ['professional', 'friendly', 'direct', 'urgent']

export default function BulkPitchModal({ leads, open, onClose }) {
  const { user } = useAuth()
  const [tone, setTone] = useState('professional')
  const [senderName, setSenderName] = useState('')
  const [results, setResults] = useState(null) // [{lead_id, pitch, error}]
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sentIds, setSentIds] = useState(new Set())
  const [sendingId, setSendingId] = useState(null)
  const [copiedId, setCopiedId] = useState(null)

  const leadById = new Map((leads || []).map((l) => [l.id, l]))

  useEffect(() => {
    if (open) {
      setResults(null); setError(''); setSentIds(new Set())
      setSenderName(user?.first_name || '')
    }
  }, [open, user])

  async function generate() {
    setBusy(true)
    setError('')
    try {
      const body = { lead_ids: leads.map((l) => l.id), tone }
      if (senderName.trim()) body.sender_name = senderName.trim()
      const data = await api.post('/ai/bulk-pitch/', body)
      setResults(data.results)
    } catch (err) {
      setError(errorMessage(err, 'Bulk pitch failed'))
    } finally {
      setBusy(false)
    }
  }

  async function copy(id, pitch) {
    await navigator.clipboard.writeText(pitch)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  async function send(leadId, pitch) {
    const { subject, body } = splitPitch(pitch)
    setSendingId(leadId)
    setError('')
    try {
      await api.post('/outreach/send-email/', {
        lead_id: leadId,
        subject: subject || 'Quick note',
        body,
      })
      setSentIds((s) => new Set([...s, leadId]))
    } catch (err) {
      setError(errorMessage(err, 'Send failed'))
    } finally {
      setSendingId(null)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Bulk pitches — ${leads?.length || 0} leads`} wide>
      <div className="space-y-4">
        <Alert>{error}</Alert>

        {!results && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Select label="Tone" value={tone} onChange={(e) => setTone(e.target.value)}>
                {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
              </Select>
              <Input
                label="Your name (signature)"
                placeholder={user?.first_name || 'Your first name'}
                value={senderName}
                onChange={(e) => setSenderName(e.target.value)}
              />
            </div>
            <Button onClick={generate} disabled={busy}>
              {busy ? <><Spinner className="h-4 w-4 text-white" /> Generating {leads?.length} pitches…</> : `Generate ${leads?.length} pitches`}
            </Button>
          </>
        )}

        {results && (
          <div className="max-h-[60vh] space-y-3 overflow-y-auto">
            {results.map((r) => {
              const l = leadById.get(r.lead_id)
              return (
                <div key={r.lead_id} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-900">{l?.name || `Lead #${r.lead_id}`}</span>
                    {r.pitch && (
                      <div className="flex gap-1.5">
                        <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={() => copy(r.lead_id, r.pitch)}>
                          {copiedId === r.lead_id ? '✓' : 'Copy'}
                        </Button>
                        <Button
                          className="!px-2 !py-1 text-xs"
                          disabled={!l?.email || sendingId === r.lead_id || sentIds.has(r.lead_id)}
                          onClick={() => send(r.lead_id, r.pitch)}
                          title={l?.email ? `Send to ${l.email}` : 'No email for this lead'}
                        >
                          {sentIds.has(r.lead_id) ? 'Sent ✓' : sendingId === r.lead_id ? '…' : 'Send'}
                        </Button>
                      </div>
                    )}
                  </div>
                  {r.pitch
                    ? <pre className="whitespace-pre-wrap font-mono text-xs text-slate-600">{r.pitch}</pre>
                    : <p className="text-xs text-red-600">{r.error}</p>}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Modal>
  )
}
