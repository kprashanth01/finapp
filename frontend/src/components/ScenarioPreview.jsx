import { useRef, useState } from 'react'
import { explainApiError, previewAdvisoryScenario } from '../services/api.js'
import { formatAmount } from '../utils/format.js'

function grossRemainder(state) {
  return Number(state.monthly_income) - Number(state.monthly_expenses)
}

function firstPriority(result) {
  return result.advice.priority_actions[0]?.title ?? result.advice.summary.title
}

function planAmount(plan, key) {
  return plan.capacity == null ? 'Not calculated' : formatAmount(plan[key])
}

export function ScenarioComparison({ preview }) {
  const { baseline, scenario } = preview
  const current = baseline.advice.monthly_plan
  const changed = scenario.advice.monthly_plan
  const goals = current.goal_allocations.map((allocation) => ({
    id: allocation.requirement.goal.id,
    name: allocation.requirement.goal.name,
    current: allocation,
    changed: changed.goal_allocations.find((item) => item.requirement.goal.id === allocation.requirement.goal.id),
  }))
  const rows = [
    ['Gross monthly income', formatAmount(baseline.state.monthly_income), formatAmount(scenario.state.monthly_income)],
    ['Monthly expenses', formatAmount(baseline.state.monthly_expenses), formatAmount(scenario.state.monthly_expenses)],
    ['Gross income less expenses', formatAmount(grossRemainder(baseline.state)), formatAmount(grossRemainder(scenario.state))],
    ['First priority', firstPriority(baseline), firstPriority(scenario)],
    ['Emergency expense coverage', baseline.state.emergency_fund_months == null ? 'Unavailable' : `${baseline.state.emergency_fund_months} months`,
      scenario.state.emergency_fund_months == null ? 'Unavailable' : `${scenario.state.emergency_fund_months} months`],
    ['Planned monthly savings', planAmount(current, 'capacity'), planAmount(changed, 'capacity')],
    ['Emergency reserve', planAmount(current, 'emergency_allocation'), planAmount(changed, 'emergency_allocation')],
    ...goals.flatMap((goal) => [
      [goal.name, goal.current.allocated_monthly == null ? 'Not calculated' : formatAmount(goal.current.allocated_monthly),
        goal.changed?.allocated_monthly == null ? 'Not calculated' : formatAmount(goal.changed.allocated_monthly)],
      [`${goal.name} monthly shortfall`, goal.current.funding_gap == null ? 'Not calculated' : formatAmount(goal.current.funding_gap),
        goal.changed?.funding_gap == null ? 'Not calculated' : formatAmount(goal.changed.funding_gap)],
    ]),
    ['Unassigned for review', planAmount(current, 'unassigned'), planAmount(changed, 'unassigned')],
  ]

  return <div className="mt-5 space-y-3" aria-live="polite">
    <h4 className="font-semibold">How the monthly plan changes</h4>
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full min-w-[35rem] border-collapse text-left text-sm">
        <thead className="bg-slate-50"><tr><th scope="col" className="p-3">Financial check</th><th scope="col" className="p-3">Current saved inputs</th><th scope="col" className="p-3">Hypothetical month</th></tr></thead>
        <tbody>{rows.map(([label, before, after], index) => <tr key={`${label}-${index}`} className="border-t border-slate-200"><th scope="row" className="p-3 font-medium">{label}</th><td className="p-3">{before}</td><td className="p-3">{after}</td></tr>)}</tbody>
      </table>
    </div>
    {grossRemainder(scenario.state) < 0 && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
      In this hypothetical month, expenses exceed gross income by {formatAmount(-grossRemainder(scenario.state))}. Review spending or income before relying on a savings allocation.
    </p>}
    {changed.hold_reason && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Scenario plan: {changed.hold_reason}</p>}
    <p className="text-xs text-slate-600">Gross income less expenses is an upper bound, not take-home pay or confirmed savings. Allocations assume you can actually make the entered monthly savings contribution. No money is moved and this preview is not a forecast.</p>
  </div>
}

export default function ScenarioPreview({ user, profile, onOpenIncome, disabled = false }) {
  const [values, setValues] = useState({
    monthly_income: String(user.monthly_income),
    monthly_expenses: String(profile.monthly_expenses),
    monthly_savings_contribution: profile.monthly_savings_contribution == null ? '' : String(profile.monthly_savings_contribution),
  })
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const requestId = useRef(0)
  const hasSavedIncome = Number(user.monthly_income) > 0
  const grossSavingsCeiling = Math.max(0, Number(values.monthly_income) - Number(values.monthly_expenses))
  const contributionTooHigh = values.monthly_income !== '' && values.monthly_expenses !== '' &&
    values.monthly_savings_contribution !== '' && Number(values.monthly_savings_contribution) > grossSavingsCeiling

  function update(name, value) {
    requestId.current += 1
    setValues((current) => ({ ...current, [name]: value }))
    setPreview(null)
    setError('')
    setPending(false)
  }

  function lowerIncome() {
    update('monthly_income', (Number(user.monthly_income) * 0.8).toFixed(2))
  }

  async function submit(event) {
    event.preventDefault()
    const contribution = values.monthly_savings_contribution === '' ? null : values.monthly_savings_contribution
    if (contribution !== null && Number(contribution) > Math.max(0, Number(values.monthly_income) - Number(values.monthly_expenses))) {
      setPreview(null)
      setError('Reduce planned monthly savings or change income and expenses. The contribution cannot exceed gross income minus expenses.')
      return
    }
    const currentRequest = ++requestId.current
    setPending(true)
    setPreview(null)
    setError('')
    try {
      const result = await previewAdvisoryScenario(user.id, { ...values, monthly_savings_contribution: contribution })
      if (currentRequest === requestId.current) setPreview(result)
    } catch (requestError) {
      if (currentRequest === requestId.current) setError(explainApiError(requestError))
    } finally {
      if (currentRequest === requestId.current) setPending(false)
    }
  }

  return <section aria-labelledby="scenario-heading" className="border-t border-slate-200 pt-7">
    <h3 id="scenario-heading" className="text-xl font-semibold">What if my income or expenses change?</h3>
    <p className="mt-2 text-sm text-slate-600">Try one hypothetical month using your saved debts, reserve, and goals. This preview does not change your saved profile or plan.</p>
    <p className="mt-3 text-sm text-slate-700">Saved gross monthly income: <strong>{formatAmount(user.monthly_income)}</strong> (set under Profile → Edit user details).</p>
    {!hasSavedIncome && <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
      The 20% preset needs a positive saved income. {onOpenIncome && <button type="button" onClick={onOpenIncome} className="font-semibold underline">Update saved income</button>}
      {' '}If zero is correct for your current situation, enter a hypothetical income directly below instead.
    </p>}
    <button type="button" disabled={disabled || pending || !hasSavedIncome} onClick={lowerIncome} className="mt-3 text-sm font-medium text-slate-800 underline disabled:opacity-50">Try 20% less income</button>
    <form onSubmit={submit} className="mt-4 space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          ['monthly_income', 'Gross monthly income', 'Before tax, expected in this month.'],
          ['monthly_expenses', 'Monthly expenses (including debt payments)', 'Total you expect to pay in this month.'],
          ['monthly_savings_contribution', 'Planned monthly savings', 'Amount you expect to set aside from this month’s income.'],
        ].map(([name, label, help]) => <label key={name} className="text-sm font-medium text-slate-800">{label}
          <input name={name} type="number" min="0" step="0.01" required={name !== 'monthly_savings_contribution'} value={values[name]}
            onChange={(event) => update(name, event.target.value)} disabled={disabled || pending}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base disabled:bg-slate-100" />
          <span className="mt-1 block text-xs font-normal text-slate-600">{help}</span>
        </label>)}
      </div>
      <p className="text-xs text-slate-600">Enter the savings amount you believe you could actually set aside in this month. Leave it blank to see findings without a funded allocation.</p>
      {contributionTooHigh && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
        With these amounts, gross income minus expenses leaves at most {formatAmount(grossSavingsCeiling)} before tax. Reduce planned monthly savings, leave it blank, or change the other amounts to preview a funded plan.
      </p>}
      <button type="submit" disabled={disabled || pending || contributionTooHigh} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{pending ? 'Calculating…' : 'Preview changed plan'}</button>
    </form>
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {preview && <ScenarioComparison preview={preview} />}
  </section>
}
