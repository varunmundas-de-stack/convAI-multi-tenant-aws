import { useState, useEffect, useRef } from 'react'
import {
  fetchSuggestions, sendQuery,
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

  // activeSession tracks the session we are writing to (may be created lazily)
  const activeSessionRef = useRef(sessionId)

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // ── Load suggestions once ──────────────────────────────────────
  useEffect(() => {
    fetchSuggestions().then(setSuggestions).catch(() => {})
  }, [])

  // ── Load history when sessionId changes ───────────────────────
  useEffect(() => {
    activeSessionRef.current = sessionId

    if (!sessionId) {
      // No session selected → show welcome screen only
      setMessages([welcomeMsg(user?.full_name, clientLabel)])
      return
    }

    setHistLoading(true)
    fetchSessionMessages(sessionId)
      .then(rows => {
        if (rows.length === 0) {
          setMessages([welcomeMsg(user?.full_name, clientLabel)])
        } else {
          // Re-hydrate stored messages into the same shape MessageBubble expects
          setMessages(rows.map(r => hydrateRow(r)))
        }
      })
      .catch(() => setMessages([welcomeMsg(user?.full_name, clientLabel)]))
      .finally(() => setHistLoading(false))
  }, [sessionId])

  // ── Handle prefill from Insights tab ──────────────────────────
  useEffect(() => {
    if (prefillQuery) {
      setInput(prefillQuery)
      onPrefillConsumed?.()
      inputRef.current?.focus()
    }
  }, [prefillQuery])

  // ── Auto-scroll ────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Ensure we have an active session, creating one lazily ──────
  const ensureSession = async (firstUserMessage) => {
    if (activeSessionRef.current) return activeSessionRef.current
    const s = await createSession(firstUserMessage.slice(0, 80))
    activeSessionRef.current = s.session_id
    onSessionCreated?.(s.session_id)
    return s.session_id
  }

  // ── Send ───────────────────────────────────────────────────────
  const handleSend = async () => {
    const q = input.trim()
    if (!q || loading) return

    const tempId = `tmp-${Date.now()}`
    setMessages(prev => [...prev.filter(m => !m.isWelcome), { id: tempId, role: 'user', text: q }])
    setInput('')
    setLoading(true)

    try {
      const sid = await ensureSession(q)

      // Persist user message
      await saveMessage(sid, { role: 'user', content: q, title_hint: q }).catch(() => {})

      // Call the query API
      const data = await sendQuery(q)

      const assistantMsg = { id: `a-${Date.now()}`, role: 'assistant', data }
      setMessages(prev => [...prev, assistantMsg])

      // Persist assistant message
      await saveMessage(sid, {
        role:       'assistant',
        content:    data.response || '',
        raw_data:   data.raw_data || null,
        query_type: data.query_type || null,
        metadata:   data.metadata  || null,
      }).catch(() => {})

    } catch {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        error: 'Connection error — please try again.',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Suggestion chips */}
      {suggestions.length > 0 && (
        <div className="bg-white border-b border-gray-100 px-4 py-2.5 flex-shrink-0">
          <p className="text-xs text-gray-400 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => { setInput(s); inputRef.current?.focus() }}
                className="text-xs bg-gray-100 hover:bg-brand-500 hover:text-white px-3 py-1.5 rounded-full transition-colors font-medium text-gray-600"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-4 bg-gray-50">
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

        {loading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="bg-white border-t border-gray-200 px-4 py-3 flex-shrink-0">
        <div className="flex gap-2 items-center">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="Ask a question about your CPG data…"
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-full border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition disabled:opacity-60"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="gradient-brand text-white px-5 py-2.5 rounded-full font-semibold text-sm hover:opacity-90 active:scale-95 transition disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────────

function welcomeMsg(name, client) {
  return { id: 'welcome', role: 'assistant', isWelcome: true, name, client }
}

function hydrateRow(row) {
  // Convert a DB row back to the shape MessageBubble expects
  let raw_data = null
  let metadata = null
  try { raw_data = row.raw_data ? JSON.parse(row.raw_data) : null } catch { /* ignore */ }
  try { metadata = row.metadata ? JSON.parse(row.metadata) : null } catch { /* ignore */ }

  if (row.role === 'user') {
    return { id: row.message_id, role: 'user', text: row.content }
  }
  return {
    id:   row.message_id,
    role: 'assistant',
    data: {
      success:    true,
      response:   row.content,
      raw_data:   raw_data,
      query_type: row.query_type,
      metadata:   metadata,
    },
  }
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-2">
      <div className="w-7 h-7 gradient-brand rounded-full flex items-center justify-center flex-shrink-0">
        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-gray-100">
        <div className="flex gap-1.5 items-center h-5">
          {[0, 0.2, 0.4].map((delay, i) => (
            <span key={i} className="w-2 h-2 bg-gray-300 rounded-full dot-bounce"
              style={{ animationDelay: `${delay}s` }} />
          ))}
        </div>
      </div>
    </div>
  )
}
