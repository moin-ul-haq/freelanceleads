import { useState } from 'react'
import { api, errorMessage } from '../api/client'
import { Modal, Button, Select, Input, Alert, Spinner } from './ui'

const TONES = ['professional', 'friendly', 'direct', 'urgent']

export default function PitchModal({ lead, open, onClose }) {
  const [tone, setTone] = useState('professional')
  const [senderName, setSenderName] = useState('')
  const [pitch, setPitch] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  async function generate() {
    setBusy(true)
    setError('')
    setPitch('')
    try {
      const body = { lead_id: lead.id, tone }
      if (senderName.trim()) body.sender_name = senderName.trim()
      const data = await api.post('/ai/generate-pitch/', body)
      setPitch(data.pitch)
    } catch (err) {
      setError(errorMessage(err, 'Pitch generation failed'))
    } finally {
      setBusy(false)
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(pitch)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Modal open={open} onClose={onClose} title={`AI pitch — ${lead?.name}`} wide>
      <div className="space-y-4">
        <Alert>{error}</Alert>
        <div className="grid grid-cols-2 gap-3">
          <Select label="Tone" value={tone} onChange={(e) => setTone(e.target.value)}>
            {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Input label="Your name (signature)" placeholder="Alex" value={senderName} onChange={(e) => setSenderName(e.target.value)} />
        </div>

        <Button onClick={generate} disabled={busy}>
          {busy ? <><Spinner className="h-4 w-4 text-white" /> Generating…</> : pitch ? 'Regenerate' : 'Generate pitch'}
        </Button>

        {pitch && (
          <div>
            <textarea
              readOnly
              value={pitch}
              rows={12}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-800"
            />
            <div className="mt-2 flex justify-end">
              <Button variant="secondary" onClick={copy}>{copied ? '✓ Copied' : 'Copy to clipboard'}</Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
