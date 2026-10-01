import { formatAmount } from '../utils/format.js'
import ExplanationTrail from './ExplanationTrail.jsx'

const statuses = { completed: 'Target reached', overdue: 'Deadline needs updating', budget_covered: 'Monthly requirement covered', underfunded: 'Monthly funding gap', missing_budget: 'Add monthly savings contribution' }
const agentNames = { budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning', risk: 'Risk assessment', investment: 'Investment readiness' }

function evidenceText(item) {
  if (item.value == null) return `${item.label}: not supplied`
  if (item.unit === 'currency') return `${item.label}: ${formatAmount(item.value)} (profile currency)`
  return `${item.label}: ${item.value}${item.unit === '%' ? '%' : item.unit ? ` ${item.unit}` : ''}`
}

export default function AdvisoryPlan({ result, onOpenProfile, onOpenGoal, showExplanation = true }) {
  const { summary, monthly_plan: plan, investment, priority_actions: actions } = result.advice
  const guidedFindings = (result.agent_results ?? []).flatMap((agent) => (agent.findings ?? [])
    .filter((finding) => finding.impact && finding.suggested_action)
    .map((finding) => ({ agentId: agent.agent_id, finding })))
  function follow(next) {
    if (next.view === 'goals') onOpenGoal(next.goal_id)
    else if (next.view === 'profile') onOpenProfile(next.field)
  }
  return <div className="space-y-6">
    <section className="rounded-xl bg-slate-900 p-5 text-white" aria-label="Your next step">
      <p className="text-xs uppercase tracking-wider text-slate-300">Your next step</p>
      <h3 className="mt-2 text-xl font-semibold">{summary.title}</h3><p className="mt-2 text-sm text-slate-200">{summary.text}</p>
      <button className="mt-4 rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-900" onClick={() => follow(summary.next_action)}>{summary.next_action.view === 'goals' ? 'Review goals' : 'Review profile'}</button>
    </section>
    {showExplanation && result.explanation && <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-medium">How this plan was decided</summary><ExplanationTrail trace={result.explanation} /></details>}
    <section aria-labelledby="monthly-plan-heading">
      <h3 id="monthly-plan-heading" className="text-lg font-semibold">Your monthly savings plan</h3>
      <p className="mt-1 text-sm text-slate-600">Based on {result.state.as_of_date}. These are proposed allocations, not payments or automatic balance changes. All amounts use your profile currency.</p>
      <dl className="mt-4 divide-y divide-slate-200 rounded-xl border border-slate-200 px-4 text-sm">
        <div className="flex flex-wrap justify-between gap-2 py-3 font-semibold"><dt>Monthly savings budget</dt><dd>{formatAmount(plan.capacity)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2 py-3"><dt>Emergency reserve first</dt><dd>{formatAmount(plan.emergency_allocation)}</dd></div>
        {plan.goal_allocations.map((a) => <div key={a.requirement.goal.id} className="flex flex-wrap justify-between gap-2 py-3"><dt className="break-words">{a.requirement.goal.name}</dt><dd>{formatAmount(a.allocated_monthly)}</dd></div>)}
        <div className="flex flex-wrap justify-between gap-2 py-3 font-medium"><dt>Unassigned savings</dt><dd>{formatAmount(plan.unassigned)}</dd></div>
      </dl>
      {plan.hold_reason && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{plan.hold_reason}</p>}
      <p className="mt-2 text-xs text-slate-500">Reserve target: three months of expenses, not a three-month deadline. Remaining capacity goes to goals by priority, then date.</p>
    </section>
    <section><h3 className="text-lg font-semibold">Can your goals fit?</h3>
      {plan.goal_allocations.length === 0 ? <p className="mt-2 text-sm text-slate-600">No active goals were included in this run. <button onClick={() => onOpenGoal(null)} className="underline">Add a goal</button></p> :
        <ul className="mt-3 space-y-3">{plan.goal_allocations.map((a) => <li key={a.requirement.goal.id} className="rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap justify-between gap-2"><h4 className="break-words font-semibold">{a.requirement.goal.name}</h4><span className={`text-sm ${a.status === 'underfunded' || a.status === 'overdue' ? 'text-amber-800' : 'text-slate-600'}`}>{statuses[a.status]}</span></div>
          <p className="mt-1 text-xs text-slate-500">Target {a.requirement.goal.target_date} · {a.requirement.goal.priority} priority · Remaining {formatAmount(a.requirement.remaining_amount)}</p>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
            <div><dt className="text-slate-500">Saved at this run</dt><dd className="mt-1 font-medium">{formatAmount(a.requirement.goal.saved_amount)}</dd></div>
            <div><dt className="text-slate-500">Target amount</dt><dd className="mt-1 font-medium">{formatAmount(a.requirement.goal.target_amount)}</dd></div>
            <div><dt className="text-slate-500">Approximate months remaining</dt><dd className="mt-1 font-medium">{a.requirement.approximate_months ?? (a.status === 'completed' ? 'Target reached' : 'Update deadline')}</dd></div>
          </dl>
          <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">{[['Needed per month',a.requirement.required_monthly],['Planned per month',a.allocated_monthly],['Monthly gap',a.funding_gap]].map(([label,value]) => <div key={label}><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-semibold">{value == null && a.status === 'overdue' ? 'Update deadline' : formatAmount(value)}</dd></div>)}</dl>
          <button onClick={() => onOpenGoal(a.requirement.goal.id)} className="mt-3 text-sm underline">Edit current goal</button>
        </li>)}</ul>}
    </section>
    <section className="rounded-xl border border-slate-200 p-4"><h3 className="text-lg font-semibold">Investment readiness</h3>
      <p className="mt-2 font-medium">{investment.status === 'ready_to_consider' ? 'Ready to consider' : investment.status === 'deferred' ? 'Address priorities first' : 'More information needed'}</p>
      {investment.category && <p className="mt-1 text-sm capitalize">Illustrative category: {investment.category}</p>}
      {investment.reasons.length > 0 ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">{investment.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p className="mt-2 text-sm text-slate-600">The saved profile passes these project checks. Unassigned savings: {formatAmount(plan.unassigned)}. Passing checks does not select an investment or promise returns.</p>}
    </section>
    {guidedFindings.length > 0 && <section aria-labelledby="specialist-guidance-heading">
      <h3 id="specialist-guidance-heading" className="text-lg font-semibold">What each check found</h3>
      <p className="mt-1 text-sm text-slate-600">These checks explain the coordinated plan above. They do not assign additional money.</p>
      <ul className="mt-3 grid gap-3 md:grid-cols-2">{guidedFindings.map(({ agentId, finding }) => <li key={`${agentId}-${finding.code}`} className="rounded-xl border border-slate-200 p-4 text-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{agentNames[agentId] ?? agentId}</p>
        <h4 className="mt-1 font-semibold">{finding.title}</h4>
        <p className="mt-2 text-slate-700"><span className="font-medium text-slate-900">What we found:</span> {finding.reason}</p>
        {finding.evidence?.length > 0 && <ul className="mt-2 flex flex-wrap gap-2">{finding.evidence.map((item) => <li key={item.label} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">{evidenceText(item)}</li>)}</ul>}
        <p className="mt-2 text-slate-700"><span className="font-medium text-slate-900">Why it matters:</span> {finding.impact}</p>
        <p className="mt-2 text-slate-700"><span className="font-medium text-slate-900">What to do:</span> {finding.suggested_action}</p>
      </li>)}</ul>
    </section>}
    <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-medium">Why this plan and what to update</summary>
      <p className="mt-3 text-sm text-slate-600">One savings budget is used once. Emergency needs come first; high or unknown debt burden holds the remainder for review. Future goals then receive up to their monthly requirement.</p>
      <p className="mt-2 text-sm text-slate-600">Goal requirement = remaining target ÷ rounded-up 30-day months, rounded up to cents. No growth is assumed.</p>
      <ul className="mt-4 space-y-4">{actions.map((action) => <li key={action.code}><h4 className="font-medium">{action.title}</h4><p className="mt-1 text-sm text-slate-600">{action.reason}</p><button onClick={() => follow(action.next_action)} className="mt-1 text-sm underline">{action.next_action.view === 'goals' ? 'Update goal' : 'Update profile'}</button></li>)}</ul>
    </details>
  </div>
}
