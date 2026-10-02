import { useRef, useState } from 'react'
import AdvisoryPlan from './AdvisoryPlan.jsx'
import { explainApiError, previewRecordedMonthPlan } from '../services/api.js'
import { estimateMonthContribution, monthSavingsLimit, summarizeMonths, unpaidObligations } from '../services/monthlyPlanning.js'
import { formatAmount } from '../utils/format.js'

const monthLabel = (period) => new Date(`${period}T12:00:00`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

export default function RecordedMonthPlan({ months, userId, onOpenProfile, onOpenGoal }) {
  const [period, setPeriod] = useState(months.at(-1).period)
  const [contribution, setContribution] = useState('')
  const [unrecordedCosts, setUnrecordedCosts] = useState('')
  const [heldCash, setHeldCash] = useState('')
  const [estimateApplied, setEstimateApplied] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const requestId = useRef(0)
  const selected = months.find((month) => month.period === period) ?? months.at(-1)
  const history = summarizeMonths(months, null)
  const bufferCents = history.sampleCount > 1 ? history.lowIncomeObligationGapCents : 0
  const shortfall = Math.max(0, Math.round((Number(selected.monthly_expenses) - Number(selected.monthly_income)) * 100))
  const limit = monthSavingsLimit(selected)
  const estimate = estimateMonthContribution(selected, unrecordedCosts, heldCash)
  const contributionCents = Math.round(Number(contribution || 0) * 100)
  const tooHigh = contribution !== '' && contributionCents > limit
  const aboveEstimate = contribution !== '' && estimate !== null && contributionCents > estimate.possibleCents
  const unpaid = unpaidObligations(selected)
  const blockedContribution = unpaid && contribution !== '' && contributionCents > 0

  function changePeriod(value) {
    requestId.current += 1
    setPeriod(value); setContribution(''); setUnrecordedCosts(''); setHeldCash(''); setEstimateApplied(false)
    setPreview(null); setError(''); setPending(false)
  }

  function changeContribution(value) {
    requestId.current += 1
    setContribution(value); setEstimateApplied(false); setPreview(null); setError(''); setPending(false)
  }

  function changeWorksheet(field, value) {
    requestId.current += 1
    if (field === 'unrecordedCosts') setUnrecordedCosts(value)
    else setHeldCash(value)
    if (estimateApplied) { setContribution(''); setEstimateApplied(false) }
    setPreview(null); setError(''); setPending(false)
  }

  function useEstimate() {
    if (estimate === null) return
    requestId.current += 1
    setContribution(((unpaid ? 0 : estimate.possibleCents) / 100).toFixed(2))
    setEstimateApplied(true); setPreview(null); setError(''); setPending(false)
  }

  function useLowIncomeBuffer() {
    if (bufferCents <= 0) return
    changeWorksheet('heldCash', (bufferCents / 100).toFixed(2))
  }

  async function submit(event) {
    event.preventDefault()
    if (pending || tooHigh || aboveEstimate || blockedContribution) return
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
    <p className="mt-2 text-sm text-slate-700">Choose a month, work out an amount you could set aside, then preview how the existing plan would prioritize it. The preview uses that month's recorded income, expenses, balances and risk settings with your current saved goals. It does not change your Profile or saved Advisor plan.</p>
    <label className="mt-4 block text-sm font-medium text-slate-800">Month to plan from
      <select value={period} onChange={(event) => changePeriod(event.target.value)} disabled={pending}
        className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base">
        {months.map((month) => <option key={month.period} value={month.period}>{monthLabel(month.period)}</option>)}
      </select>
    </label>
    <section className="mt-4 rounded-lg border border-teal-200 bg-white p-4" aria-labelledby="month-amount-heading">
      <h5 id="month-amount-heading" className="font-semibold text-teal-950">Work out an amount to plan with</h5>
      <p className="mt-2 text-sm text-slate-700">Calculated from your recorded figures: {monthLabel(selected.period)} leaves at most <strong>{formatAmount(limit / 100)}</strong> of income after entered spending. This is a ceiling, not a savings recommendation.</p>
      {history.sampleCount > 1 && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-slate-800">
        <p className="font-semibold">Check a low-income month buffer</p>
        {bufferCents > 0 ? <>
          <p className="mt-1">Your lowest recorded income was {formatAmount(history.lowest.monthly_income)} in {monthLabel(history.lowest.period)}. If that income recurred while your latest essential bills and scheduled loan payment stayed at {formatAmount(history.latestObligationsCents / 100)}, you would need <strong>{formatAmount(bufferCents / 100)}</strong> to cover the gap for one month.</p>
          <p className="mt-1">If you have not already set aside a buffer, you can keep this amount out of the selected month's plan. This replaces the cash-to-keep entry below; you can adjust it afterwards. It does not change your saved balance or move money.</p>
          {bufferCents > limit && <p className="mt-1 font-medium text-amber-900">This selected month's recorded remainder is smaller than that gap. Keeping the full amount would leave no new money to allocate from this month.</p>}
          <button type="button" onClick={useLowIncomeBuffer} disabled={pending}
            className="mt-2 rounded-lg border border-amber-700 px-3 py-2 font-semibold text-amber-900 disabled:opacity-50">Keep {formatAmount(bufferCents / 100)} unallocated</button>
          {heldCash === (bufferCents / 100).toFixed(2) && <p role="status" className="mt-2">The buffer is entered below. Add any missing costs (enter 0 if none) to see what remains for a plan.</p>}
        </> : <p className="mt-1">The lowest recorded income covers the latest essential bills and scheduled loan payment, so this check found no positive one-month gap. You can still enter cash to keep for other uncertainties below.</p>}
        <p className="mt-1 text-xs text-slate-600">Based on up to 12 entered months, not a forecast. Taxes, payment timing and unrecorded costs may change what you need.</p>
      </div>}
      <p className="mt-2 text-sm text-slate-700">Enter costs missing from recorded spending and cash you want to keep unallocated. Enter 0 if none. These are your assumptions for this preview and are not saved.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-800">Costs not included in recorded spending
          <input type="number" min="0" step="0.01" inputMode="decimal" value={unrecordedCosts} disabled={pending}
            onChange={(event) => changeWorksheet('unrecordedCosts', event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base" />
          <small className="font-normal text-slate-600">For example, taxes or bills omitted from that month's total.</small>
        </label>
        <label className="text-sm font-medium text-slate-800">Keep unallocated from this remainder
          <input type="number" min="0" step="0.01" inputMode="decimal" value={heldCash} disabled={pending}
            onChange={(event) => changeWorksheet('heldCash', event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base" />
          <small className="font-normal text-slate-600">Money you want to leave available for near-term uncertainty.</small>
        </label>
      </div>
      {estimate === null ? <p className="mt-3 text-sm text-slate-700">Enter both amounts, including 0 where appropriate, to see what remains. You can still enter a plan amount directly below.</p>
        : <div className="mt-3 text-sm text-slate-700">
          <p>Based on your entries, <strong>{formatAmount(estimate.possibleCents / 100)}</strong> remains as a maximum for this hypothetical plan.</p>
          {estimate.overByCents > 0 && <p role="status" className="mt-2 text-amber-900">The costs and cash you want to keep exceed the recorded remainder by {formatAmount(estimate.overByCents / 100)}. Preview priorities without a new funded allocation.</p>}
          {unpaid && <p role="status" className="mt-2 text-amber-900">This month has an unpaid {unpaid === 'loan' ? 'loan payment' : 'bill'}. Review it before using a positive plan amount.</p>}
          <button type="button" onClick={useEstimate} disabled={pending} className="mt-3 rounded-lg border border-teal-700 px-3 py-2 font-semibold text-teal-800 disabled:opacity-50">
            {estimate.possibleCents === 0 || unpaid ? 'Use 0 for priorities only' : `Use ${formatAmount(estimate.possibleCents / 100)} in plan preview`}
          </button>
        </div>}
    </section>
    <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium text-slate-800">Amount you can actually set aside (optional)
        <input type="number" min="0" step="0.01" value={contribution} onChange={(event) => changeContribution(event.target.value)} disabled={pending}
          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base" />
      </label>
      <p className="sm:col-span-2 text-sm text-slate-700">Use the worksheet amount or enter your own amount. If you filled the worksheet, keep your amount within its result. Leave this blank to see priorities without a funded allocation. The plan is hypothetical and does not move money.</p>
      {shortfall > 0 && <p role="status" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Entered spending exceeded income by {formatAmount(shortfall / 100)} in this month. There is no room in these figures for a new savings contribution.</p>}
      {tooHigh && <p role="alert" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">The amount to set aside cannot exceed this month's income minus expenses. Enter {formatAmount(limit / 100)} or less, or leave it blank.</p>}
      {aboveEstimate && !tooHigh && <p role="alert" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Your plan amount exceeds what remains after the costs and cash to keep that you entered above. Lower the amount or clear the worksheet.</p>}
      {unpaid && <p role="alert" className="sm:col-span-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This month records {unpaid === 'loan' ? 'a loan payment that was not fully made' : 'bills that could not be funded'}. Review that obligation before assigning new savings. Leave the amount blank or enter zero to preview priorities without a funded allocation.</p>}
      <button type="submit" disabled={pending || tooHigh || aboveEstimate || blockedContribution} className="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{pending ? 'Calculating…' : 'Preview coordinated plan'}</button>
    </form>
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {preview && <div className="mt-6 border-t border-teal-200 pt-5" aria-live="polite">
      <p className="text-sm font-semibold text-teal-950">If your {monthLabel(preview.source_period)} figures applied now</p>
      <p className="mt-1 text-xs text-slate-600">This read-only plan uses the recorded scheduled loan payment, not any missed payment. It uses current goals and the project's standard reserve rule. It does not forecast future income or move money.</p>
      <div className="mt-5 rounded-xl bg-white p-4"><AdvisoryPlan result={preview.result} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} showExplanation={false} /></div>
    </div>}
  </section>
}
