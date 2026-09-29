import { useEffect, useRef, useState } from 'react'
import AuthScreen from './components/AuthScreen.jsx'
import Workspace from './Workspace.jsx'
import { createAuthRequestGate, identityEpoch, resolveBootState, subscribeToAuthChanges } from './services/authState.js'
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
      if (!requests.current.isCurrent(token)) return
      identityEpoch.invalidate()
      setStartView(selectedMode === 'signup' ? 'profile' : 'dashboard')
      setAuth({ status: 'signedIn', user: account })
      announceAccountChange()
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
      if (!requests.current.isCurrent(token)) return
      setAuth({ status: 'signedOut', user: null })
      setMode('login')
      announceAccountChange()
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

  return <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:py-16">
    <div className="mx-auto max-w-lg">
      <header className="mb-8"><h1 className="text-3xl font-semibold tracking-tight">FinApp</h1>
        <p className="mt-2 text-slate-600">Your saved financial profile, goals, and explained advisory plans.</p></header>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        {auth.status === 'checking' ? <p role="status">Checking your session…</p>
          : auth.status === 'unavailable' ? <div role="alert"><h2 className="text-xl font-semibold">API unavailable</h2>
            <p className="mt-2 text-sm text-slate-600">Your account status could not be checked. Check the backend and try again.</p>
            <button onClick={checkSession} className="mt-4 rounded-lg bg-slate-900 px-5 py-2 text-sm text-white">Retry connection</button></div>
            : <AuthScreen key={mode} mode={mode} pending={pending} error={error} onSubmit={submit}
                onMode={(next) => { setMode(next); setError('') }} />}
      </section>
      <p className="mt-5 text-sm text-slate-500">Educational research prototype. Use practice financial values.</p>
    </div>
  </main>
}
