import { staleMessage } from '../utils/format.js'
import { useEffect, useRef, useState } from 'react'
import { explainApiError, getAdvisorySessionHistory } from '../services/api.js'

function AdvisoryHistory({ userId, refreshKey, selectedId, onSelect }) {
  const [items, setItems] = useState([])
  const [nextBeforeId, setNextBeforeId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [errorKind, setErrorKind] = useState('initial')
  const [retryKey, setRetryKey] = useState(0)
  const generation = useRef(0)

  useEffect(() => {
    const current = ++generation.current
    setLoading(true)
    setLoadingMore(false)
    setItems([])
    setNextBeforeId(null)
    setError('')
    getAdvisorySessionHistory(userId, { limit: 10 })
      .then((page) => {
        if (current !== generation.current) return
        setItems(page.items)
        setNextBeforeId(page.next_before_id)
      })
      .catch((requestError) => {
        if (current === generation.current) {
          setErrorKind('initial')
          setError(explainApiError(requestError))
        }
      })
      .finally(() => {
        if (current === generation.current) setLoading(false)
      })
    return () => { generation.current += 1 }
  }, [userId, refreshKey, retryKey])

  async function loadMore() {
    if (nextBeforeId == null || loading || loadingMore) return
    const current = generation.current
    setLoadingMore(true)
    setError('')
    try {
      const page = await getAdvisorySessionHistory(userId, { limit: 10, beforeId: nextBeforeId })
      if (current !== generation.current) return
      setItems((existing) => {
        const known = new Set(existing.map((item) => item.id))
        return [...existing, ...page.items.filter((item) => !known.has(item.id))]
      })
      setNextBeforeId(page.next_before_id)
    } catch (requestError) {
      if (current === generation.current) {
        setErrorKind('more')
        setError(explainApiError(requestError))
      }
    } finally {
      if (current === generation.current) setLoadingMore(false)
    }
  }

  return (
    <section className="mt-8 border-t border-slate-200 pt-7" aria-labelledby="history-heading">
      <h2 id="history-heading" className="text-xl font-semibold">Saved analysis history</h2>
      <p className="mt-1 text-sm text-slate-600">Open a past run to see the inputs and findings recorded at that time.</p>
      {loading && <p className="mt-4 text-sm text-slate-600">Loading saved runs…</p>}
      {error && (
        <div role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
          <p>History could not load: {error}</p>
          <button type="button" onClick={() => errorKind === 'more' ? loadMore() : setRetryKey((value) => value + 1)} className="mt-2 font-medium underline underline-offset-4">Retry history</button>
        </div>
      )}
      {!loading && items.length === 0 && !error && <p className="mt-4 text-sm text-slate-600">No advisory runs saved yet.</p>}
      {items.length > 0 && (
        <ol className="mt-4 space-y-3">
          {items.map((item) => (
            <li key={item.id} className={`rounded-lg border p-4 ${selectedId === item.id ? 'border-slate-700 bg-slate-50' : 'border-slate-200'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{new Date(item.created_at).toLocaleString()}</p>
                  <p className="mt-1 text-xs text-slate-600">{item.method === 'rule_based' ? 'Rule based' : item.method}</p>
                </div>
                <button type="button" onClick={() => onSelect(item.id)} className="text-sm font-medium text-slate-800 underline underline-offset-4">Open run</button>
              </div>
              {item.is_stale && <p className="mt-2 text-xs font-medium text-amber-800">{staleMessage(item)}</p>}
              {item.priority_count > 0 ? (
                <p className="mt-2 text-sm text-slate-700">{item.priority_titles.join(' · ')}</p>
              ) : <p className="mt-2 text-sm text-slate-600">No priority findings</p>}
            </li>
          ))}
        </ol>
      )}
      {nextBeforeId != null && !loading && (
        <button type="button" onClick={loadMore} disabled={loadingMore} className="mt-4 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
          {loadingMore ? 'Loading…' : 'Load more'}
        </button>
      )}
    </section>
  )
}

export default AdvisoryHistory
