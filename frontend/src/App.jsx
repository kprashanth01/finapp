import { useEffect, useRef, useState } from 'react'
import AdvisorySession from './components/AdvisorySession.jsx'
import AdvisoryHistory from './components/AdvisoryHistory.jsx'
import Dashboard from './components/Dashboard.jsx'
import FinancialAnalysis from './components/FinancialAnalysis.jsx'
import FinancialProfileForm from './components/FinancialProfileForm.jsx'
import UserForm from './components/UserForm.jsx'
import { canStartRun, canStartSave, hasIncomeChanged, hasProfileFinancialChanges, markSessionStale } from './services/advisoryFreshness.js'
import {
  createUser,
  explainApiError,
  getFinancialAnalysis,
  getFinancialProfile,
  getHealth,
  getLatestAdvisorySession,
  getAdvisorySession,
  getUser,
  saveFinancialProfile,
  runAdvisorySession,
  updateUser,
} from './services/api.js'

const savedUserKey = 'finapp.userId'

function App() {
  const [activeView, setActiveView] = useState('dashboard')
  const [savedUserId, setSavedUserId] = useState(() => localStorage.getItem(savedUserKey))
  const [connection, setConnection] = useState('checking')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [advisorySession, setAdvisorySession] = useState(null)
  const [advisoryLoading, setAdvisoryLoading] = useState(false)
  const [advisoryRunning, setAdvisoryRunning] = useState(false)
  const [advisoryError, setAdvisoryError] = useState('')
  const [selectedSession, setSelectedSession] = useState(null)
  const [selectedSessionError, setSelectedSessionError] = useState('')
  const [selectedSessionLoading, setSelectedSessionLoading] = useState(false)
  const selectionToken = useRef(0)
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function checkConnection(signal) {
    setConnection('checking')
    try {
      const health = await getHealth(signal)
      setConnection(health.status === 'ok' ? 'connected' : 'unavailable')
    } catch (requestError) {
      if (requestError.name !== 'CanceledError') setConnection('unavailable')
    }
  }

  async function refreshAdvisory(userId) {
    setAdvisoryLoading(true)
    setAdvisoryError('')
    try {
      setAdvisorySession(await getLatestAdvisorySession(userId))
    } catch (requestError) {
      if (requestError.response?.status === 404) setAdvisorySession(null)
      else setAdvisoryError(`Could not verify whether the saved session is current: ${explainApiError(requestError)}`)
    } finally {
      setAdvisoryLoading(false)
    }
  }

  async function loadSavedUser(userId) {
    setLoading(true)
    setError('')
    try {
      const loadedUser = await getUser(userId)
      let loadedProfile = null
      try {
        loadedProfile = await getFinancialProfile(userId)
      } catch (requestError) {
        if (requestError.response?.status !== 404) throw requestError
      }
      setUser(loadedUser)
      setProfile(loadedProfile)
      if (loadedProfile) {
        try {
          setAnalysis(await getFinancialAnalysis(userId))
        } catch (analysisError) {
          setAnalysis(null)
          setError(`Profile loaded, but analysis could not load: ${explainApiError(analysisError)}`)
        }
        await refreshAdvisory(userId)
      } else {
        setAnalysis(null)
        setAdvisorySession(null)
      }
    } catch (requestError) {
      if (requestError.response?.status === 404) {
        localStorage.removeItem(savedUserKey)
        setSavedUserId(null)
        setUser(null)
        setProfile(null)
        setAnalysis(null)
        setAdvisorySession(null)
        selectionToken.current += 1
        setSelectedSession(null)
        setMessage('The saved user was not found. Create a new user to continue.')
      } else {
        setError(explainApiError(requestError))
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    checkConnection(controller.signal)
    if (savedUserId) loadSavedUser(savedUserId)
    else setLoading(false)
    return () => controller.abort()
  }, [])

  async function handleSaveUser(values) {
    if (!canStartSave({ saving, running: advisoryRunning })) return
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = user ? await updateUser(user.id, values) : await createUser(values)
      if (user && hasIncomeChanged(user, saved)) {
        setAdvisorySession((current) => markSessionStale(current, true))
      }
      if (!user) {
        localStorage.setItem(savedUserKey, String(saved.id))
        setSavedUserId(String(saved.id))
        setActiveView('profile')
      }
      setUser(saved)
      setMessage(user ? 'User details updated.' : 'User created. Now save a financial profile.')
      if (user && profile) {
        try {
          setAnalysis(await getFinancialAnalysis(saved.id))
        } catch (analysisError) {
          setAnalysis(null)
          setError(`User details saved, but analysis could not load: ${explainApiError(analysisError)}`)
        }
        await refreshAdvisory(saved.id)
        selectionToken.current += 1
        setSelectedSession(null)
        setSelectedSessionError('')
        setSelectedSessionLoading(false)
        setHistoryRefreshKey((value) => value + 1)
      }
    } catch (requestError) {
      setError(explainApiError(requestError))
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveProfile(values) {
    if (!canStartSave({ saving, running: advisoryRunning })) return
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await saveFinancialProfile(user.id, values)
      setAdvisorySession((current) => markSessionStale(current, hasProfileFinancialChanges(profile, saved)))
      setProfile(saved)
      setMessage('Financial profile saved.')
      setActiveView('dashboard')
      try {
        setAnalysis(await getFinancialAnalysis(user.id))
      } catch (analysisError) {
        setAnalysis(null)
        setError(`Profile saved, but analysis could not load: ${explainApiError(analysisError)}`)
      }
      await refreshAdvisory(user.id)
      selectionToken.current += 1
      setSelectedSession(null)
      setSelectedSessionError('')
      setSelectedSessionLoading(false)
      setHistoryRefreshKey((value) => value + 1)
    } catch (requestError) {
      setError(explainApiError(requestError))
    } finally {
      setSaving(false)
    }
  }

  async function handleRunAdvisory() {
    if (!canStartRun({ saving, loading: advisoryLoading, running: advisoryRunning })) return
    setAdvisoryRunning(true)
    setAdvisoryError('')
    try {
      setAdvisorySession(await runAdvisorySession(user.id))
      selectionToken.current += 1
      setSelectedSession(null)
      setSelectedSessionError('')
      setSelectedSessionLoading(false)
      setHistoryRefreshKey((value) => value + 1)
    } catch (requestError) {
      setAdvisoryError(explainApiError(requestError))
    } finally {
      setAdvisoryRunning(false)
    }
  }

  async function handleSelectSession(sessionId) {
    const requestId = ++selectionToken.current
    setSelectedSessionError('')
    if (sessionId === advisorySession?.id) {
      setSelectedSession(null)
      setSelectedSessionLoading(false)
      return
    }
    setSelectedSessionLoading(true)
    try {
      const saved = await getAdvisorySession(user.id, sessionId)
      if (requestId === selectionToken.current) setSelectedSession(saved)
    } catch (requestError) {
      if (requestId === selectionToken.current) setSelectedSessionError(`Could not open that saved run: ${explainApiError(requestError)}`)
    } finally {
      if (requestId === selectionToken.current) setSelectedSessionLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:py-16">
      <div className="mx-auto max-w-3xl">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">FinApp</h1>
          <p className="mt-2 text-slate-600">Save your financial profile, review transparent calculations, and run an explained rule-based analysis.</p>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-7 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-5">
            <div className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
              <span className={`h-2.5 w-2.5 rounded-full ${connection === 'connected' ? 'bg-emerald-500' : connection === 'checking' ? 'bg-amber-400' : 'bg-rose-500'}`} aria-hidden="true" />
              <span>{connection === 'connected' ? 'API connected' : connection === 'checking' ? 'Checking API connection…' : 'API unavailable'}</span>
            </div>
            <button type="button" onClick={() => checkConnection()} className="text-sm font-medium text-slate-700 underline underline-offset-4 hover:text-slate-900">
              Retry connection
            </button>
          </div>

          {error && <p role="alert" className="mb-5 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
          {message && <p role="status" className="mb-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}

          {loading ? (
            <p className="text-slate-600">Loading saved profile…</p>
          ) : user ? (
            <>
              <div className="mb-8 rounded-lg bg-slate-50 p-4 text-sm">
                <p className="font-medium">User: {user.name}</p>
                <p className="mt-1 text-slate-600">{user.email}</p>
                <p className="mt-2 text-slate-500">This browser remembers user #{user.id} for reloads. Login is not implemented yet.</p>
              </div>
              <nav aria-label="FinApp views" className="mb-8 flex flex-wrap gap-2 border-b border-slate-200 pb-4">
                {[
                  ['dashboard', 'Dashboard'],
                  ['profile', 'Profile'],
                  ['advisor', 'Advisor'],
                ].map(([view, label]) => (
                  <button
                    key={view}
                    type="button"
                    onClick={() => setActiveView(view)}
                    disabled={view === 'advisor' && !profile}
                    aria-current={activeView === view ? 'page' : undefined}
                    className={`rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40 ${activeView === view ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                  >
                    {label}
                  </button>
                ))}
              </nav>
              {activeView === 'dashboard' && (
                <Dashboard
                  user={user}
                  profile={profile}
                  analysis={analysis}
                  advisorySession={advisorySession}
                  onOpenProfile={() => setActiveView('profile')}
                  onOpenAdvisor={() => setActiveView('advisor')}
                />
              )}
              {activeView === 'profile' && (
                <>
                  <details className="mb-8 rounded-lg border border-slate-200 p-4">
                    <summary className="cursor-pointer text-sm font-medium">Edit user details</summary>
                    <div className="mt-5"><UserForm user={user} onSave={handleSaveUser} saving={saving} disabled={advisoryRunning} /></div>
                  </details>
                  <FinancialProfileForm profile={profile} onSave={handleSaveProfile} saving={saving} disabled={advisoryRunning} />
                  {profile && <FinancialAnalysis analysis={analysis} user={user} profile={profile} />}
                </>
              )}
              {activeView === 'advisor' && profile && (
                <>
                  {selectedSessionLoading && <p className="text-sm text-slate-600">Opening saved run…</p>}
                  {selectedSessionError && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{selectedSessionError}</p>}
                  <AdvisorySession
                    key={(selectedSession ?? advisorySession)?.id ?? 'empty'}
                    session={selectedSession ?? advisorySession}
                    loading={advisoryLoading}
                    running={advisoryRunning}
                    saving={saving}
                    error={advisoryError}
                    onRun={handleRunAdvisory}
                    historical={selectedSession != null}
                    onShowLatest={() => { selectionToken.current += 1; setSelectedSession(null); setSelectedSessionError(''); setSelectedSessionLoading(false) }}
                  />
                  <AdvisoryHistory
                    userId={user.id}
                    refreshKey={historyRefreshKey}
                    selectedId={(selectedSession ?? advisorySession)?.id}
                    onSelect={handleSelectSession}
                  />
                </>
              )}
            </>
          ) : savedUserId ? (
            <div>
              <h2 className="text-xl font-semibold">Saved user unavailable</h2>
              <p className="mt-2 text-sm text-slate-600">The browser still remembers this user. Retry after checking the API and database connection.</p>
              <button type="button" onClick={() => loadSavedUser(savedUserId)} className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700">
                Reload saved user
              </button>
            </div>
          ) : (
            <UserForm onSave={handleSaveUser} saving={saving} />
          )}
        </section>
        <p className="mx-auto mt-5 max-w-3xl text-sm text-slate-500">Local research prototype. Use practice values until authentication is added.</p>
      </div>
    </main>
  )
}

export default App
