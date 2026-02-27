import { useState, useEffect, useRef } from 'react'
import {
  fetchSuggestions, sendQueryStream,
  fetchSessionMessages, saveMessage, createSession,
} from '../api/client'
import MessageBubble from './MessageBubble'

export default function ChatTab({ user, sessionId, onSessionCreated, prefillQuery, onPrefillConsumed }) {
  const clientLabel = (user?.client_id || '').charAt(0).toUpperCase() + (user?.client_id || '').slice(1)

  const [messages, setMessages]       = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [input, setInput]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [histLoading, setHistLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(null)  // live streaming step

  const activeSessionRef = useRef(sessionId)
  const bottomRef        = useRef(null)
  const inputRef         = useRef(null)

  useEffect(() => {
    fetchSuggestions().then(setSuggestions).catch(() => {})
  }, [])

  useEffect(() => {
    activeSessionRef.current = sessionId
    if (!sessionId) {
      setMessages([welcomeMsg(user?.full_name, clientLabel)])
      return
    }
    setHistLoading(true)
    fetchSessionMessages(sessionId)
      .then(rows => {
        setMessages(rows.length === 0
          ? [welcomeMsg(user?.full_name, clientLabel)]
          : rows.map(hydrateRow))
      })
      .catch(() => setMessages([welcomeMsg(user?.full_name, clientLabel)]))
      .finally(() => setHistLoading(false))
  }, [sessionId])

  useEffect(() => {
    if (prefillQuery) {
      setInput(prefillQuery)
      onPrefillConsumed?.()
      inputRef.current?.focus()
    }
  }, [prefillQuery])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea whenever input changes
  useEffect(() => {
    const ta = inputRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }, [input])

  const ensureSession = async (firstUserMessage) => {
    if (activeSessionRef.current) return activeSessionRef.current
    const s = await createSession(firstUserMessage.slice(0, 80))
    activeSessionRef.current = s.session_id
    onSessionCreated?.(s.session_id)
    return s.session_id
  }

  const handleSend = async (directQuery = null) => {
    const q = directQuery ? directQuery.trim() : input.trim()
    if (!q || loading) return

    setMessages(prev => [...prev.filter(m => !m.isWelcome), { id: `u-${Date.now()}`, role: 'user', text: q }])
    setInput('')
    setLoading(true)
    setProgressStep({ step: 'intent', msg: '🧠 Understanding your question…' })

    try {
      const sid = await ensureSession(q)
      await saveMessage(sid, { role: 'user', content: q, title_hint: q }).catch(() => {})

      const data = await sendQueryStream(q, (evt) => setProgressStep(evt))

      setProgressStep(null)
      const assistantMsg = { id: `a-${Date.now()}`, role: 'assistant', data }
      setMessages(prev => [...prev, assistantMsg])

      await saveMessage(sid, {
        role:       'assistant',
        content:    data.response || '',
        raw_data:   data.raw_data   ? JSON.stringify(data.raw_data)   : null,
        query_type: data.query_type || null,
        metadata:   data.metadata   ? JSON.stringify(data.metadata)   : null,
      }).catch(() => {})
    } catch {
      setProgressStep(null)
      setMessages(prev => [...prev, {
        id:    `err-${Date.now()}`,
        role:  'assistant',
        error: 'Connection error — please try again.',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="flex flex-col h-full">

      {/* ── Suggestion chips — horizontal scroll row ──────────────── */}
      {suggestions.length > 0 && (
        <div
          className="flex-shrink-0 px-4 pt-2.5 pb-3"
          style={{
            background: 'rgba(255,255,255,0.75)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderBottom: '1px solid rgba(255,255,255,0.9)',
          }}
        >
          <p className="text-[10px] font-black text-gray-400 mb-2 uppercase tracking-widest">Try asking</p>
          <div className="flex gap-2 overflow-x-auto scrollbar-none pb-0.5">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSend(s)}
                className="flex-shrink-0 text-xs text-gray-600 hover:text-brand-600 px-3.5 py-1.5 rounded-full transition-all duration-150 font-semibold whitespace-nowrap"
                style={{
                  background: 'rgba(255,255,255,0.9)',
                  border: '1px solid rgba(99,102,241,0.15)',
                  boxShadow: '0 1px 6px rgba(99,102,241,0.06)',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'rgba(99,102,241,0.08)'
                  e.currentTarget.style.borderColor = 'rgba(99,102,241,0.35)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.9)'
                  e.currentTarget.style.borderColor = 'rgba(99,102,241,0.15)'
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Messages ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scroll-smooth-ios px-4 py-4 space-y-4" style={{ background: 'transparent' }}>
        {histLoading ? (
          <div className="flex items-center justify-center py-16 text-gray-300 text-sm gap-2">
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Loading conversation…
          </div>
        ) : (
          messages.map(msg => <MessageBubble key={msg.id} message={msg} />)
        )}

        {loading && <TypingIndicator step={progressStep} />}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ─────────────────────────────────────────────── */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{
          background: 'rgba(255,255,255,0.80)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(255,255,255,0.9)',
          boxShadow: '0 -4px 24px rgba(99,102,241,0.05)',
        }}
      >
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="Ask a question about your sales data…"
              disabled={loading}
              className="w-full px-4 py-2.5 pr-10 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-400/50 focus:border-transparent transition-all duration-150 disabled:opacity-50 resize-none overflow-hidden leading-relaxed"
              style={{
                background: 'rgba(255,255,255,0.9)',
                border: '1px solid rgba(99,102,241,0.18)',
                boxShadow: '0 1px 8px rgba(99,102,241,0.07)',
                minHeight: '42px',
                maxHeight: '120px',
              }}
            />
            {input.length > 0 && (
              <span className="absolute right-3 bottom-3 text-[10px] text-gray-300 font-mono select-none leading-none">
                ↵
              </span>
            )}
          </div>
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="text-white px-5 py-2.5 rounded-2xl font-bold text-sm active:scale-95 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            style={{
              background: loading || !input.trim()
                ? 'linear-gradient(135deg, #a5b4fc, #c4b5fd)'
                : 'linear-gradient(135deg, #4f46e5, #7c3aed, #9333ea)',
              boxShadow: loading || !input.trim() ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
            }}
          >
            {loading ? (
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
            ) : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function welcomeMsg(name, client) {
  return { id: 'welcome', role: 'assistant', isWelcome: true, name, client }
}

function hydrateRow(row) {
  let raw_data = null, metadata = null
  try { raw_data = row.raw_data ? JSON.parse(row.raw_data) : null } catch { /* ignore */ }
  try { metadata = row.metadata ? JSON.parse(row.metadata) : null } catch { /* ignore */ }
  if (row.role === 'user') return { id: row.message_id, role: 'user', text: row.content }
  return {
    id: row.message_id, role: 'assistant',
    data: { success: true, response: row.content, raw_data, query_type: row.query_type, metadata },
  }
}

const STEPS = [
  { key: 'intent',   label: 'Understanding' },
  { key: 'validate', label: 'Validating'    },
  { key: 'exec',     label: 'Running query' },
  { key: 'format',   label: 'Formatting'    },
]

function TypingIndicator({ step }) {
  const activeIdx = step ? STEPS.findIndex(s => s.key === step.step) : 0

  return (
    <div className="flex items-start gap-2 animate-slide-in">
      <BotAvatar />
      <div
        className="rounded-2xl rounded-tl-sm px-4 py-3 min-w-[220px]"
        style={{
          background: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.95)',
          boxShadow: '0 2px 16px rgba(99,102,241,0.10)',
        }}
      >
        {/* Live step message */}
        {step?.msg && (
          <p className="text-xs font-semibold text-violet-600 mb-2.5 tracking-tight">
            {step.msg}
          </p>
        )}

        {/* Step pills */}
        <div className="flex gap-1.5 flex-wrap">
          {STEPS.map((s, i) => {
            const done    = i < activeIdx
            const active  = i === activeIdx
            const pending = i > activeIdx
            return (
              <span
                key={s.key}
                className="text-[10px] font-bold px-2 py-0.5 rounded-full transition-all duration-300"
                style={{
                  background: done    ? 'rgba(16,185,129,0.12)'  :
                              active  ? 'rgba(99,102,241,0.12)'  :
                                        'rgba(0,0,0,0.04)',
                  color:      done    ? '#059669' :
                              active  ? '#4f46e5' :
                                        '#9ca3af',
                  border:     `1px solid ${done ? 'rgba(16,185,129,0.3)' : active ? 'rgba(99,102,241,0.3)' : 'transparent'}`,
                }}
              >
                {done ? '✓ ' : active ? '⟳ ' : ''}{s.label}
              </span>
            )
          })}
        </div>

        {/* Animated progress bar */}
        <div className="mt-2.5 h-0.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
          <div
            className="h-full rounded-full transition-all duration-700 ease-out"
            style={{
              width: `${Math.max(8, ((activeIdx + 1) / STEPS.length) * 100)}%`,
              background: 'linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7)',
            }}
          />
        </div>
      </div>
    </div>
  )
}

function BotAvatar() {
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
      style={{
        background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
        boxShadow: '0 2px 10px rgba(99,102,241,0.4)',
      }}
    >
      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    </div>
  )
}
