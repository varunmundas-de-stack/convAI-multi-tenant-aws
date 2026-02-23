import { useState, useEffect } from 'react'
import { fetchInsights, markInsightRead } from '../api/client'

const PRIORITY_BORDER = { high: 'border-l-red-500', medium: 'border-l-orange-400', low: 'border-l-green-500' }
const PRIORITY_BG     = { high: 'bg-red-50', medium: 'bg-orange-50', low: 'bg-green-50' }
const TYPE_BADGE      = {
  trend:          'bg-blue-100 text-blue-700',
  anomaly:        'bg-red-100 text-red-700',
  alert:          'bg-orange-100 text-orange-700',
  recommendation: 'bg-green-100 text-green-700',
  opportunity:    'bg-purple-100 text-purple-700',
}

export default function InsightsTab({ user, onBadgeRefresh, onAskQuery }) {
  const [insights, setInsights]   = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchInsights()
      setInsights(data)
    } catch {
      setError('Could not load insights. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleCardClick = async (insight) => {
    if (!insight.is_read) {
      try {
        await markInsightRead(insight.insight_id)
        setInsights(prev => prev.map(i => i.insight_id === insight.insight_id ? { ...i, is_read: true } : i))
        onBadgeRefresh()
      } catch { /* ignore */ }
    }
    if (insight.suggested_query) {
      onAskQuery(insight.suggested_query)
    }
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin bg-gray-100 px-4 py-5">
      <div className="max-w-4xl mx-auto">
        {/* Heading */}
        <div className="mb-5">
          <h2 className="text-lg font-bold text-gray-800">Your Targeted Insights</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Personalised nudges based on your role &amp; territory — refreshed every 6 hours
          </p>
        </div>

        {/* Refresh button */}
        <div className="flex justify-end mb-4">
          <button
            onClick={load}
            className="text-xs text-brand-500 hover:text-brand-700 flex items-center gap-1 font-medium"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="bg-white rounded-xl h-32 animate-pulse border border-gray-100" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="text-center py-16 text-gray-400">
            <p className="mb-3">{error}</p>
            <button onClick={load} className="text-brand-500 text-sm font-medium hover:underline">Try again</button>
          </div>
        )}

        {!loading && !error && insights.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm leading-relaxed max-w-sm mx-auto">
            <div className="text-4xl mb-3">🎯</div>
            {user?.sales_hierarchy_level ? (
              <>
                <p className="font-medium text-gray-500">Insights are being generated…</p>
                <p className="mt-2 text-xs">The system generates targeted nudges for your role (<strong>{user.sales_hierarchy_level}</strong>) every 6 hours.</p>
                <p className="mt-1 text-xs">Check back in a few minutes after the server starts.</p>
              </>
            ) : (
              <>
                <p className="font-medium text-gray-500">Targeted Insights are for the sales field team</p>
                <p className="mt-2 text-xs">This feed delivers role-specific nudges to <strong>SO → ASM → ZSM → NSM</strong> users based on their territory data.</p>
                <p className="mt-3 text-xs bg-brand-50 border border-brand-100 rounded-lg px-4 py-2 text-brand-600">
                  Try logging in as <strong>nsm_rajesh</strong> (nsm123) or <strong>so_field1</strong> (so123) to see insights in action.
                </p>
              </>
            )}
            <p className="mt-4 text-xs">Use <strong>Ask your own Q</strong> to explore your data right now.</p>
          </div>
        )}

        {!loading && !error && insights.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {insights.map(ins => (
              <InsightCard key={ins.insight_id} insight={ins} onClick={() => handleCardClick(ins)} />
            ))}
          </div>
        )}

        {!loading && insights.length > 0 && (
          <p className="text-center text-xs text-gray-300 mt-5">Insights refresh every 6 hours</p>
        )}
      </div>
    </div>
  )
}

function InsightCard({ insight: ins, onClick }) {
  const isUnread    = !ins.is_read
  const borderColor = PRIORITY_BORDER[ins.priority] || 'border-l-gray-300'
  const bgColor     = isUnread ? (PRIORITY_BG[ins.priority] || 'bg-white') : 'bg-white'
  const typeBadge   = TYPE_BADGE[ins.insight_type] || 'bg-gray-100 text-gray-600'
  const changePct   = ins.metric_change_pct

  return (
    <div
      onClick={onClick}
      className={`relative rounded-xl border-l-4 border border-gray-100 p-4 cursor-pointer shadow-sm
        hover:-translate-x-0.5 hover:shadow-md transition-all duration-150
        ${borderColor} ${bgColor}`}
    >
      {isUnread && (
        <span className="absolute top-3 right-3 w-2 h-2 bg-red-500 rounded-full" />
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${typeBadge}`}>
          {ins.insight_type}
        </span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase
          ${ins.priority === 'high' ? 'bg-red-100 text-red-700' : ins.priority === 'medium' ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
          {ins.priority}
        </span>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase bg-gray-100 text-gray-500">
          {ins.hierarchy_level}
        </span>
      </div>

      {/* Title + change % */}
      <div className="text-sm font-semibold text-gray-800 mb-1 leading-snug">
        {ins.title}
        {changePct != null && (
          <span className={`ml-1.5 font-bold ${changePct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {changePct >= 0 ? '+' : ''}{changePct.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-xs text-gray-500 leading-relaxed mb-2">{ins.description}</p>

      {/* Suggested action */}
      {ins.suggested_action && (
        <p className="text-xs text-brand-500 font-semibold">→ {ins.suggested_action}</p>
      )}

      <p className="text-[10px] text-gray-300 mt-2 italic">Click to explore in chat →</p>
    </div>
  )
}
