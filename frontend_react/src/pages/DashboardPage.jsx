import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import InsightsTab from '../components/InsightsTab'
import ChatTab from '../components/ChatTab'
import SessionSidebar from '../components/SessionSidebar'
import { fetchInsightCount, logoutUser } from '../api/client'

export default function DashboardPage({ user, onLogout }) {
  const navigate = useNavigate()
  const hasSalesHierarchy = Boolean(user?.sales_hierarchy_level)
  const [activeTab, setActiveTab]         = useState(hasSalesHierarchy ? 'insights' : 'chat')
  const [unreadCount, setUnreadCount]     = useState(0)
  const [sidebarOpen, setSidebarOpen]     = useState(false)
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [prefillQuery, setPrefillQuery]   = useState(null)

  useEffect(() => {
    refreshBadge()
    const interval = setInterval(refreshBadge, 30000)
    return () => clearInterval(interval)
  }, [])

  const refreshBadge = async () => {
    try { setUnreadCount(await fetchInsightCount()) } catch { /* silent */ }
  }

  const handleLogout = async () => {
    try { await logoutUser() } catch { /* ignore */ }
    onLogout()
    navigate('/login', { replace: true })
  }

  const handleInsightQuery = (query) => {
    setPrefillQuery(query)
    setActiveTab('chat')
  }

  const handleNewSession = (sessionId) => {
    setActiveSessionId(sessionId)
    setActiveTab('chat')
    setPrefillQuery(null)
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Header
        user={user}
        onLogout={handleLogout}
        onMenuToggle={() => setSidebarOpen(v => !v)}
      />

      {/* Tab bar */}
      <div className="flex bg-white border-b border-gray-200 flex-shrink-0">
        <TabButton
          active={activeTab === 'insights'}
          onClick={() => setActiveTab('insights')}
          icon="🎯"
          label="Targeted Insights"
          badge={unreadCount}
        />
        <TabButton
          active={activeTab === 'chat'}
          onClick={() => setActiveTab('chat')}
          icon="💬"
          label="Ask your own Q"
        />
      </div>

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Session sidebar — only shows on Chat tab */}
        {activeTab === 'chat' && (
          <SessionSidebar
            activeSessionId={activeSessionId}
            onSelect={setActiveSessionId}
            onNew={handleNewSession}
            isOpen={sidebarOpen}
            onClose={() => setSidebarOpen(false)}
          />
        )}

        {/* Content pane */}
        <div className="flex-1 min-w-0">
          {activeTab === 'insights'
            ? <InsightsTab user={user} onBadgeRefresh={refreshBadge} onAskQuery={handleInsightQuery} />
            : <ChatTab
                key={activeSessionId}
                user={user}
                sessionId={activeSessionId}
                onSessionCreated={setActiveSessionId}
                prefillQuery={prefillQuery}
                onPrefillConsumed={() => setPrefillQuery(null)}
              />
          }
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, icon, label, badge }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-3.5 px-5 text-sm font-semibold border-b-2 transition-colors
        ${active
          ? 'text-brand-500 border-brand-500 bg-brand-50'
          : 'text-gray-400 border-transparent hover:text-brand-500 hover:bg-gray-50'
        }`}
    >
      <span className="text-base">{icon}</span>
      <span>{label}</span>
      {badge > 0 && (
        <span className="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full min-w-[20px] text-center">
          {badge > 9 ? '9+' : badge}
        </span>
      )}
    </button>
  )
}
