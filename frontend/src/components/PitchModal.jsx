import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Modal, Button, Select, Input, Alert, Spinner } from './ui'

const TONES = ['professional', 'friendly', 'direct', 'urgent']

// "Subject: xyz\n\nbody..." → { subject, body }
export function splitPitch(pitch) {
  const match = pitch.match(/^Subject:\s*(.+?)\s*\n+([\s\S]*)$/i)
  if (match) return { subject: match[1].trim(), body: match[2].trim() }
  return { subject: '', body: pitch.trim() }
}

export default function PitchModal({ lead, open, onClose }) {
  const { user } = useAuth()
  const [tone, setTone] = useState('professional')
  const [senderName, setSenderName] = useState('')
  const [pitch, setPitch] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sending, setSending] = useState(false)
  const [sentTo, setSentTo] = useState('')

  useEffect(() => {
    if (open) {
      setPitch(''); setError(''); setSentTo('')
      setSenderName(user?.first_name || '')
    }
  }, [open, user])

  async function generate() {
    setBusy(true)
    setError('')
    setPitch('')
    setSentTo('')
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

  async function sendEmail() {
    const { subject, body } = splitPitch(pitch)
    setSending(true)
    setError('')
    try {
      const res = await api.post('/outreach/send-email/', {
        lead_id: lead.id,
        subject: subject || `Quick note for ${lead.name}`,
        body,
      })
      setSentTo(res.to)
    } catch (err) {
      setError(errorMessage(err, 'Send failed'))
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`AI pitch — ${lead?.name}`} wide>
      <div className="space-y-4">
        <Alert>{error}</Alert>
        {sentTo && <Alert kind="success">Email sent to {sentTo} ✓</Alert>}

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
          {busy ? <><Spinner className="h-4 w-4 text-white" /> Generating…</> : pitch ? 'Regenerate' : 'Generate pitch'}
        </Button>

        {pitch && (
          <div>
            <textarea
              value={pitch}
              onChange={(e) => { setPitch(e.target.value); setSentTo('') }}
              rows={12}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-800"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-xs text-slate-400">
                {lead?.email ? `Recipient: ${lead.email}` : 'No email found for this lead — copy the pitch instead.'}
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={copy}>{copied ? '✓ Copied' : 'Copy'}</Button>
                <Button onClick={sendEmail} disabled={sending || !lead?.email || !!sentTo}>
                  {sending ? <><Spinner className="h-4 w-4 text-white" /> Sending…</> : sentTo ? 'Sent ✓' : '✉️ Send email'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
