const ROLE_COLORS = {
  NSM: 'bg-purple-100 text-purple-700',
  ZSM: 'bg-blue-100 text-blue-700',
  ASM: 'bg-green-100 text-green-700',
  SO:  'bg-orange-100 text-orange-700',
  admin:   'bg-gray-100 text-gray-700',
  analyst: 'bg-sky-100 text-sky-700',
}

export default function Header({ user, onLogout, onMenuToggle }) {
  const roleColor = ROLE_COLORS[user?.role] || 'bg-gray-100 text-gray-700'
  const clientLabel = (user?.client_id || '').charAt(0).toUpperCase() + (user?.client_id || '').slice(1)

  return (
    <header className="gradient-brand text-white flex-shrink-0">
      <div className="px-5 py-4 flex items-center justify-between">
        {/* Hamburger for sidebar (mobile / chat tab) */}
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="md:hidden mr-2 p-1.5 rounded-lg bg-white/20 hover:bg-white/30 transition"
          >
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}

        {/* Left: branding */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-bold leading-tight">CPG Sales Assistant</h1>
            <p className="text-white/70 text-xs">AI-powered analytics &amp; insights</p>
          </div>
        </div>

        {/* Centre: user pill */}
        <div className="hidden sm:flex items-center gap-3 bg-white/15 backdrop-blur px-4 py-2 rounded-full border border-white/25">
          <div className="w-7 h-7 bg-white/30 rounded-full flex items-center justify-center text-xs font-bold">
            {(user?.full_name || 'U').charAt(0)}
          </div>
          <div className="text-sm leading-tight">
            <div className="font-semibold">{user?.full_name}</div>
            <div className="text-white/70 text-xs">{clientLabel}</div>
          </div>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${roleColor}`}>
            {user?.role}
          </span>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          {/* Dashboard button intentionally removed — requires Metabase on port 3000 */}
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 bg-white/20 hover:bg-white/30 border border-white/30 px-3 py-1.5 rounded-full text-xs font-semibold transition"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logout
          </button>
        </div>
      </div>
    </header>
  )
}
