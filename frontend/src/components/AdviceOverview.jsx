import { formatAmount } from '../utils/format.js'

function money(value) {
  return value == null ? 'Unknown' : formatAmount(value)
}

function daysFrom(asOfDate, dueDate) {
  if (!dueDate) return null
  const start = Date.parse(`${asOfDate}T00:00:00Z`)
  const due = Date.parse(`${dueDate}T00:00:00Z`)
  return Number.isNaN(start) || Number.isNaN(due) ? null : Math.round((due - start) / 86400000)
}

function dueLabel(item, asOfDate) {
  if (!item.due_date) return 'Payment date not entered'
  const days = daysFrom(asOfDate, item.due_date)
  if (days != null && days < 0) return `Overdue since ${item.due_date}`
  return `${item.kind === 'loan_payment' ? 'Next payment' : 'Due'} ${item.due_date}`
}

function Obligation({ item, asOfDate }) {
  const planned = item.kind === 'planned_expense'
  return <li className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="font-semibold text-slate-900">{item.name}</p><p className="mt-1 text-xs text-slate-600">{dueLabel(item, asOfDate)}</p></div>
      <p className="font-semibold text-slate-900">{money(item.amount)}</p>
    </div>
    <p className="mt-2 text-xs text-slate-600">{planned
      ? item.unreserved_amount == null ? 'Reserved amount unknown; check how much is set aside.'
        : `${formatAmount(item.unreserved_amount)} not marked reserved${item.is_essential ? ' · essential cost' : ''}.`
      : 'Recurring loan payment already included in monthly expenses.'}</p>
  </li>
}

function Goal({ goal, asOfDate, onOpenGoal }) {
  const days = daysFrom(asOfDate, goal.target_date)
  const overdue = days != null && days < 0
  return <li className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="font-semibold text-slate-900">{goal.name}</p>
        <p className="mt-1 text-xs text-slate-600">{overdue ? 'Target date passed' : 'Target'} {goal.target_date} · {goal.priority} priority</p></div>
      <p className="font-semibold text-slate-900">{money(goal.remaining_amount)} left</p>
    </div>
    <button type="button" onClick={() => onOpenGoal?.(goal.id)} className="mt-2 text-sm font-medium text-teal-900 underline">Review goal</button>
  </li>
}

export function MonthlySnapshot({ picture, onRetry, retrying = false }) {
  if (!picture) return <section aria-labelledby="snapshot-heading" className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
    <h3 id="snapshot-heading" className="text-xl font-semibold">Your month at a glance</h3>
    <p className="mt-2 text-sm text-slate-600">Current calculations are unavailable. Your saved profile still exists.</p>
    <button type="button" onClick={onRetry} disabled={retrying} className="mt-3 text-sm font-medium text-teal-900 underline disabled:opacity-50">{retrying ? 'Retrying calculations…' : 'Retry calculations'}</button>
  </section>

  const gross = picture.spending.gross_cash_flow.value
  const shortfall = gross != null && Number(gross) < 0
  const coverage = picture.reserve.total_expense_coverage_months.value
  const targetGap = picture.reserve.funding_gap.value
  const due = picture.planned_due_90_days.value
  return <section aria-labelledby="snapshot-heading" className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
    <div className="flex flex-wrap items-end justify-between gap-2">
      <h3 id="snapshot-heading" className="text-xl font-semibold">Your month at a glance</h3>
      <p className="text-xs text-slate-500">Saved information as of {picture.as_of_date}</p>
    </div>
    <dl className="mt-4 grid gap-3 md:grid-cols-3">
      <div className={`rounded-xl p-4 ${shortfall ? 'border border-rose-200 bg-rose-50' : 'border border-teal-200 bg-teal-50'}`}>
        <dt className="text-sm font-medium">{gross == null ? 'Gross monthly position' : shortfall ? 'Gross monthly shortfall' : Number(gross) === 0 ? 'Gross monthly balance' : 'Gross monthly remainder'}</dt>
        <dd className="mt-1 text-2xl font-semibold">{gross == null ? 'Unknown' : formatAmount(Math.abs(Number(gross)))}</dd>
        <p className="mt-2 text-xs text-slate-600">Income before tax minus entered monthly expenses. A remainder is not verified spendable cash.</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <dt className="text-sm font-medium">Emergency reserve</dt>
        <dd className="mt-1 text-2xl font-semibold">{coverage == null ? 'Unknown coverage' : `${coverage} months covered`}</dd>
        <p className="mt-2 text-xs text-slate-600">{coverage == null ? 'Enter monthly expenses to estimate coverage.'
          : targetGap != null && Number(targetGap) === 0 ? "At or above the app's illustrative three-month target."
            : `${money(targetGap)} below the app's illustrative three-month target.`}</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <dt className="text-sm font-medium">One-time costs due in 90 days</dt>
        <dd className="mt-1 text-2xl font-semibold">{money(due)}</dd>
        <p className="mt-2 text-xs text-slate-600">These dated costs are separate from the recurring monthly expenses above.</p>
      </div>
    </dl>
  </section>
}

export function UpcomingOverview({ picture, onOpenProfile, onOpenGoal, onOpenGoals }) {
  if (!picture) return null
  const obligations = picture.obligations.filter((item) => {
    const days = daysFrom(picture.as_of_date, item.due_date)
    return item.kind === 'loan_payment' || days == null || days <= 90
  })
  const goals = picture.goals.filter((item) => Number(item.remaining_amount) > 0)
  return <section aria-labelledby="upcoming-heading" className="rounded-2xl border border-slate-200 bg-slate-50 p-5 sm:p-6">
    <h3 id="upcoming-heading" className="text-xl font-semibold">What is coming up</h3>
    <p className="mt-1 text-sm text-slate-600">Due dates and targets you saved. Check actual payment dates and money set aside before acting.</p>
    <div className="mt-5 grid gap-6 lg:grid-cols-2">
      <div><div className="flex flex-wrap items-baseline justify-between gap-2"><h4 className="font-semibold">Upcoming obligations</h4>
        <button type="button" onClick={() => onOpenProfile?.()} className="text-sm text-teal-900 underline">Review costs and loans</button></div>
        {obligations.length ? <><ul className="mt-3 space-y-3">{obligations.slice(0, 3).map((item) =>
          <Obligation key={`${item.kind}-${item.id}`} item={item} asOfDate={picture.as_of_date} />)}</ul>
          {obligations.length > 3 && <details className="mt-3 text-sm"><summary className="cursor-pointer font-medium">Show {obligations.length - 3} more obligations</summary>
            <ul className="mt-3 space-y-3">{obligations.slice(3).map((item) => <Obligation key={`${item.kind}-${item.id}`} item={item} asOfDate={picture.as_of_date} />)}</ul></details>}</>
          : <p className="mt-3 rounded-xl bg-white p-4 text-sm text-slate-600">No dated costs or loan payments are recorded for the next 90 days.</p>}
      </div>
      <div><div className="flex flex-wrap items-baseline justify-between gap-2"><h4 className="font-semibold">Goals in progress</h4>
        <button type="button" onClick={() => onOpenGoals?.()} className="text-sm text-teal-900 underline">Manage goals</button></div>
        {goals.length ? <><ul className="mt-3 space-y-3">{goals.slice(0, 3).map((goal) =>
          <Goal key={goal.id} goal={goal} asOfDate={picture.as_of_date} onOpenGoal={onOpenGoal} />)}</ul>
          {goals.length > 3 && <details className="mt-3 text-sm"><summary className="cursor-pointer font-medium">Show {goals.length - 3} more goals</summary>
            <ul className="mt-3 space-y-3">{goals.slice(3).map((goal) => <Goal key={goal.id} goal={goal} asOfDate={picture.as_of_date} onOpenGoal={onOpenGoal} />)}</ul></details>}</>
          : <p className="mt-3 rounded-xl bg-white p-4 text-sm text-slate-600">{picture.goals.length ? 'All active goal targets are reached.' : 'No active goals are saved yet.'}</p>}
      </div>
    </div>
  </section>
}
