import { formatAmount } from '../utils/format.js'

const statusText = {
  MET: 'Requirement currently met', NEEDS_IMPROVEMENT: 'Needs improvement',
  NOT_MET: 'Not met based on entered figures', UNKNOWN: 'Not provided / cannot assess',
}
const statusColor = {
  MET: 'bg-emerald-100 text-emerald-900', NEEDS_IMPROVEMENT: 'bg-amber-100 text-amber-900',
  NOT_MET: 'bg-rose-100 text-rose-900', UNKNOWN: 'bg-slate-100 text-slate-700',
}

function Money({ value }) { return <>{value == null ? 'Not supplied' : formatAmount(value)}</> }

function CapacityCard({ title, point }) {
  if (!point) return <div className="rounded-xl border border-slate-200 p-4"><h4 className="font-semibold">{title}</h4>
    <p className="mt-2 text-sm text-slate-600">Record income months to see this comparison.</p></div>
  const remaining = point.remaining_after_savings ?? point.remaining_before_savings
  return <div className="rounded-xl border border-slate-200 bg-white p-4">
    <h4 className="font-semibold text-slate-900">{title}</h4>
    {point.period && <p className="mt-1 text-xs text-slate-500">Recorded income from {point.period}; compared with current Profile expenses</p>}
    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
      <dt>Gross income</dt><dd className="text-right font-medium"><Money value={point.income} /></dd>
      <dt>Current total expenses</dt><dd className="text-right font-medium"><Money value={point.total_expenses_including_existing_emi} /></dd>
      <dt>Existing EMI included above</dt><dd className="text-right font-medium"><Money value={point.existing_emi_included} /></dd>
      <dt>Proposed new EMI</dt><dd className="text-right font-medium"><Money value={point.proposed_emi} /></dd>
      <dt>Planned savings</dt><dd className="text-right font-medium"><Money value={point.planned_savings} /></dd>
    </dl>
    <p className={`mt-4 rounded-lg p-3 text-sm font-semibold ${Number(remaining) < 0 ? 'bg-rose-50 text-rose-900' : 'bg-teal-50 text-teal-900'}`}>
      {point.planned_savings == null ? 'Gross room before planned savings' : 'Gross room after planned savings'}: <Money value={remaining} />
    </p>
  </div>
}

function RequirementCard({ item, compact = false }) {
  return <article className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><h4 className="font-semibold text-slate-900">{item.name}</h4>
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusColor[item.status]}`}>{statusText[item.status]}</span></div>
    <p className="mt-2 text-sm text-slate-700">{item.explanation}</p>
    {!compact && <dl className="mt-3 grid gap-1 text-xs text-slate-600">
      <div><dt className="inline font-semibold">Your value: </dt><dd className="inline">{item.current_value ?? 'Not provided'}</dd></div>
      <div><dt className="inline font-semibold">Comparison: </dt><dd className="inline">{item.required_value ?? 'No threshold entered'}</dd></div>
    </dl>}
    {item.action && <p className="mt-3 text-sm"><strong>What you can do:</strong> {item.action}</p>}
    <p className="mt-3 text-xs text-slate-500">Source: {item.source_label}</p>
  </article>
}

export default function LoanReadinessResults({ assessment }) {
  const a = assessment
  return <div className="space-y-7" aria-label="Loan readiness assessment">
    <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Your current financial position</p>
      <h3 className="mt-1 text-xl font-semibold text-teal-950">{a.summary}</h3>
      <p className="mt-2 text-sm text-slate-700">Last evaluated: {new Date(a.evaluated_at).toLocaleString()}. This is a preparation check, not an approval decision.</p>
      {a.changes_since_previous?.length > 0 && <div className="mt-4 rounded-lg bg-white p-3 text-sm">
        <h4 className="font-semibold">What changed since the previous evaluation</h4>
        <ul className="mt-2 list-disc space-y-1 pl-5">{a.changes_since_previous.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>}
    </section>

    <section aria-labelledby="loan-payment-heading">
      <h3 id="loan-payment-heading" className="text-xl font-semibold">Proposed loan payment</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 p-4"><p className="text-sm text-slate-600">Estimated monthly EMI</p><p className="mt-1 text-2xl font-semibold"><Money value={a.estimated_emi} /></p>
          <p className="mt-1 text-xs text-slate-500">{a.emi_source === 'entered_quote' ? 'Your entered payment quote' : a.emi_source === 'calculated' ? 'Calculated from amount, rate and tenure' : 'Enter an interest rate or payment quote'}</p></div>
        <div className="rounded-xl border border-slate-200 p-4"><p className="text-sm text-slate-600">Estimated total repayment</p><p className="mt-1 text-2xl font-semibold"><Money value={a.total_repayment} /></p><p className="mt-1 text-xs text-slate-500">EMI × tenure, excluding other charges</p></div>
        <div className="rounded-xl border border-slate-200 p-4"><p className="text-sm text-slate-600">Existing monthly EMI</p><p className="mt-1 text-2xl font-semibold"><Money value={a.existing_monthly_emi} /></p><p className="mt-1 text-xs text-slate-500">Already included in current expenses</p></div>
      </div>
    </section>

    <section aria-labelledby="loan-income-heading">
      <h3 id="loan-income-heading" className="text-xl font-semibold">Your changing income</h3>
      <p className="mt-1 text-sm text-slate-600">{a.income.observed_months} recorded months{a.income.first_period ? ` from ${a.income.first_period} to ${a.income.latest_period}` : ''}. These are observations, not a forecast.</p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[["Average income", a.income.average], ["Median income", a.income.median],
          ["Lowest income", a.income.minimum], ["Highest income", a.income.maximum]].map(([label, value]) =>
          <div key={label} className="rounded-xl bg-slate-50 p-3"><dt className="text-sm text-slate-600">{label}</dt><dd className="mt-1 font-semibold"><Money value={value} /></dd></div>)}
      </dl>
      <p className="mt-3 text-sm text-slate-700">Income variation (standard deviation divided by average): {a.income.variability_percent == null ? 'Needs at least two recorded months' : `${a.income.variability_percent}%`}.
        {a.income.latest_change != null && ` Latest recorded change: ${formatAmount(a.income.latest_change)}.`}</p>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <CapacityCard title="Typical month (median income)" point={a.typical_month} />
        <CapacityCard title="Low-income month" point={a.low_income_month} />
      </div>
      <details className="mt-4 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-semibold">Compare every recorded month</summary>
        <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[580px] text-left text-sm"><thead><tr className="border-b"><th className="p-2">Month</th><th className="p-2">Income</th><th className="p-2">Spending incl. existing EMI</th><th className="p-2">New EMI</th><th className="p-2">Room before savings</th></tr></thead>
          <tbody>{a.recorded_months.map((point) => <tr key={point.period} className="border-b"><td className="p-2">{point.period}</td><td className="p-2"><Money value={point.income} /></td><td className="p-2"><Money value={point.total_expenses_including_existing_emi} /></td><td className="p-2"><Money value={point.proposed_emi} /></td><td className="p-2"><Money value={point.remaining_before_savings} /></td></tr>)}</tbody></table></div>
      </details>
    </section>

    <section aria-labelledby="loan-strengthen-heading">
      <h3 id="loan-strengthen-heading" className="text-xl font-semibold">Areas to strengthen</h3>
      <p className="mt-1 text-sm text-slate-600">These actions come from the calculated checks below, ordered by urgency.</p>
      {a.priority_actions.length ? <div className="mt-3 grid gap-3 md:grid-cols-2">{a.priority_actions.map((item) => <RequirementCard key={item.key} item={item} compact />)}</div>
        : <p className="mt-3 rounded-xl bg-emerald-50 p-4 text-sm">No area is flagged by the available project checks. Confirm lender terms, take-home pay and missing information before applying.</p>}
    </section>

    <section aria-labelledby="loan-requirements-heading">
      <h3 id="loan-requirements-heading" className="text-xl font-semibold">Requirement-by-requirement review</h3>
      <p className="mt-1 text-sm text-slate-600">A lender name does not add requirements automatically. User-entered criteria are labeled unverified until you confirm their source.</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">{a.requirements.map((item) => <RequirementCard key={item.key} item={item} />)}</div>
    </section>

    <section className="rounded-xl border border-slate-200 p-5">
      <h3 className="text-xl font-semibold">Costs, debt and reserve behind this check</h3>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div><dt className="text-slate-600">Known essential monthly floor</dt><dd className="font-semibold"><Money value={a.known_essential_expenses} /></dd></div>
        <div><dt className="text-slate-600">Known discretionary costs</dt><dd className="font-semibold"><Money value={a.known_discretionary_expenses} /></dd></div>
        <div><dt className="text-slate-600">Unclassified spending</dt><dd className="font-semibold"><Money value={a.unclassified_expenses} /></dd></div>
        <div><dt className="text-slate-600">Existing debt balance</dt><dd className="font-semibold"><Money value={a.existing_debt} /></dd></div>
        <div><dt className="text-slate-600">Emergency reserve coverage</dt><dd className="font-semibold">{a.reserve_coverage_months == null ? 'Not supplied' : `${a.reserve_coverage_months} months`}</dd></div>
        <div><dt className="text-slate-600">Gap to illustrative reserve target</dt><dd className="font-semibold"><Money value={a.reserve_gap} /></dd></div>
      </dl>
      {a.goal_monthly_needs.length > 0 && <div className="mt-4"><h4 className="font-semibold">Competing saved goals</h4><ul className="mt-2 list-disc pl-5 text-sm">{a.goal_monthly_needs.map((goal) =>
        <li key={goal.name}>{goal.name}: {goal.required_monthly == null ? 'monthly need cannot be calculated' : `${formatAmount(goal.required_monthly)} needed monthly`} ({goal.priority} priority)</li>)}</ul></div>}
    </section>
    <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-semibold">Assumptions and calculation limits</summary>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">{a.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
    </details>
  </div>
}
