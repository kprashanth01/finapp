import { useEffect, useState } from 'react'
import { getHealth } from './services/api.js'

function App() {
  const [connection, setConnection] = useState('checking')

  async function checkConnection(signal) {
    setConnection('checking')
    try {
      const health = await getHealth(signal)
      setConnection(health.status === 'ok' ? 'connected' : 'unavailable')
    } catch (error) {
      if (error.name !== 'CanceledError') {
        setConnection('unavailable')
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    checkConnection(controller.signal)
    return () => controller.abort()
  }, [])

  const isConnected = connection === 'connected'
  const statusText = {
    checking: 'Checking API connection…',
    connected: 'API connected',
    unavailable: 'API unavailable',
  }[connection]

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12 text-slate-900">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
        <h1 className="text-3xl font-semibold tracking-tight">FinApp</h1>
        <p className="mt-3 text-base leading-7 text-slate-600">
          Financial advisory research prototype. This first step checks that the frontend can reach the API.
        </p>

        <div className="mt-8 flex items-center gap-3" role="status" aria-live="polite">
          <span
            className={`h-3 w-3 shrink-0 rounded-full ${isConnected ? 'bg-emerald-500' : connection === 'checking' ? 'bg-amber-400' : 'bg-rose-500'}`}
            aria-hidden="true"
          />
          <span className="font-medium">{statusText}</span>
        </div>

        <button
          type="button"
          onClick={() => checkConnection()}
          disabled={connection === 'checking'}
          className="mt-8 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-wait disabled:bg-slate-400"
        >
          Retry connection
        </button>
      </section>
    </main>
  )
}

export default App
