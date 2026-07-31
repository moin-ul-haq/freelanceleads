import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../api/client'
import { PageHeader, Card, Button, Alert, Spinner } from '../components/ui'

const SUGGESTIONS = [
  'How should I price a 5-page website for a local plumber?',
  'Write a follow-up for a lead who ghosted after my first email.',
  'What objections do local businesses have about SEO retainers?',
]

export default function Assistant() {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, busy])

  async function send(text) {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    setError('')
    setBusy(true)
    setHistory((h) => [...h, { role: 'user', content: message }])
    try {
      const data = await api.post('/ai/chat/', { message, history })
      setHistory(data.history)
    } catch (err) {
      setError(errorMessage(err, 'Chat failed'))
      setHistory((h) => h.slice(0, -1)) // roll back optimistic user message
      setInput(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="AI Assistant"
        subtitle="Your freelance sales coach — pitches, pricing, objection handling."
      >
        {history.length > 0 && (
          <Button variant="secondary" onClick={() => setHistory([])}>New conversation</Button>
        )}
      </PageHeader>

      <Card className="flex min-h-[60vh] flex-col p-4">
        <div className="flex-1 space-y-3 overflow-y-auto pb-3">
          {history.length === 0 && (
            <div className="py-10 text-center">
              <p className="text-3xl">🤖</p>
              <p className="mt-2 text-sm text-slate-500">Ask anything about landing local business clients.</p>
              <div className="mx-auto mt-4 flex max-w-md flex-col gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-600 hover:border-indigo-300 hover:bg-indigo-50"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {history.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-800'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-slate-100 px-4 py-3"><Spinner className="h-4 w-4" /></div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <Alert>{error}</Alert>

        <form
          onSubmit={(e) => { e.preventDefault(); send() }}
          className="mt-3 flex gap-2 border-t border-slate-100 pt-3"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the assistant…"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
          <Button type="submit" disabled={busy || !input.trim()}>Send</Button>
        </form>
      </Card>
    </div>
  )
}
