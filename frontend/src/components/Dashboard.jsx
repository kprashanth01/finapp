import { formatAmount, staleMessage } from '../utils/format.js'
import { getDashboardDecision, getDashboardDisplayState } from '../services/dashboardState.js'
import ScenarioPreview from './ScenarioPreview.jsx'

const balanceItems = [
  ['Gross monthly income', 'monthly_income', 'user'],
  ['Monthly expenses', 'monthly_expenses', 'profile'],
  ['Savings balance', 'savings', 'profile'],
  ['Outstanding debt', 'existing_debt', 'profile'],
  ['Emergency fund balance', 'emergency_fund', 'profile'],
]

const ratioItems = [
  ['Savings rate', 'savings_rate_percent', '%'],
  ['Debt-to-income ratio', 'debt_to_income_percent', '%'],
  ['Expense-to-income ratio', 'expense_to_income_percent', '%'],
  ['Emergency fund coverage', 'emergency_fund_months', ' months'],
]

function evidenceText(item) {
  if (!item) return null
  const value = item.unit === 'currency' ? formatAmount(item.value) : item.value
  const unit = item.unit === '%' ? '%' : item.unit === 'months' ? ' months' : item.unit === 'currency' ? ' (profile currency)' : ''
  return `${item.label}: ${value}${unit}`
}

function Dashboard({ user, profile, analysis, advisorySession, advisoryLoading, advisoryRunning, advisoryError, saving, goalPending, onRetryAdvisory, onRunAdvisory, onOpenProfile, onOpenGoal, onOpenAdvisor, goals, goalsLoading, goalsError, onOpenGoals }) {
  const display = getDashboardDisplayState({ saving, analysis, advisoryLoading, advisoryError, advisorySession })
  if (display.updating) return <p role="status" className="text-slate-600">Updating dashboard from your saved values…</p>

  if (!profile) return <section aria-labelledby="dashboard-heading">
    <h2 id="dashboard-heading" className="text-2xl font-semibold">Start your financial plan</h2>
    <p className="mt-2 text-slate-600">Add your monthly expenses, savings, debt, and emergency reserve to see what needs attention.</p>
    <button type="button" onClick={() => onOpenProfile()} className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700">Create financial profile</button>
  </section>

  const decision = display.latest === 'saved' ? getDashboardDecision(advisorySession) : null
  const activeGoals = goals.filter((goal) => !goal.archived)
  const reachedGoals = activeGoals.filter((goal) => Number(goal.saved_amount) >= Number(goal.target_amount)).length
  const canRun = !saving && !goalPending && !advisoryLoading && !advisoryRunning && !goalsLoading && !goalsError

  function follow(action) {
    const next = action?.next_action
    if (next?.view === 'profile') onOpenProfile(next.field)
    else if (next?.view === 'goals') onOpenGoal(next.goal_id)
    else onOpenAdvisor()
  }

  return <div className="space-y-8">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 id="dashboard-heading" className="text-2xl font-semibold">{user.name}'s financial plan</h2>
        <p className="mt-1 text-sm text-slate-600">Your saved profile and the latest monthly plan, in your profile currency.</p></div>
      <button type="button" onClick={() => onOpenProfile()} className="text-sm font-medium text-slate-700 underline underline-offset-4">Edit profile</button>
    </div>

    <section aria-labelledby="decision-heading" className="rounded-2xl border border-slate-200 bg-slate-50 p-5 sm:p-6">
      <h3 id="decision-heading" className="text-xl font-semibold">What should I do this month?</h3>
      {display.latest === 'loading' && <p role="status" className="mt-3 text-sm text-slate-600">Checking your saved plan…</p>}
      {display.latest === 'error' && <div className="mt-3 text-sm"><p role="alert" className="text-rose-800">Your plan status could not be checked: {advisoryError}</p>
        <button type="button" onClick={onRetryAdvisory} className="mt-3 font-medium underline">Retry plan status</button></div>}
      {display.latest === 'empty' && <div className="mt-3"><p className="text-sm text-slate-700">You have a saved profile. Run a plan to see which financial need comes first and how to divide your recorded monthly savings.</p>
        <button type="button" disabled={!canRun} onClick={onRunAdvisory} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Create my monthly plan</button></div>}
      {display.latest === 'saved' && !decision && <div className="mt-3"><p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{advisorySession.is_stale ? staleMessage(advisorySession) : 'This earlier run has no coordinated monthly plan. Run analysis again to build one.'}</p>
        <button type="button" disabled={!canRun} onClick={onRunAdvisory} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Run updated plan</button></div>}
      {decision && <div className="mt-4 space-y-5">
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your first priority · Plan from {advisorySession.result.state.as_of_date}</p>
          <h4 className="mt-2 text-lg font-semibold text-slate-900">{decision.primary.title}</h4>
          {decision.evidence && <p className="mt-2 text-sm font-medium text-slate-900">{evidenceText(decision.evidence)}</p>}
          <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">What we found:</span> {decision.primary.reason}</p>
          {decision.impact && <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">Why it matters:</span> {decision.impact}</p>}
          {decision.suggestedAction ? <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">What to do:</span> {decision.suggestedAction}</p>
            : decision.hasPriority && <p className="mt-2 text-sm text-slate-600">{advisorySession.result.advice.summary.text}</p>}
          <div className="mt-4 flex flex-wrap gap-4 text-sm">
            <button type="button" onClick={() => follow(decision.primary)} className="font-semibold text-slate-900 underline underline-offset-4">{decision.primary.next_action?.view === 'goals' ? 'Review this goal' : 'Review saved details'}</button>
            <button type="button" onClick={onOpenAdvisor} className="font-semibold text-slate-700 underline underline-offset-4">See the full plan and reasons</button>
          </div>
        </div>
        <div>
          <h4 className="font-semibold">How to divide your monthly savings</h4>
          {decision.plan.capacity == null ? <p className="mt-2 text-sm text-slate-700">Add the amount you plan to save each month before an allocation can be calculated. Gross income minus expenses is not treated as available savings. <button type="button" onClick={() => onOpenProfile('monthly_savings_contribution')} className="font-medium underline">Add monthly savings contribution</button></p> : <>
            <p className="mt-1 text-sm text-slate-600">Proposed use of your recorded monthly savings contribution. No money is moved or balance changed.</p>
            <dl className="mt-3 divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white px-4 text-sm">
              <div className="flex justify-between gap-3 py-3 font-semibold"><dt>Available for this plan</dt><dd>{formatAmount(decision.plan.capacity)}</dd></div>
              <div className="flex justify-between gap-3 py-3"><dt>Emergency reserve</dt><dd>{formatAmount(decision.plan.emergency_allocation)}</dd></div>
              {decision.plan.goal_allocations.map((item) => <div key={item.requirement.goal.id} className="flex justify-between gap-3 py-3"><dt className="break-words">{item.requirement.goal.name}</dt><dd>{formatAmount(item.allocated_monthly)}</dd></div>)}
              <div className="flex justify-between gap-3 py-3"><dt>Unassigned for review</dt><dd>{formatAmount(decision.plan.unassigned)}</dd></div>
            </dl>
          </>}
          {decision.plan.hold_reason && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{decision.plan.hold_reason}</p>}
        </div>
        {decision.otherPriorities.length > 0 && <div><h4 className="font-semibold">Also needs attention</h4>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-700">{decision.otherPriorities.map((action) => <li key={action.code}><span className="font-medium text-slate-900">{action.title}.</span> {action.reason}</li>)}</ol></div>}
      </div>}
    </section>

    <ScenarioPreview key={JSON.stringify([user, profile, goals])} user={user} profile={profile} disabled={!canRun} />

    <section aria-labelledby="picture-heading" className="border-t border-slate-200 pt-7">
      <h3 id="picture-heading" className="text-xl font-semibold">Your financial picture</h3>
      <p className="mt-1 text-sm text-slate-600">These are recorded amounts and calculated facts. Monthly savings contribution is the budget used by the plan.</p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 p-4"><dt className="text-sm text-slate-600">Monthly savings contribution</dt><dd className="mt-1 text-xl font-semibold">{formatAmount(profile.monthly_savings_contribution)}</dd></div>
        <div className="rounded-xl border border-slate-200 p-4"><dt className="text-sm text-slate-600">Emergency expense coverage</dt><dd className="mt-1 text-xl font-semibold">{analysis?.emergency_fund_months == null ? 'Unavailable' : `${analysis.emergency_fund_months} months`}</dd></div>
        <div className="rounded-xl border border-slate-200 p-4"><dt className="text-sm text-slate-600">Debt payment share of gross income</dt><dd className="mt-1 text-xl font-semibold">{analysis?.debt_to_income_percent == null ? 'Unavailable' : `${analysis.debt_to_income_percent}%`}</dd></div>
      </dl>
      <details className="mt-4 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-medium">All saved amounts and calculated ratios</summary>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{balanceItems.map(([label, key, source]) => <div key={key} className="rounded-lg bg-slate-50 p-3"><dt className="text-sm text-slate-600">{label}</dt><dd className="mt-1 font-semibold">{formatAmount(source === 'user' ? user[key] : profile[key])}</dd></div>)}</dl>
        {display.snapshot === 'ready' ? <dl className="mt-4 grid gap-3 sm:grid-cols-2">{ratioItems.map(([label, key, unit]) => <div key={key} className="rounded-lg bg-slate-50 p-3"><dt className="text-sm text-slate-600">{label}</dt><dd className="mt-1 font-semibold">{analysis[key] == null ? 'Unavailable' : `${analysis[key]}${unit}`}</dd></div>)}</dl> : <p className="mt-4 text-sm text-slate-600">Calculated ratios could not load. Reload this page to try again.</p>}
        <p className="mt-4 text-sm text-slate-600">Risk tolerance: <span className="font-medium capitalize text-slate-900">{profile.risk_tolerance}</span>. Ratios using income use gross income, which does not show spendable cash.</p>
        {display.snapshot === 'ready' && <p className="mt-2 text-xs text-slate-500">Illustrative project health score: {analysis.health_score == null ? 'Unavailable' : `${analysis.health_score} / 100`}. This heuristic is not validated financial advice.</p>}
      </details>
    </section>

    <section aria-labelledby="goals-heading" className="border-t border-slate-200 pt-7"><h3 id="goals-heading" className="text-lg font-semibold">Goals at a glance</h3>
      <p className="mt-2 text-sm text-slate-600">{goalsLoading ? 'Loading goals…' : goalsError ? 'Goals could not load. Open Goals to retry.' : `${activeGoals.length} active ${activeGoals.length === 1 ? 'goal' : 'goals'} · ${reachedGoals} targets reached`}</p>
      <button type="button" onClick={onOpenGoals} className="mt-3 text-sm underline">Manage goals</button>
    </section>
  </div>
}

export default Dashboard
