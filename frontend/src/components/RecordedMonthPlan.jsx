import { useRef, useState } from 'react'
import AdvisoryPlan from './AdvisoryPlan.jsx'
import { explainApiError, previewRecordedMonthPlan } from '../services/api.js'
import { monthSavingsLimit, unpaidObligations } from '../services/monthlyPlanning.js'
import { formatAmount } from '../utils/format.js'

const monthLabel = (period) => new Date(`${period}T12:00:00`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

export default function RecordedMonthPlan({ months, userId, onOpenProfile, onOpenGoal }) {
  const [period, setPeriod] = useState(months.at(-1).period)
  const [contribution, setContribution] = useState('')
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const requestId = useRef(0)
  const selected = months.find((month) => month.period === period) ?? months.at(-1)
  const shortfall = Math.max(0, Math.round((Number(selected.monthly_expenses) - Number(selected.monthly_income)) * 100))
  const limit = monthSavingsLimit(selected)
  const tooHigh = contribution !== '' && Number(contribution) * 100 > limit
  const unpaid = unpaidObligations(selected)
  const blockedContribution = unpaid && contribution !== '' && Number(contribution) > 0

  function changePeriod(value) {
    requestId.current += 1
    setPeriod(value); setContribution(''); setPreview(null); setError(''); setPending(false)
  }

  function changeContribution(value) {
    requestId.current += 1
    setContribution(value); setPreview(null); setError(''); setPending(false)
  }

  async function submit(event) {
    event.preventDefault()
    if (pending || tooHigh || blockedContribution) return
    const currentRequest = ++requestId.current
    setPending(true); setPreview(null); setError('')
    try {
      const result = await previewRecordedMonthPlan(userId, selected.period,
        contribution === '' ? null : contribution)
      if (currentRequest === requestId.current) setPreview(result)
    } catch (requestError) {
      if (currentRequest === requestId.current) setError(explainApiError(requestError))
    } finally {
      if (currentRequest === requestId.current) setPending(false)
    }
  }

  return <section className="mt-8 rounded-xl border border-teal-200 bg-teal-50 p-5" aria-labelledby="recorded-month-plan-heading">
    <h4 id="recorded-month-plan-heading">Preview a plan for a recorded month</h4>
    <p className="mt-2 text-sm text-slate-700">Choose a month, then enter the amount you believe you can actually set aside. The preview uses that month's recorded income, expenses, balances and risk settings with your current saved goals. It does not change your Profile or saved Advisor plan.</p>
    <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium text-slate-800">Month to plan from
        <select value={period} onChange={(event) => changePeriod(event.target.value)} disabled={pending}
          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base">
          {months.map((month) => <option key={month.period} value={month.period}>{monthLabel(month.period)}</option>)}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-800">Amount you can actually set aside (optional)
        <input type="number" min="0" step="0.01" value={contribution} onChange={(event) => changeContribution(event.target.value)} disabled={pending}
          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base" />
      </label>
      <p className="sm:col-span-2 text-sm text-slate-700">{monthLabel(selected.period)} leaves at most <strong>{formatAmount(limit / 100)}</strong> of income after entered spending, before taxes and other unrecorded costs. This is a ceiling, not a savings recommendation. Leave the amount blank to see priorities without a funded allocation.</p>
      {shortfall > 0 && <p role="status" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Entered spending exceeded income by {formatAmount(shortfall / 100)} in this month. There is no room in these figures for a new savings contribution.</p>}
      {tooHigh && <p role="alert" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">The amount to set aside cannot exceed this month's income minus expenses. Enter {formatAmount(limit / 100)} or less, or leave it blank.</p>}
      {unpaid && <p role="alert" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This month records {unpaid === 'loan' ? 'a loan payment that was not fully made' : 'bills that could not be funded'}. Review that obligation before assigning new savings. Leave the amount blank or enter zero to preview priorities without a funded allocation.</p>}
      <button type="submit" disabled={pending || tooHigh || blockedContribution} className="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{pending ? 'Calculating…' : 'Preview coordinated plan'}</button>
    </form>
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {preview && <div className="mt-6 border-t border-teal-200 pt-5" aria-live="polite">
      <p className="text-sm font-semibold text-teal-950">If your {monthLabel(preview.source_period)} figures applied now</p>
      <p className="mt-1 text-xs text-slate-600">This read-only plan uses the recorded scheduled loan payment, not any missed payment. It uses current goals and the project's standard reserve rule. It does not forecast future income or move money.</p>
      <div className="mt-5 rounded-xl bg-white p-4"><AdvisoryPlan result={preview.result} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} showExplanation={false} /></div>
    </div>}
  </section>
}
