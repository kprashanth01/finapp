import { useEffect, useRef, useState } from 'react'
import { formatAmount } from './utils/format.js'
import Goals from './components/Goals.jsx'
import useGoals from './hooks/useGoals.js'
import { createOperationGate } from './services/operationGate.js'
import AdvisorySession from './components/AdvisorySession.jsx'
import OrchestrationLab from './components/OrchestrationLab.jsx'
import AdvisoryHistory from './components/AdvisoryHistory.jsx'
import Dashboard from './components/Dashboard.jsx'
import AppShell from './components/AppShell.jsx'
import Research from './components/Research.jsx'
import FinancialAnalysis from './components/FinancialAnalysis.jsx'
import FinancialProfileForm from './components/FinancialProfileForm.jsx'
import UserForm from './components/UserForm.jsx'
import { canStartRun, canStartSave, hasIncomeChanged, hasProfileFinancialChanges, markSessionStale } from './services/advisoryFreshness.js'
import {
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

function Workspace({ initialUser, startView = 'dashboard', onSignOut }) {
  const [activeView, setActiveView] = useState(startView)
  const [connection, setConnection] = useState('checking')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [user, setUser] = useState(initialUser)
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
  const goalsState = useGoals(user?.id)
  const operations = useRef(createOperationGate())
  const advisoryToken = useRef(0)
  const [focusTarget, setFocusTarget] = useState(null)
  const [focusGoalId, setFocusGoalId] = useState(null)

  function openProfile(field) { setFocusTarget(field ?? null); setActiveView('profile') }
  function openGoal(id) { setFocusGoalId(id ?? null); setActiveView('goals') }
  function navigate(view) {
    setMessage('')
    setFocusGoalId(null); setFocusTarget(null)
    if (view === 'advisor' && !profile) setActiveView('profile')
    else setActiveView(view)
  }
  useEffect(() => {
    if (activeView !== 'profile' || !focusTarget) return
    const input = document.querySelector(`[name="${focusTarget}"]`)
    const details = input?.closest('details')
    if (details) details.open = true
    input?.focus()
    input?.scrollIntoView({ block: 'center' })
  }, [activeView, focusTarget])

  async function mutateGoal(operation) {
    if (advisoryRunning || advisoryLoading || goalsState.loading) return null
    const release = operations.current.begin()
    if (!release) return null
    advisoryToken.current += 1
    selectionToken.current += 1
    setSaving(true)
    try {
      const saved = await operation()
      if (!saved) return null
      setAdvisorySession((current) => markSessionStale(current, true))
      setSelectedSession(null); setSelectedSessionError(''); setSelectedSessionLoading(false)
      if (profile) await refreshAdvisory(user.id)
      setHistoryRefreshKey((key) => key + 1)
      return saved
    } finally { setSaving(false); release() }
  }

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
    const token = ++advisoryToken.current
    setAdvisoryLoading(true)
    setAdvisoryError('')
    try {
      const saved = await getLatestAdvisorySession(userId)
      if (token === advisoryToken.current) setAdvisorySession(saved)
    } catch (requestError) {
      if (token !== advisoryToken.current) return
      if (requestError.response?.status === 404) setAdvisorySession(null)
      else setAdvisoryError(`Could not verify whether the saved session is current: ${explainApiError(requestError)}`)
    } finally {
      if (token === advisoryToken.current) setAdvisoryLoading(false)
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
      setError(explainApiError(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    checkConnection(controller.signal)
    loadSavedUser(initialUser.id)
    return () => controller.abort()
  }, [initialUser.id])

  async function handleSaveUser(values) {
    if (!canStartSave({ saving: saving || goalsState.pending || advisoryLoading, running: advisoryRunning })) return
    const release = operations.current.begin()
    if (!release) return
    advisoryToken.current += 1
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await updateUser(user.id, values)
      if (hasIncomeChanged(user, saved)) {
        setAdvisorySession((current) => markSessionStale(current, true))
      }
      setUser(saved)
      setMessage('User details updated.')
      if (profile) {
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
      release()
    }
  }

  async function handleSaveProfile(values, nextView = 'dashboard') {
    if (!canStartSave({ saving: saving || goalsState.pending || advisoryLoading, running: advisoryRunning })) return
    const release = operations.current.begin()
    if (!release) return
    advisoryToken.current += 1
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await saveFinancialProfile(user.id, values)
      setAdvisorySession((current) => markSessionStale(current, hasProfileFinancialChanges(profile, saved)))
      setProfile(saved)
      setMessage('Financial profile saved.')
      setActiveView(nextView)
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
      release()
    }
  }

  async function handleRunAdvisory() {
    if (!profile || !canStartRun({ saving: saving || goalsState.pending, loading: advisoryLoading || goalsState.loading || !!goalsState.error, running: advisoryRunning })) return
    const release = operations.current.begin()
    if (!release) return
    advisoryToken.current += 1
    setActiveView('advisor')
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
      release()
    }
  }

  async function handleSelectSession(sessionId) {
    if (saving || advisoryRunning || goalsState.pending) return
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
    <AppShell activeView={activeView} onChangeView={navigate} user={user} connection={connection}
      onRetryConnection={() => checkConnection()} onSignOut={onSignOut}
      signOutDisabled={saving || advisoryRunning || goalsState.pending}>
      <div className="workspace-content">
        <section className="workspace-surface">

          {error && <p role="alert" className="mb-5 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
          {message && <p role="status" className="mb-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}

          {loading ? (
            <p className="text-slate-600">Loading saved profile…</p>
          ) : user ? (
            <>
              {activeView === 'dashboard' && (
                <Dashboard
                  user={user}
                  goals={goalsState.goals}
                  goalsLoading={goalsState.loading}
                  goalsError={goalsState.error}
                  onOpenGoals={() => openGoal(null)}
                  profile={profile}
                  analysis={analysis}
                  advisorySession={advisorySession}
                  advisoryLoading={advisoryLoading}
                  advisoryRunning={advisoryRunning}
                  advisoryError={advisoryError}
                  saving={saving}
                  goalPending={goalsState.pending}
                  onRetryAdvisory={() => refreshAdvisory(user.id)}
                  onRunAdvisory={handleRunAdvisory}
                  onOpenProfile={openProfile}
                  onOpenGoal={openGoal}
                  onOpenAdvisor={() => setActiveView('advisor')}
                />
              )}
              {activeView === 'goals' && <Goals {...goalsState} disabled={saving || advisoryRunning || advisoryLoading} hasProfile={!!profile}
                onCreate={(values) => mutateGoal(() => goalsState.create(values))}
                onUpdate={(id, values) => mutateGoal(() => goalsState.update(id, values))}
                onArchive={(id, archived) => mutateGoal(() => goalsState.setArchived(id, archived))}
                onRetry={goalsState.reload} legacyNote={profile?.financial_goal} focusGoalId={focusGoalId}
                onClearLegacyNote={() => handleSaveProfile({ ...profile, financial_goal: null }, 'goals')}
                onRunAnalysis={handleRunAdvisory} onOpenProfile={() => openProfile(null)} />}
              {activeView === 'goals' && advisoryError && <p role="alert" className="mt-4 text-sm text-amber-900">Your goal changes are saved. {advisoryError} <button className="underline" disabled={saving || advisoryRunning} onClick={() => refreshAdvisory(user.id)}>Retry plan status</button></p>}
              {activeView === 'profile' && (
                <>
                  {!profile && <p className="mb-5 rounded-lg bg-blue-50 p-4 text-sm text-slate-800">Start by entering your gross monthly income in User details, then save your financial profile below. You can add goals afterward.</p>}
                  <details open={!profile} className="mb-8 rounded-lg border border-slate-200 p-4">
                    <summary className="cursor-pointer text-sm font-medium">Gross monthly income (before tax): {formatAmount(user.monthly_income)} · Edit user details</summary>
                    <div className="mt-5"><UserForm user={user} onSave={handleSaveUser} saving={saving} disabled={advisoryRunning || advisoryLoading} /></div>
                  </details>
                  <FinancialProfileForm profile={profile} onSave={handleSaveProfile} saving={saving} disabled={advisoryRunning || advisoryLoading} />
                  {profile && (saving
                    ? <p role="status" className="mt-8 text-sm text-slate-600">Updating financial snapshot…</p>
                    : <FinancialAnalysis analysis={analysis} user={user} profile={profile} />)}
                  <div className="mt-7 rounded-xl border border-teal-200 bg-teal-50 p-4">
                    <h3 className="font-semibold text-teal-950">Track changes month by month</h3>
                    <p className="mt-1 text-sm text-slate-700">Your Profile is the current snapshot. Record past months separately to see how the trained monthly selector responds to income and expense changes.</p>
                    <button type="button" className="mt-3 font-semibold text-teal-800 underline" onClick={() => setActiveView('research')}>Open monthly history</button>
                  </div>
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
                    saving={saving || goalsState.pending || goalsState.loading || !!goalsState.error}
                    onOpenProfile={openProfile}
                    onOpenGoal={openGoal}
                    error={advisoryError}
                    onRun={handleRunAdvisory}
                    historical={selectedSession != null}
                    onShowLatest={() => { selectionToken.current += 1; setSelectedSession(null); setSelectedSessionError(''); setSelectedSessionLoading(false) }}
                  />
                  <OrchestrationLab userId={user.id} onOpenProfile={openProfile} onOpenGoal={openGoal} />
                  <AdvisoryHistory
                    userId={user.id}
                    refreshKey={historyRefreshKey}
                    selectedId={(selectedSession ?? advisorySession)?.id}
                    onSelect={handleSelectSession}
                  />
                </>
              )}
              {activeView === 'research' && <Research userId={user.id} user={user} profile={profile} hasProfile={!!profile} onOpenProfile={() => openProfile(null)} />}
            </>
          ) : (
            <p role="alert">The account could not be loaded. Refresh to retry.</p>
          )}
        </section>
        <p className="app-disclaimer">Educational research prototype. Use practice values for your profile.</p>
      </div>
    </AppShell>
  )
}

export default Workspace
