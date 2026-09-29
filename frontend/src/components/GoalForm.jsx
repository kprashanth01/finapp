import { useState } from 'react'
import { explainApiError } from '../services/api.js'

const input = 'mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:ring-2 focus:ring-slate-300'

export default function GoalForm({ goal, initialName = '', pending, onSave, onCancel }) {
  const [fields, setFields] = useState({ name: goal?.name ?? initialName, target_amount: goal?.target_amount ?? '',
    saved_amount: goal?.saved_amount ?? '0', target_date: goal?.target_date ?? '', priority: goal?.priority ?? 'medium' })
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const change = (e) => setFields((old) => ({ ...old, [e.target.name]: e.target.value }))
  async function submit(e) {
    e.preventDefault()
    setError(''); setFieldErrors({})
    if (!fields.name.trim() || fields.name.trim().length > 100) {
      setError('Use a goal name between 1 and 100 characters. Your original note has been kept.'); return
    }
    try { await onSave({ ...fields, name: fields.name.trim() }) } catch (requestError) {
      const detail = requestError.response?.data?.detail
      if (Array.isArray(detail)) setFieldErrors(Object.fromEntries(detail.map((item) => [item.loc.at(-1), item.msg])))
      setError(explainApiError(requestError))
    }
  }
  return <form onSubmit={submit} className="rounded-xl border border-slate-300 bg-slate-50 p-5">
    <h3 className="text-lg font-semibold">{goal ? `Edit ${goal.name}` : 'New goal'}</h3>
    <fieldset disabled={pending} className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium sm:col-span-2">Goal name
        <input name="name" className={input} value={fields.name} onChange={change} required autoFocus aria-invalid={!!fieldErrors.name} />
        {fields.name.length > 100 && <span className="text-rose-700">Shorten this name to 100 characters. The earlier note is preserved.</span>}
      </label>
      {[['Target amount', 'target_amount', '0.01'], ['Already saved for this goal', 'saved_amount', '0']].map(([label,name,min]) =>
        <label key={name} className="text-sm font-medium">{label}
          <input name={name} className={input} type="number" min={min} max="9999999999.99" step="0.01" required value={fields[name]} onChange={change} aria-invalid={!!fieldErrors[name]} aria-describedby={name === 'saved_amount' ? 'goal-earmark-help' : undefined} />
          {name === 'saved_amount' && <span id="goal-earmark-help" className="mt-2 block text-xs font-normal text-slate-600">Record money earmarked only for this goal. Exclude your emergency reserve and money already assigned to another goal. The app cannot verify whether these amounts overlap.</span>}
        </label>)}
      <label className="text-sm font-medium">Target date<input name="target_date" className={input} type="date" required value={fields.target_date} onChange={change} aria-invalid={!!fieldErrors.target_date} /></label>
      <label className="text-sm font-medium">Priority<select name="priority" className={input} value={fields.priority} onChange={change}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
      <p className="text-xs text-slate-600 sm:col-span-2">Saving a goal does not move money or change your savings balance.</p>
      {error && <p role="alert" className="text-sm text-rose-700 sm:col-span-2">{error}</p>}
      <div className="flex gap-4 sm:col-span-2"><button className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white" type="submit">{pending ? 'Saving…' : 'Save goal'}</button><button type="button" onClick={onCancel} className="text-sm underline">Cancel</button></div>
    </fieldset>
  </form>
}
