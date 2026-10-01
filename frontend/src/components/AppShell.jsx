const views = [
  ['dashboard', 'Dashboard', 'An overview of your saved finances and latest plan.'],
  ['profile', 'Profile', 'Keep the amounts behind your analysis up to date.'],
  ['months', 'Months', 'Record changing income and check this month’s cash flow.'],
  ['goals', 'Goals', 'See what you are working toward and what each target needs.'],
  ['advisor', 'Advisor', 'Review your coordinated plan and earlier runs.'],
  ['research', 'Research', 'Try agent selections and review the test results.'],
]

function ViewIcon({ view }) {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    months: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18M7 14h3M7 17h3" /></>,
    goals: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>,
    advisor: <><path d="M4 5h16v14H4z" /><path d="M8 10h8M8 14h5" /></>,
    research: <><path d="M5 19h14M7 16l3-6 3 3 4-7" /><circle cx="17" cy="6" r="1" /></>,
  }
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[view]}</svg>
}

export default function AppShell({ activeView, onChangeView, user, connection, onRetryConnection, onSignOut, signOutDisabled, children }) {
  const current = views.find(([view]) => view === activeView) ?? views[0]
  return <div className="app-shell">
    <aside className="app-sidebar">
      <div className="app-brand"><span className="app-brand-mark" aria-hidden="true"><span /><span /><span /></span><span>FinApp</span></div>
      <p className="app-sidebar-caption">YOUR WORKSPACE</p>
      <nav aria-label="FinApp views" className="app-nav">
        {views.map(([view, label]) => <button key={view} type="button" onClick={() => onChangeView(view)}
          aria-current={activeView === view ? 'page' : undefined}
          className={`app-nav-item${activeView === view ? ' is-active' : ''}`}>
          <ViewIcon view={view} /><span>{label}</span>
        </button>)}
      </nav>
      <p className="app-sidebar-note">Your data stays with your account. Research scores are experimental.</p>
    </aside>
    <div className="app-main">
      <header className="app-topbar">
        <div className="app-heading"><h1>{current[1]}</h1><p>{current[2]}</p></div>
        <div className="app-account-tools">
          <button type="button" onClick={onRetryConnection} className="app-connection" aria-label="Retry API connection" title="Check API connection again">
            <span className={`app-status-dot ${connection}`} />
            <span role="status" aria-live="polite">{connection === 'connected' ? 'Connected' : connection === 'checking' ? 'Checking connection' : 'API unavailable'}</span>
          </button>
          <div className="app-account"><span className="app-avatar" aria-hidden="true">{user?.name?.trim()?.[0]?.toUpperCase() ?? 'U'}</span>
            <span className="app-account-name">{user?.name}</span></div>
          <button type="button" className="app-signout" onClick={onSignOut} disabled={signOutDisabled}>Sign out</button>
        </div>
      </header>
      <main id="main-content" className="app-content">{children}</main>
    </div>
  </div>
}
