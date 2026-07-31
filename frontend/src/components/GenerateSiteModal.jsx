import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { Modal, Button, Select, Input, Alert, Spinner } from './ui'

const PALETTES = [
  ['ocean_blue', 'Ocean Blue', '#2563eb', '#1e40af'],
  ['emerald', 'Emerald', '#059669', '#065f46'],
  ['royal_purple', 'Royal Purple', '#7c3aed', '#5b21b6'],
  ['sunset_orange', 'Sunset Orange', '#ea580c', '#9a3412'],
  ['rose_red', 'Rose Red', '#dc2626', '#991b1b'],
  ['slate', 'Slate', '#475569', '#1e293b'],
  ['teal', 'Teal', '#0d9488', '#115e59'],
  ['amber_gold', 'Amber Gold', '#d97706', '#92400e'],
  ['indigo', 'Indigo', '#4f46e5', '#3730a3'],
  ['forest_green', 'Forest Green', '#16a34a', '#14532d'],
  ['hot_pink', 'Hot Pink', '#db2777', '#9d174d'],
  ['midnight', 'Midnight', '#334155', '#0f172a'],
]

const TONES = [
  ['auto', 'Auto — let AI choose for the niche'],
  ['friendly', 'Friendly & warm'],
  ['professional', 'Professional & polished'],
  ['bold', 'Bold & energetic'],
  ['luxury', 'Premium & upscale'],
  ['playful', 'Playful & casual'],
]

export default function GenerateSiteModal({ lead, open, onClose, onGenerated }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({})
  const [scheme, setScheme] = useState('ai')
  const [customPrimary, setCustomPrimary] = useState('#2563eb')
  const [customSecondary, setCustomSecondary] = useState('#1e40af')
  const [tone, setTone] = useState('auto')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open && lead) {
      setStep(1)
      setError('')
      setForm({
        business_name: lead.name || '',
        phone: lead.phone || '',
        email: lead.email || '',
        address: lead.address || '',
        services: '',
        extra_info: '',
      })
      setScheme('ai')
      setTone('auto')
    }
  }, [open, lead])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function generate() {
    setBusy(true)
    setError('')
    try {
      const body = {
        lead_id: lead.id,
        regenerate: true,
        color_scheme: scheme,
        tone,
        ...form,
      }
      if (scheme === 'custom') {
        body.custom_primary = customPrimary
        body.custom_secondary = customSecondary
      }
      const res = await api.post('/sites/generate/', body)
      onGenerated?.(res)
      onClose()
    } catch (err) {
      setError(errorMessage(err, 'Site generation failed'))
    } finally {
      setBusy(false)
    }
  }

  if (!lead) return null

  return (
    <Modal open={open} onClose={onClose} title={`Generate website — ${lead.name}`} wide>
      <div className="space-y-4">
        <Alert>{error}</Alert>

        {/* progress */}
        <div className="flex items-center gap-2">
          {[1, 2].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full ${step >= s ? 'bg-indigo-500' : 'bg-slate-200'}`} />
          ))}
          <span className="text-xs text-slate-400">{step}/2</span>
        </div>

        {step === 1 && (
          <>
            <p className="text-sm text-slate-500">
              Business details are pre-filled from the lead — adjust anything, or leave the optional
              fields empty and the AI will decide from the niche.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Business name" value={form.business_name} onChange={set('business_name')} />
              <Input label="Phone" value={form.phone} onChange={set('phone')} />
              <Input label="Email" value={form.email} onChange={set('email')} />
              <Input label="Address" value={form.address} onChange={set('address')} />
            </div>
            <Input
              label="Services (optional, comma-separated — else AI picks 6 for the niche)"
              placeholder="Drain cleaning, Leak repair, Water heaters"
              value={form.services}
              onChange={set('services')}
            />
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">
                Anything else about this business? (optional — real facts only, they'll be woven into the copy)
              </span>
              <textarea
                rows={3}
                value={form.extra_info}
                onChange={set('extra_info')}
                placeholder="Family-run shop, open 7 days, serves the whole metro area…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </label>
            <div className="flex justify-end">
              <Button onClick={() => setStep(2)}>Next: design →</Button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <p className="text-sm text-slate-500">Choose a color scheme, or let AI pick one for the business.</p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {PALETTES.map(([key, label, c1, c2]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setScheme(key)}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 text-xs font-medium transition ${
                    scheme === key ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <span className="flex gap-1">
                    <span className="h-6 w-6 rounded-full" style={{ background: c1 }} />
                    <span className="h-6 w-6 rounded-full" style={{ background: c2 }} />
                  </span>
                  {label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setScheme('custom')}
                className={`rounded-lg border px-3 py-2 text-sm font-medium ${scheme === 'custom' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600'}`}
              >
                🎨 Custom colors
              </button>
              <button
                type="button"
                onClick={() => setScheme('ai')}
                className={`rounded-lg border px-3 py-2 text-sm font-medium ${scheme === 'ai' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600'}`}
              >
                ✨ Let AI decide
              </button>
              {scheme === 'custom' && (
                <span className="flex items-center gap-2">
                  <input type="color" value={customPrimary} onChange={(e) => setCustomPrimary(e.target.value)} className="h-9 w-12 cursor-pointer rounded border border-slate-200" title="Primary" />
                  <input type="color" value={customSecondary} onChange={(e) => setCustomSecondary(e.target.value)} className="h-9 w-12 cursor-pointer rounded border border-slate-200" title="Secondary (dark)" />
                </span>
              )}
            </div>

            <Select label="Copy tone (optional)" value={tone} onChange={(e) => setTone(e.target.value)}>
              {TONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
            <p className="-mt-2 text-xs text-slate-400">Same niche, different tones → totally different copy.</p>

            <div className="flex justify-between">
              <Button variant="secondary" onClick={() => setStep(1)}>← Back</Button>
              <Button onClick={generate} disabled={busy}>
                {busy ? <><Spinner className="h-4 w-4 text-white" /> Generating website…</> : '✨ Generate website'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
