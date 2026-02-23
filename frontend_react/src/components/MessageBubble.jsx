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
        <div className="gradient-brand text-white px-4 py-2.5 rounded-2xl rounded-br-sm text-sm shadow-sm">
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
        <div className="max-w-[85%] bg-red-50 border border-red-200 text-red-700 rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow-sm">
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
        <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
          {/* Natural summary for multi-row data */}
          {raw_data?.length > 0 && query_type !== 'diagnostic' && (
            <NaturalSummary data={raw_data} />
          )}

          {/* Main response HTML */}
          {response && (
            <div
              className="text-sm text-gray-700 prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: success ? response : `<span class="text-red-600">${response}</span>` }}
            />
          )}

          {/* Chart */}
          {raw_data?.length >= 2 && query_type !== 'diagnostic' && (
            <DataChart data={raw_data} />
          )}

          {/* SQL toggle */}
          {metadata?.sql && (
            <div className="mt-3">
              <button
                onClick={() => setShowSQL(v => !v)}
                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                {showSQL ? 'Hide SQL' : 'Show SQL'}
              </button>
              {showSQL && (
                <pre className="mt-1.5 bg-gray-900 text-green-300 text-xs rounded-lg p-3 overflow-x-auto font-mono leading-relaxed">
                  {metadata.sql}
                </pre>
              )}
            </div>
          )}

          {/* Metadata footer */}
          {metadata && (
            <p className="text-[10px] text-gray-300 mt-2 pt-2 border-t border-gray-50">
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
  const top   = data[0]
  const count = data.length

  if (count === 1) {
    const val = top[cols[0]]
    const fmt = typeof val === 'number' ? val.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : val
    return (
      <div className="mb-2 px-3 py-2 bg-brand-50 border-l-4 border-brand-500 rounded-r-lg text-sm">
        <span className="text-gray-600">{cols[0]}: </span>
        <span className="font-bold text-brand-600">{fmt}</span>
      </div>
    )
  }

  const topVal = top[cols[1]]
  const fmtVal = typeof topVal === 'number' ? topVal.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : topVal
  return (
    <div className="mb-2 px-3 py-2 bg-brand-50 border-l-4 border-brand-500 rounded-r-lg text-sm text-gray-600">
      Found <strong>{count}</strong> results. Top: <strong>{top[cols[0]]}</strong> — <span className="font-bold text-brand-600">{fmtVal}</span>
    </div>
  )
}

function BotAvatar() {
  return (
    <div className="w-7 h-7 gradient-brand rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
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
      <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm max-w-[88%]">
        <p className="text-sm font-semibold text-gray-800 mb-2">
          Hello {name}! Welcome to {client} Analytics.
        </p>
        <div className="text-xs space-y-2">
          <div className="px-3 py-2 bg-blue-50 border-l-4 border-blue-400 rounded-r-lg">
            <p className="font-semibold text-blue-700 mb-1">✓ You CAN ask about:</p>
            <ul className="text-blue-600 space-y-0.5 list-disc list-inside">
              <li>{client} sales, brands, SKUs and products</li>
              <li>Distribution channels and customer insights</li>
              <li>Time-based trends and performance metrics</li>
              <li>Diagnostic analysis ("Why did sales change?")</li>
            </ul>
          </div>
          <div className="px-3 py-2 bg-red-50 border-l-4 border-red-400 rounded-r-lg">
            <p className="font-semibold text-red-700 mb-1">✗ You CANNOT ask about:</p>
            <ul className="text-red-600 space-y-0.5 list-disc list-inside">
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
