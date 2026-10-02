import { useEffect, useRef, useState } from 'react'
import { explainApiError, getFinancialDetails, previewEventScenario } from '../services/api.js'
import { formatAmount } from '../utils/format.js'

const choices = [
  ['income_decrease', 'Income decrease'],
  ['income_increase', 'Income increase'],
  ['unexpected_expense', 'Unexpected expense'],
  ['upcoming_expense', 'Upcoming expense'],
  ['subscription_reduction', 'Subscription reduction'],
  ['additional_loan_payment', 'Extra loan payment'],
  ['additional_savings', 'Add emergency savings'],
  ['goal_contribution_change', 'Change goal contribution'],
]
const oneTimeExpense = new Set(['unexpected_expense', 'upcoming_expense'])

export function buildEventPayload(values) {
  const event = { kind: values.kind, amount: values.amount }
  if (oneTimeExpense.has(values.kind)) {
    event.reserved_amount = values.reserved_amount === '' ? '0' : values.reserved_amount
    if (values.name.trim()) event.name = values.name.trim()
    if (values.is_essential) event.is_essential = true
  }
  if (values.kind === 'upcoming_expense') event.due_date = values.due_date
  if (values.kind === 'subscription_reduction') event.expense_id = Number(values.expense_id)
  if (values.kind === 'additional_loan_payment') event.loan_id = Number(values.loan_id)
  if (values.kind === 'goal_contribution_change') event.goal_id = Number(values.goal_id)
  return event
}

function money(fact) {
  return fact?.value == null ? 'Unknown' : formatAmount(fact.value)
}

export function EventComparison({ result }) {
  const { before, after } = result
  const rows = [
    ['Gross monthly income', before.income.expected_monthly, after.income.expected_monthly],
    ['Recurring monthly expenses', before.spending.monthly_total, after.spending.monthly_total],
    ['Gross monthly cash flow', before.spending.gross_cash_flow, after.spending.gross_cash_flow],
    ['Possible surplus ceiling', before.spending.available_surplus_upper_bound, after.spending.available_surplus_upper_bound],
    ['Emergency reserve gap', before.reserve.funding_gap, after.reserve.funding_gap],
    ['One-time costs due in 90 days', before.planned_due_90_days, after.planned_due_90_days],
    ['Unreserved costs due in 90 days', before.unreserved_due_90_days, after.unreserved_due_90_days],
    ['Monthly savings budget', before.spending.entered_savings_capacity, after.spending.entered_savings_capacity],
  ]
  return <div className="mt-5 space-y-4" aria-live="polite">
    <div className="rounded-xl border border-teal-200 bg-teal-50 p-4">
      <h4 className="font-semibold">What changes in this preview</h4>
      <p className="mt-1 text-sm text-slate-700">One event is applied to your saved financial picture. No saved value or plan is changed.</p>
      {Number(result.one_time_cash_need) > 0 && <p className="mt-2 text-sm">One-time cash needed beyond the entered reserved amount: <strong>{formatAmount(result.one_time_cash_need)}</strong>.</p>}
      {result.illustrative_current_month_cash_after_event != null &&
        <p className="mt-1 text-sm">Illustrative gross cash after this month's one-time amount: <strong>{formatAmount(result.illustrative_current_month_cash_after_event)}</strong>.</p>}
      {result.event.kind === 'upcoming_expense' && <p className="mt-1 text-sm">The new cost is due {result.event.due_date}; it is not added to recurring monthly expenses.{result.event.is_essential ? ' You marked it essential.' : ''}</p>}
      {result.loan_effect && <p className="mt-1 text-sm">Selected loan balance: {formatAmount(result.loan_effect.balance_before)} → {formatAmount(result.loan_effect.balance_after)}. The regular payment stays the same.</p>}
      {result.goal_effect && <div className="mt-2 space-y-1 text-sm">
        <p>Current plan suggestion for this goal: {money({ value: result.goal_effect.current_plan_allocation })}. Your hypothetical monthly contribution: {formatAmount(result.goal_effect.hypothetical_contribution)}.</p>
        <p>Monthly gap to its target: {money({ value: result.goal_effect.current_plan_gap })} under the current plan → {money({ value: result.goal_effect.hypothetical_gap })} with your hypothetical contribution.</p>
        {Number(result.goal_effect.budget_shortfall) > 0 && <p className="font-medium text-amber-900">This contribution exceeds the saved total monthly savings budget by {formatAmount(result.goal_effect.budget_shortfall)}.</p>}
      </div>}
    </div>
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
        <thead className="bg-slate-50"><tr><th scope="col" className="p-3">Financial check</th><th scope="col" className="p-3">Saved picture</th><th scope="col" className="p-3">With this event</th></tr></thead>
        <tbody>{rows.map(([label, oldFact, newFact]) => <tr key={label} className="border-t border-slate-200">
          <th scope="row" className="p-3 font-medium">{label}</th><td className="p-3">{money(oldFact)}</td><td className="p-3">{money(newFact)}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
  </div>
}

export default function EventScenario({ user, goals = [], disabled = false }) {
  const [values, setValues] = useState({
    kind: 'income_decrease', amount: '', expense_id: '', loan_id: '', goal_id: '',
    due_date: '', reserved_amount: '0', name: '', is_essential: false,
  })
  const [details, setDetails] = useState({ recurring_expenses: [], loans: [] })
  const [detailsError, setDetailsError] = useState('')
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const requestId = useRef(0)

  useEffect(() => {
    let alive = true
    getFinancialDetails(user.id).then((saved) => { if (alive) setDetails(saved) })
      .catch((failure) => { if (alive) setDetailsError(explainApiError(failure)) })
    return () => { alive = false }
  }, [user.id])

  function update(name, value) {
    requestId.current += 1
    setValues((current) => ({ ...current, [name]: value }))
    setPreview(null); setError(''); setPending(false)
  }

  async function submit(event) {
    event.preventDefault()
    const currentRequest = ++requestId.current
    setPending(true); setError(''); setPreview(null)
    try {
      const result = await previewEventScenario(user.id, buildEventPayload(values))
      if (currentRequest === requestId.current) setPreview(result)
    } catch (failure) {
      if (currentRequest === requestId.current) setError(explainApiError(failure))
    } finally {
      if (currentRequest === requestId.current) setPending(false)
    }
  }

  const subscriptions = details.recurring_expenses.filter((item) => item.category === 'discretionary')
  const knownLoans = details.loans.filter((item) => item.remaining_balance != null)
  const activeGoals = goals.filter((item) => !item.archived)
  const needsTarget = values.kind === 'subscription_reduction' || values.kind === 'additional_loan_payment' || values.kind === 'goal_contribution_change'
  const targetOptions = values.kind === 'subscription_reduction' ? subscriptions : values.kind === 'additional_loan_payment' ? knownLoans : activeGoals
  const targetName = values.kind === 'subscription_reduction' ? 'Saved discretionary expense' : values.kind === 'additional_loan_payment' ? 'Saved loan' : 'Active goal'
  const targetKey = values.kind === 'subscription_reduction' ? 'expense_id' : values.kind === 'additional_loan_payment' ? 'loan_id' : 'goal_id'
  const amountLabel = values.kind === 'goal_contribution_change' ? 'Monthly contribution to this goal'
    : values.kind === 'subscription_reduction' ? 'Monthly reduction'
      : values.kind === 'additional_savings' ? 'New cash to add to emergency savings'
        : values.kind === 'additional_loan_payment' ? 'Extra one-time payment' : 'Event amount'
  const targetMissing = needsTarget && targetOptions.length === 0
  return <section aria-labelledby="event-scenario-heading" className="border-t border-slate-200 pt-7">
    <h3 id="event-scenario-heading" className="text-xl font-semibold">Try a specific financial change</h3>
    <p className="mt-2 text-sm text-slate-600">Preview one event at a time. This does not change saved information or move money.</p>
    <form onSubmit={submit} className="mt-4 space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">What changes?
          <select name="kind" value={values.kind} onChange={(event) => update('kind', event.target.value)} disabled={disabled || pending}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base">
            {choices.map(([kind, label]) => <option key={kind} value={kind}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{amountLabel}
          <input name="amount" type="number" min={values.kind === 'goal_contribution_change' ? '0' : '0.01'} step="0.01" required
            value={values.amount} onChange={(event) => update('amount', event.target.value)} disabled={disabled || pending}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base" />
        </label>
      </div>
      {needsTarget && <label className="block text-sm font-medium">{targetName}
        <select name={targetKey} value={values[targetKey]} onChange={(event) => update(targetKey, event.target.value)}
          disabled={disabled || pending || targetMissing} required
          className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base">
          <option value="">Choose one</option>
          {targetOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>}
      {targetMissing && <p className="text-sm text-slate-600">Add a matching {targetName.toLowerCase()} in Profile or Goals to preview this change.</p>}
      {detailsError && needsTarget && values.kind !== 'goal_contribution_change' && <p role="alert" className="text-sm text-rose-800">Saved detail could not load: {detailsError}</p>}
      {oneTimeExpense.has(values.kind) && <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Cost name (optional)
          <input name="name" value={values.name} maxLength="100" onChange={(event) => update('name', event.target.value)}
            disabled={disabled || pending} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base" />
        </label>
        <label className="text-sm font-medium">Already set aside
          <input name="reserved_amount" type="number" min="0" step="0.01" required value={values.reserved_amount}
            onChange={(event) => update('reserved_amount', event.target.value)} disabled={disabled || pending}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base" />
        </label>
      </div>}
      {oneTimeExpense.has(values.kind) && <label className="flex items-center gap-2 text-sm font-medium">
        <input name="is_essential" type="checkbox" checked={values.is_essential}
          onChange={(event) => update('is_essential', event.target.checked)} disabled={disabled || pending} />
        Essential cost that must be paid
      </label>}
      {values.kind === 'upcoming_expense' && <label className="block text-sm font-medium">Due date
        <input name="due_date" type="date" required value={values.due_date} onChange={(event) => update('due_date', event.target.value)}
          disabled={disabled || pending} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-base" />
      </label>}
      {values.kind === 'goal_contribution_change' && <p className="text-xs text-slate-600">Compare your proposed goal contribution with the current plan suggestion and saved total savings budget. Other allocations are not recalculated.</p>}
      <button type="submit" disabled={disabled || pending || targetMissing}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
        {pending ? 'Calculating…' : 'Preview this event'}
      </button>
    </form>
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {preview && <EventComparison result={preview} />}
  </section>
}
