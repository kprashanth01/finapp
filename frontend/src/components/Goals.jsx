import { useEffect, useState } from 'react'
import GoalForm from './GoalForm.jsx'
import { explainApiError } from '../services/api.js'
import { formatAmount } from '../utils/format.js'

export default function Goals({ goals, loading, error, pending, disabled, onCreate, onUpdate, onArchive, onRetry,
  legacyNote, onClearLegacyNote, onRunAnalysis, onOpenProfile, hasProfile, focusGoalId }) {
  const [editing, setEditing] = useState(null)
  const [initialName, setInitialName] = useState('')
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [undo, setUndo] = useState(null)
  useEffect(() => {
    if (focusGoalId != null && !loading) {
      const goal = goals.find((g) => g.id === focusGoalId)
      if (goal) setEditing(goal)
      else setNotice('This goal is no longer available. The saved analysis still contains its earlier values.')
    }
  }, [focusGoalId, loading])
  const active = goals.filter((g) => !g.archived)
  const archived = goals.filter((g) => g.archived)
  const busy = pending || disabled || loading
  async function save(values) {
    const saved = editing?.id ? await onUpdate(editing.id, values) : await onCreate(values)
    if (saved) { setEditing(null); setInitialName(''); setNotice('Goal saved. Run analysis when you want an updated plan.') }
  }
  async function archive(goal, value) {
    setActionError('')
    try {
      const saved = await onArchive(goal.id,value)
      if (saved) { setUndo(value ? goal : null); setNotice(value ? 'Goal archived. It is excluded from new plans.' : 'Goal restored.') }
    } catch (e) { setActionError(explainApiError(e)) }
  }
  function card(g) {
    const remaining = Math.max(0,Number(g.target_amount)-Number(g.saved_amount))
    return <li key={g.id} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="break-words font-semibold">{g.name}</h3><span className="text-xs capitalize text-slate-600">{remaining === 0 ? 'Target reached' : `${g.priority} priority`} · {g.target_date}</span></div>
      <p className="mt-2 text-sm text-slate-600">Saved {formatAmount(g.saved_amount)} of {formatAmount(g.target_amount)} · Remaining {formatAmount(remaining)}</p>
      <div className="mt-3 flex gap-4 text-sm"><button disabled={busy} onClick={() => { setEditing(g); setNotice('') }} className="underline disabled:opacity-40">Edit {g.name}</button><button disabled={busy} onClick={() => archive(g,!g.archived)} className="underline disabled:opacity-40">{g.archived ? 'Restore' : 'Archive'} {g.name}</button></div>
    </li>
  }
  return <section aria-labelledby="goals-heading" className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="goals-heading" className="text-2xl font-semibold">Your goals</h2><p className="mt-1 text-sm text-slate-600">Set a target, track saved progress, and see what your monthly budget can cover.</p></div><button disabled={busy || !!error} onClick={() => { setEditing({}); setInitialName('') }} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40">Add goal</button></div>
    {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">{notice} {undo && <button disabled={busy} className="ml-2 underline" onClick={() => archive(undo,false)}>Undo archive</button>}</p>}
    {(error || actionError) && <div role="alert" className="text-sm text-rose-700">{error || actionError}{error && <button disabled={busy} className="ml-2 underline" onClick={onRetry}>Retry goals</button>}</div>}
    {loading && <p role="status">Loading goals…</p>}
    {editing && <GoalForm key={editing.id ?? initialName} goal={editing.id ? editing : null} initialName={initialName} pending={busy} onSave={save} onCancel={() => setEditing(null)} />}
    {!loading && !error && active.length === 0 && <p className="rounded-lg bg-slate-50 p-5 text-sm text-slate-600">No active goals yet. Add a target to begin; your plan will use the monthly savings contribution in Profile.</p>}
    <ul className="space-y-3">{active.map(card)}</ul>
    {archived.length > 0 && <details className="rounded-lg border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-medium">Archived goals ({archived.length})</summary><ul className="mt-3 space-y-3">{archived.map(card)}</ul></details>}
    {legacyNote && <details className="rounded-lg border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-medium">Earlier goal note</summary><p className="mt-3 whitespace-pre-wrap break-words text-sm">{legacyNote}</p><p className="mt-2 text-xs text-slate-500">This note is preserved; it is not a funded goal.</p><div className="mt-3 flex gap-4 text-sm"><button disabled={busy} className="underline" onClick={() => { setInitialName(legacyNote); setEditing({}) }}>Use note as a goal name</button><button disabled={busy} className="underline" onClick={onClearLegacyNote}>Clear earlier note</button></div></details>}
    <button disabled={busy || loading || !!error} onClick={hasProfile ? onRunAnalysis : onOpenProfile} className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm text-white disabled:opacity-40">{hasProfile ? 'Run analysis with saved goals' : 'Complete financial profile'}</button>
  </section>
}
