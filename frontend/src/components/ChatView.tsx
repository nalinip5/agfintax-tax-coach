import { useState, useRef, useEffect } from 'react'
import { api, Citation } from '../lib/api'

type Message = {
  role: 'user' | 'assistant'
  content: string
  intent?: string
  citations?: Citation[]
  blocked?: boolean
}

const USER_ID = 'demo-user'

const INTENT_LABEL: Record<string, string> = {
  TAX_RULE: 'Tax rule',
  PLAN_QUESTION: 'Your plan',
  STRATEGY_EXPLANATION: 'Strategy',
  WHAT_IF: 'Scenario',
  LIFE_EVENT: 'Life event',
  PROFESSIONAL_JUDGMENT: 'Professional judgment',
  DOCUMENTATION: 'Documentation',
  OUT_OF_SCOPE: 'Out of scope',
  PII_VIOLATION: 'Blocked',
}

function SourceCard({ citation }: { citation: Citation }) {
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 rounded-full border border-ledger-200 bg-white px-3 py-1 text-xs text-ledger-700 hover:border-clay-500 hover:text-clay-600 transition-colors"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-clay-500" />
      {citation.label}
    </a>
  )
}

function LifeEventCard() {
  return (
    <div className="rounded-lg border border-clay-500/40 bg-clay-500/5 px-4 py-3 text-sm text-ledger-900">
      <p className="font-medium text-clay-600">Worth a second look</p>
      <p className="mt-0.5 text-ledger-700">
        This touches a life event that can shift your filing situation. We've flagged it for a
        professional referral so nothing gets missed.
      </p>
    </div>
  )
}

export default function ChatView() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "I'm your tax coach. Ask about your plan, a tax rule, or try a what-if scenario.",
    },
  ])
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState<string>()
  const [usage, setUsage] = useState<{ used_today: number; limit: number; tier: string }>()
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.usage(USER_ID).then(setUsage).catch(() => {})
  }, [messages.length])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setSending(true)
    try {
      const res = await api.chat(USER_ID, text, conversationId)
      setConversationId(res.conversation_id)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: res.reply,
          intent: res.intent,
          citations: res.citations,
          blocked: res.blocked,
        },
      ])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: 'Something went wrong reaching the coach. Try again.' }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="mx-auto flex h-screen max-w-6xl gap-6 px-6 py-6">
      {/* Plan rail */}
      <aside className="hidden w-64 shrink-0 flex-col gap-4 lg:flex">
        <div className="rounded-xl border border-ledger-200 bg-white p-4">
          <h2 className="font-serif text-lg text-ledger-900">This year</h2>
          <p className="mt-1 text-sm text-ledger-700">Tax year 2025 · Single filer</p>
          <div className="mt-3 h-px bg-ledger-100" />
          <p className="mt-3 text-xs uppercase tracking-wide text-ledger-600">Usage today</p>
          {usage ? (
            <div className="mt-1">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-ledger-100">
                <div
                  className="h-full rounded-full bg-ledger-600"
                  style={{ width: `${Math.min(100, (usage.used_today / usage.limit) * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-ledger-600">
                {usage.used_today} / {usage.limit} messages · {usage.tier} plan
              </p>
            </div>
          ) : (
            <p className="mt-1 text-xs text-ledger-500">—</p>
          )}
        </div>
        <div className="rounded-xl border border-ledger-200 bg-white p-4">
          <h2 className="font-serif text-lg text-ledger-900">Try asking</h2>
          <ul className="mt-2 space-y-2 text-sm text-ledger-700">
            {[
              'What is the 401k contribution limit?',
              'What if I earn $90,000 next year?',
              "I'm getting married next month",
            ].map((s) => (
              <li key={s}>
                <button
                  onClick={() => setInput(s)}
                  className="text-left underline decoration-ledger-200 underline-offset-2 hover:decoration-clay-500"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Chat column */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="mb-4">
          <h1 className="font-serif text-2xl text-ledger-900">AGFinTax Coach</h1>
          <p className="text-sm text-ledger-600">Answers are grounded in your plan and cited government sources.</p>
        </header>

        <div className="flex-1 overflow-y-auto rounded-xl border border-ledger-200 bg-white p-5">
          <div className="space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex flex-col gap-2'}>
                <div
                  className={
                    m.role === 'user'
                      ? 'max-w-[75%] rounded-2xl rounded-tr-sm bg-ledger-700 px-4 py-2.5 text-sm text-white'
                      : `max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm ${
                          m.blocked ? 'bg-clay-500/10 text-clay-600 border border-clay-500/30' : 'bg-ledger-50 text-ledger-900'
                        }`
                  }
                >
                  {m.intent && m.role === 'assistant' && (
                    <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-ledger-500">
                      {INTENT_LABEL[m.intent] ?? m.intent}
                    </span>
                  )}
                  {m.content}
                </div>
                {m.intent === 'LIFE_EVENT' && <LifeEventCard />}
                {m.citations && m.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {m.citations.map((c, j) => (
                      <SourceCard key={j} citation={c} />
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="mt-3 flex items-end gap-2 rounded-xl border border-ledger-200 bg-white p-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            rows={1}
            placeholder="Ask about your taxes…"
            className="max-h-32 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-ledger-900 outline-none placeholder:text-ledger-400"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim()}
            className="shrink-0 rounded-lg bg-ledger-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ledger-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}
