import { formatAmount } from '../utils/format.js'

const sources = {
  'user.current_income_estimate': 'Profile income estimate',
  'profile.guaranteed_income': 'Optional Profile detail',
  'recorded_months.last_12': 'Recorded Months',
  'recorded_months.latest': 'Latest recorded Month',
  current_estimate_and_recent_recorded_months: 'Profile and recorded Months',
  'profile.monthly_expenses': 'Profile total',
  expense_details_and_profile_debt_payment: 'Expense detail and Profile',
  expense_details: 'Expense detail',
  profile_minus_itemized_expenses_and_debt_payment: 'Profile minus entered detail',
  complete_expense_breakdown: 'Complete expense detail',
  current_income_estimate_minus_profile_expenses: 'Profile income minus expenses',
  gross_cash_flow: 'Calculated gross cash flow',
  'profile.monthly_savings_contribution': 'Profile entry',
  profile_contribution_divided_by_gross_income: 'Profile entries',
  profile_debt_payment_divided_by_gross_income: 'Profile entries',
  profile_emergency_fund_divided_by_total_expenses: 'Profile entries',
  profile_emergency_fund_divided_by_complete_essentials: 'Profile and complete expense detail',
  profile_total_expenses_and_emergency_fund: 'Profile entries',
  active_goals: 'Active Goals',
  planned_expenses_due_within_90_days: 'Upcoming expenses',
}

function FactCard({ title, fact, unit = 'money' }) {
  const value = fact?.value == null ? 'Unknown' : unit === 'money' ? formatAmount(fact.value)
    : `${fact.value}${unit === 'percent' ? '%' : ' months'}`
  return <div className="rounded-lg border border-slate-200 bg-white p-4">
    <dt className="text-sm text-slate-600">{title}</dt>
    <dd className="mt-1 text-xl font-semibold text-slate-900">{value}{fact?.status === 'partial' ? ' known so far' : ''}</dd>
    <p className="mt-2 text-xs text-slate-600">Source: {sources[fact?.source] ?? fact?.source ?? 'Unavailable'}. {fact?.note}</p>
  </div>
}

export default function FinancialPicture({ picture }) {
  if (!picture) return null
  const { income, spending, reserve } = picture
  return <section aria-labelledby="calculated-picture-heading" className="rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:p-6">
    <h3 id="calculated-picture-heading" className="text-xl font-semibold text-teal-950">Deeper financial analysis</h3>
    <p className="mt-1 text-sm text-slate-700">Calculated from saved information as of {picture.as_of_date}. These are facts and estimates, not a new recommendation.</p>
    <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <FactCard title="Gross monthly cash flow" fact={spending.gross_cash_flow} />
      <FactCard title="Possible surplus ceiling" fact={spending.available_surplus_upper_bound} />
      <FactCard title="Emergency reserve gap" fact={reserve.funding_gap} />
    </dl>
    <details className="mt-4 rounded-xl border border-teal-200 bg-white p-4">
      <summary className="cursor-pointer font-semibold">See income history, spending, goals and upcoming costs</summary>
      <div className="mt-5 space-y-6">
        <div><h4 className="font-semibold">Income · {income.observed_months} recorded months</h4>
          <p className="mt-1 text-sm text-slate-600">Latest recorded period: {income.recent_period ?? 'none yet'}. Recorded income is separate from the current estimate and any guaranteed portion.</p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <FactCard title="Current gross estimate" fact={income.expected_monthly} />
            <FactCard title="Guaranteed portion" fact={income.guaranteed_monthly} />
            <FactCard title="Average recorded income" fact={income.observed_average} />
            <FactCard title="Latest recorded income" fact={income.observed_recent} />
            <FactCard title="Lowest recorded income" fact={income.observed_minimum} />
            <FactCard title="Income variability" fact={income.variability_percent} unit="percent" />
            <FactCard title="Conservative planning reference" fact={income.conservative_reference} />
          </dl></div>
        <div><h4 className="font-semibold">Monthly spending and debt</h4>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <FactCard title="Total expenses, including debt" fact={spending.monthly_total} />
            <FactCard title="Known essential fixed costs" fact={spending.known_essential_fixed} />
            <FactCard title="Known essential variable costs" fact={spending.known_essential_variable} />
            <FactCard title="Known essential spending" fact={spending.known_essential} />
            <FactCard title="Known discretionary spending" fact={spending.known_discretionary} />
            <FactCard title="Unclassified non-debt spending" fact={spending.unclassified_monthly} />
            <FactCard title="Exact essential spending" fact={spending.exact_essential} />
            <FactCard title="Exact discretionary spending" fact={spending.exact_discretionary} />
            <FactCard title="Entered monthly savings budget" fact={spending.entered_savings_capacity} />
            <FactCard title="Savings rate" fact={spending.savings_rate_percent} unit="percent" />
            <FactCard title="Debt payment share" fact={spending.debt_to_income_percent} unit="percent" />
          </dl></div>
        <div><h4 className="font-semibold">Reserve, goals and obligations</h4>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <FactCard title="Reserve coverage of all expenses" fact={reserve.total_expense_coverage_months} unit="months" />
            <FactCard title="Reserve coverage of essentials" fact={reserve.essential_coverage_months} unit="months" />
            <FactCard title="Remaining active goal targets" fact={picture.goal_funding_gap} />
            <FactCard title="One-time costs due in 90 days" fact={picture.planned_due_90_days} />
            <FactCard title="Unreserved costs due in 90 days" fact={picture.unreserved_due_90_days} />
          </dl>
          {picture.goals.length > 0 && <ul className="mt-3 space-y-1 text-sm text-slate-700">{picture.goals.map((goal) =>
            <li key={goal.id}>{goal.name}: {formatAmount(goal.remaining_amount)} remaining by {goal.target_date}</li>)}</ul>}
          {picture.obligations.length > 0 && <ul className="mt-3 space-y-1 text-sm text-slate-700">{picture.obligations.map((item) =>
            <li key={`${item.kind}-${item.id}`}>{item.name} ({item.kind === 'loan_payment' ? 'loan payment already in monthly expenses' : 'one-time cost'}): {item.amount == null ? 'amount unknown' : formatAmount(item.amount)}{item.due_date ? ` · ${item.is_overdue ? 'overdue since' : 'due'} ${item.due_date}` : ' · due day unknown'}{item.kind === 'planned_expense' ? ` · unreserved ${item.unreserved_amount == null ? 'unknown' : formatAmount(item.unreserved_amount)}` : ''}{item.rate_change_date ? ` · entered rate-change date ${item.rate_change_date}, new rate ${item.new_annual_interest_rate_percent}%` : ''}</li>)}</ul>}
          {picture.obligations.some((item) => item.kind === 'loan_payment') && <p className="mt-2 text-xs text-slate-600">Loan dates follow your entered day of month and may differ from the lender schedule. Rate changes do not recalculate payments.</p>}
        </div>
        <ul className="space-y-1 text-xs text-slate-600">{picture.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
    </details>
  </section>
}
