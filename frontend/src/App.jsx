import { useEffect, useState } from 'react'
import FinancialProfileForm from './components/FinancialProfileForm.jsx'
import UserForm from './components/UserForm.jsx'
import {
  createUser,
  explainApiError,
  getFinancialProfile,
  getHealth,
  getUser,
  saveFinancialProfile,
  updateUser,
} from './services/api.js'

const savedUserKey = 'finapp.userId'

function App() {
  const [savedUserId, setSavedUserId] = useState(() => localStorage.getItem(savedUserKey))
  const [connection, setConnection] = useState('checking')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
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
    } catch (requestError) {
      if (requestError.response?.status === 404) {
        localStorage.removeItem(savedUserKey)
        setSavedUserId(null)
        setUser(null)
        setProfile(null)
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
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = user ? await updateUser(user.id, values) : await createUser(values)
      if (!user) {
        localStorage.setItem(savedUserKey, String(saved.id))
        setSavedUserId(String(saved.id))
      }
      setUser(saved)
      setMessage(user ? 'User details updated.' : 'User created. Now save a financial profile.')
    } catch (requestError) {
      setError(explainApiError(requestError))
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveProfile(values) {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await saveFinancialProfile(user.id, values)
      setProfile(saved)
      setMessage('Financial profile saved.')
    } catch (requestError) {
      setError(explainApiError(requestError))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:py-16">
      <div className="mx-auto max-w-3xl">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">FinApp</h1>
          <p className="mt-2 text-slate-600">Build your financial starting point. Analysis and recommendations come in later issues.</p>
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
                <p className="mt-1 text-slate-600">{user.email} · Monthly income: {user.monthly_income}</p>
                <p className="mt-2 text-slate-500">This browser remembers user #{user.id} for reloads. Login is not implemented yet.</p>
              </div>
              <details className="mb-8 rounded-lg border border-slate-200 p-4">
                <summary className="cursor-pointer text-sm font-medium">Edit user details</summary>
                <div className="mt-5"><UserForm user={user} onSave={handleSaveUser} saving={saving} /></div>
              </details>
              <FinancialProfileForm profile={profile} onSave={handleSaveProfile} saving={saving} />
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
