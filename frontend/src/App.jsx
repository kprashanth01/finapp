import { useEffect, useRef, useState } from 'react'
import AuthScreen from './components/AuthScreen.jsx'
import Workspace from './Workspace.jsx'
import { createAuthRequestGate, identityEpoch, resolveBootState, settleAuthSuccess, subscribeToAuthChanges } from './services/authState.js'
import { claimEarlierProfile, createUser, explainApiError, getCurrentUser, signIn, signOut } from './services/api.js'

export default function App() {
  const [auth, setAuth] = useState({ status: 'checking', user: null })
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [startView, setStartView] = useState('dashboard')
  const requests = useRef(createAuthRequestGate())
  const authInFlight = useRef(false)
  const accountChannel = useRef(null)

  function announceAccountChange() {
    accountChannel.current?.postMessage({ type: 'account-changed' })
  }

  async function checkSession() {
    const token = requests.current.begin()
    setAuth({ status: 'checking', user: null })
    const next = await resolveBootState(getCurrentUser)
    if (requests.current.isCurrent(token)) setAuth(next)
  }

  function reconcileChangedCookie() {
    identityEpoch.invalidate()
    setPending(false)
    announceAccountChange()
    return checkSession()
  }

  useEffect(() => {
    // Earlier builds stored a user ID here. It is never an authentication credential.
    localStorage.removeItem('finapp.userId')
    function expired() {
      requests.current.invalidate()
      identityEpoch.invalidate()
      setAuth({ status: 'signedOut', user: null })
      setPending(false)
      setMode('login')
      setError('Your session ended. Sign in again to continue.')
    }
    window.addEventListener('finapp:session-expired', expired)
    let unsubscribe
    if (typeof BroadcastChannel !== 'undefined') {
      const channel = new BroadcastChannel('finapp-auth')
      accountChannel.current = channel
      unsubscribe = subscribeToAuthChanges(channel, () => {
        requests.current.invalidate()
        identityEpoch.invalidate()
        setPending(false)
        setError('')
        checkSession()
      })
    }
    checkSession()
    return () => {
      requests.current.invalidate()
      window.removeEventListener('finapp:session-expired', expired)
      unsubscribe?.()
      accountChannel.current = null
    }
  }, [])

  async function submit(selectedMode, values) {
    if (authInFlight.current) return
    authInFlight.current = true
    const token = requests.current.begin()
    identityEpoch.invalidate()
    setError('')
    setPending(true)
    try {
      const account = selectedMode === 'signup' ? await createUser(values)
        : selectedMode === 'claim' ? await claimEarlierProfile(values) : await signIn(values)
      await settleAuthSuccess(requests.current, token, () => {
        identityEpoch.invalidate()
        setStartView(selectedMode === 'signup' ? 'profile' : 'dashboard')
        setAuth({ status: 'signedIn', user: account })
        announceAccountChange()
      }, reconcileChangedCookie)
    } catch (requestError) {
      if (requests.current.isCurrent(token)) setError(explainApiError(requestError))
    } finally {
      if (requests.current.isCurrent(token)) setPending(false)
      authInFlight.current = false
    }
  }

  async function logout() {
    if (authInFlight.current) return
    authInFlight.current = true
    const token = requests.current.begin()
    identityEpoch.invalidate()
    setPending(true)
    setError('')
    try {
      await signOut()
      await settleAuthSuccess(requests.current, token, () => {
        setAuth({ status: 'signedOut', user: null })
        setMode('login')
        announceAccountChange()
      }, reconcileChangedCookie)
    } catch (requestError) {
      if (requests.current.isCurrent(token)) setError(`Sign out failed: ${explainApiError(requestError)}`)
    } finally {
      if (requests.current.isCurrent(token)) setPending(false)
      authInFlight.current = false
    }
  }

  if (auth.status === 'signedIn' && auth.user) {
    return <><Workspace key={auth.user.id} initialUser={auth.user} startView={startView} onSignOut={logout} />
      {error && <p role="alert" className="mx-auto max-w-3xl px-5 text-sm text-rose-800">{error}</p>}
    </>
  }

  return <main className="auth-page">
    <div className="auth-layout">
      <aside className="auth-story">
        <div className="auth-brand"><span className="app-brand-mark" aria-hidden="true"><span /><span /><span /></span>FinApp</div>
        <div className="auth-story-copy"><h1>Make sense of your financial picture.</h1>
          <p>Keep your profile and goals in one place. See the calculations behind a monthly plan, and inspect how the advisory agents were chosen.</p></div>
        <p className="auth-story-note">Educational research prototype · Use practice financial values</p>
      </aside>
      <section className="auth-panel">
        <div className="auth-mobile-brand">FinApp</div>
        {auth.status === 'checking' ? <p role="status">Checking your session…</p>
          : auth.status === 'unavailable' ? <div role="alert"><h2 className="text-xl font-semibold">API unavailable</h2>
            <p className="mt-2 text-sm text-slate-600">Your account status could not be checked. Check the backend and try again.</p>
            <button onClick={checkSession} className="mt-4 rounded-lg bg-slate-900 px-5 py-2 text-sm text-white">Retry connection</button></div>
            : <AuthScreen key={mode} mode={mode} pending={pending} error={error} onSubmit={submit}
                onMode={(next) => { setMode(next); setError('') }} />}
      </section>
    </div>
  </main>
}
