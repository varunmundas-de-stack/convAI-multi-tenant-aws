import { useState } from 'react'
import DataChart from './DataChart'

export default function MessageBubble({ message }) {
  if (message.isWelcome) return <WelcomeCard name={message.name} client={message.client} />
  if (message.role === 'user') return <UserBubble text={message.text} />
  return <AssistantBubble message={message} />
}

function UserBubble({ text }) {
  return (
    <div className="flex justify-end animate-slide-in">
      <div className="max-w-[75%]">
        <div
          className="text-white px-4 py-2.5 rounded-2xl rounded-br-sm text-sm"
          style={{
            background: 'linear-gradient(135deg, #4f46e5, #7c3aed, #9333ea)',
            boxShadow: '0 4px 16px rgba(99,102,241,0.35)',
          }}
        >
          {text}
        </div>
        <p className="text-[10px] text-gray-300 mt-1 text-right">{timestamp()}</p>
      </div>
    </div>
  )
}

function AssistantBubble({ message }) {
  const { data, error } = message
  const [showSQL, setShowSQL] = useState(false)

  if (error) {
    return (
      <div className="flex gap-2 animate-slide-in">
        <BotAvatar />
        <div
          className="max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm"
          style={{
            background: 'rgba(254,242,242,0.9)',
            border: '1px solid rgba(252,165,165,0.5)',
            color: '#b91c1c',
            backdropFilter: 'blur(12px)',
          }}
        >
          {error}
        </div>
      </div>
    )
  }

  if (!data) return null
  const { success, response, raw_data, metadata, query_type } = data

  return (
    <div className="flex gap-2 animate-slide-in">
      <BotAvatar />
      <div className="max-w-[88%] space-y-2">
        <div
          className="rounded-2xl rounded-tl-sm px-4 py-3"
          style={{
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(255,255,255,0.9)',
            boxShadow: '0 2px 16px rgba(99,102,241,0.07)',
          }}
        >
          {/* Natural summary for multi-row data */}
          {raw_data?.length > 0 && query_type !== 'diagnostic' && (
            <NaturalSummary data={raw_data} />
          )}

          {/* Main response HTML — overflow-x-auto ensures wide tables scroll on mobile */}
          {response && (
            <div className="overflow-x-auto">
              <div
                className="text-sm text-gray-700 prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: success ? response : `<span class="text-red-600">${response}</span>` }}
              />
            </div>
          )}

          {/* Chart */}
          {raw_data?.length >= 2 && query_type !== 'diagnostic' && (
            <DataChart data={raw_data} />
          )}

          {/* CSV export */}
          {raw_data?.length > 0 && (
            <div className="mt-2">
              <button
                onClick={() => downloadCSV(raw_data)}
                className="text-xs text-gray-400 hover:text-emerald-600 flex items-center gap-1 transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download CSV
              </button>
            </div>
          )}

          {/* SQL toggle */}
          {metadata?.sql && (
            <div className="mt-3">
              <button
                onClick={(e) => { e.stopPropagation(); setShowSQL(v => !v) }}
                className="text-xs text-gray-400 hover:text-brand-500 flex items-center gap-1 transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                {showSQL ? 'Hide SQL' : 'Show SQL'}
              </button>
              {showSQL && (
                <pre
                  className="mt-2 text-xs rounded-xl p-3 overflow-x-auto font-mono leading-relaxed"
                  style={{
                    background: 'linear-gradient(135deg, #0f0c29, #302b63, #24243e)',
                    color: '#86efac',
                    border: '1px solid rgba(99,102,241,0.2)',
                  }}
                >
                  {metadata.sql}
                </pre>
              )}
            </div>
          )}

          {/* Metadata footer */}
          {metadata && (
            <p className="text-[10px] text-gray-300 mt-2 pt-2 border-t border-gray-100/80">
              Intent: {metadata.intent} · Confidence: {((metadata.confidence || 0) * 100).toFixed(0)}% · {metadata.exec_time_ms?.toFixed(0)}ms
            </p>
          )}
        </div>
        <p className="text-[10px] text-gray-300 ml-1">{timestamp()}</p>
      </div>
    </div>
  )
}

function NaturalSummary({ data }) {
  if (!data?.length) return null
  const cols  = Object.keys(data[0])
  const count = data.length

  // Identify the best value column (numeric, highest magnitude) and dimension column
  const numCols = cols.filter(c => typeof data[0][c] === 'number')
  const strCols = cols.filter(c => typeof data[0][c] === 'string')

  // Value col = numeric col with the largest average value (avoids picking week=5 over sales=345000)
  const valCol = numCols.length === 0 ? null
    : numCols.reduce((best, c) => {
        const avg = data.reduce((s, r) => s + Math.abs(r[c] ?? 0), 0) / data.length
        const bestAvg = data.reduce((s, r) => s + Math.abs(r[best] ?? 0), 0) / data.length
        return avg > bestAvg ? c : best
      })

  // Dim col = string col preferred; else the numeric col that is NOT the value col
  const dimCol = strCols[0] ?? numCols.find(c => c !== valCol) ?? null

  if (!valCol) return null

  const fmt = (n) => typeof n === 'number'
    ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 })
    : String(n ?? '')

  // For multi-row: find the actual peak row by value (not just first row)
  const peakRow = count === 1 ? data[0]
    : [...data].sort((a, b) => (b[valCol] ?? 0) - (a[valCol] ?? 0))[0]

  const dimVal = dimCol ? peakRow[dimCol] : null
  const numVal = peakRow[valCol]

  // Format label: if it's a number (e.g. week=6), prefix with column name "Week 6"
  const label = dimVal == null ? null
    : typeof dimVal === 'number'
      ? `${dimCol.charAt(0).toUpperCase() + dimCol.slice(1)} ${dimVal}`
      : String(dimVal)

  const BANNER = {
    background: 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.08))',
    borderLeft: '3px solid #6366f1',
  }

  if (count === 1) {
    return (
      <div className="mb-2 px-3 py-2 rounded-xl text-sm" style={BANNER}>
        {label && <span className="text-gray-500">{label}: </span>}
        <span className="font-black text-brand-600">{fmt(numVal)}</span>
      </div>
    )
  }

  return (
    <div className="mb-2 px-3 py-2 rounded-xl text-sm text-gray-600" style={BANNER}>
      Found <strong>{count}</strong> results
      {label
        ? <> · Top: <strong>{label}</strong> — <span className="font-black text-brand-600">{fmt(numVal)}</span></>
        : <> · Peak: <span className="font-black text-brand-600">{fmt(numVal)}</span></>
      }
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

function WelcomeCard({ name, client }) {
  return (
    <div className="flex gap-2 animate-slide-in">
      <BotAvatar />
      <div
        className="rounded-2xl rounded-tl-sm overflow-hidden max-w-[88%]"
        style={{
          background: 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.9)',
          boxShadow: '0 4px 20px rgba(99,102,241,0.1)',
        }}
      >
        {/* Gradient header strip */}
        <div
          className="px-4 py-3"
          style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed, #9333ea)' }}
        >
          <p className="text-sm font-black text-white leading-snug">
            Hey {name}! 👋
          </p>
          <p className="text-xs text-white/70 mt-0.5">
            Welcome to <strong className="text-white">{client}</strong> Analytics
          </p>
        </div>

        <div className="px-4 py-3 text-xs space-y-2">
          <div
            className="px-3 py-2 rounded-xl"
            style={{
              background: 'rgba(16,185,129,0.07)',
              borderLeft: '3px solid #10b981',
            }}
          >
            <p className="font-bold text-emerald-700 mb-1">✓ You CAN ask about:</p>
            <ul className="text-emerald-600 space-y-0.5 list-disc list-inside">
              <li>{client} sales, brands, SKUs and products</li>
              <li>Distribution channels and customer insights</li>
              <li>Time-based trends and performance metrics</li>
              <li>Diagnostic analysis ("Why did sales change?")</li>
            </ul>
          </div>
          <div
            className="px-3 py-2 rounded-xl"
            style={{
              background: 'rgba(244,63,94,0.07)',
              borderLeft: '3px solid #f43f5e',
            }}
          >
            <p className="font-bold text-rose-700 mb-1">✗ You CANNOT ask about:</p>
            <ul className="text-rose-600 space-y-0.5 list-disc list-inside">
              <li>Other companies' data</li>
              <li>Database metadata or schema information</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function timestamp() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function downloadCSV(data) {
  if (!data?.length) return
  const headers = Object.keys(data[0])
  const escape  = (v) => {
    const s = String(v ?? '')
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
  }
  const rows = [headers.join(','), ...data.map(row => headers.map(h => escape(row[h])).join(','))]
  const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `cpg-export-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
