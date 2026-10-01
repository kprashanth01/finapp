import { staleMessage } from '../utils/format.js'

import { getDashboardDisplayState } from '../services/dashboardState.js'



const summaryItems = [

  ['Gross monthly income', 'monthly_income', 'user'],

  ['Monthly expenses', 'monthly_expenses', 'profile'],

  ['Savings balance', 'savings', 'profile'],

  ['Outstanding debt', 'existing_debt', 'profile'],

  ['Emergency fund', 'emergency_fund', 'profile'],

]



const snapshotItems = [

  ['Savings rate', 'savings_rate_percent', '%'],

  ['Debt-to-income ratio', 'debt_to_income_percent', '%'],

  ['Expense-to-income ratio', 'expense_to_income_percent', '%'],

  ['Emergency fund coverage', 'emergency_fund_months', ' months'],

]



function Dashboard({ user, profile, analysis, advisorySession, advisoryLoading, advisoryError, saving, onRetryAdvisory, onOpenProfile, onOpenAdvisor, goals, goalsLoading, goalsError, onOpenGoals }) {

  const display = getDashboardDisplayState({ saving, analysis, advisoryLoading, advisoryError, advisorySession })



  if (display.updating) {

    return <p role="status" className="text-slate-600">Updating dashboard from your saved values…</p>

  }



  if (!profile) {

    return (

      <section aria-labelledby="dashboard-heading">

        <h2 id="dashboard-heading" className="text-2xl font-semibold">Dashboard</h2>

        <p className="mt-2 text-slate-600">Your user record is saved. Add a financial profile to see your dashboard.</p>

        <button type="button" onClick={onOpenProfile} className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700">

          Create financial profile

        </button>

      </section>

    )

  }



  const priorities = advisorySession?.result.advice?.priority_actions ?? advisorySession?.result.priority_actions ?? []

  const advice = advisorySession?.result.advice
  const summaryPriority = advice ? priorities.findIndex((action) => action.title === advice.summary.title) : -1
  const otherPriorities = priorities.filter((_, index) => index !== summaryPriority)
  const activeGoals = goals.filter((goal) => !goal.archived)
  const reachedGoals = activeGoals.filter((goal) => Number(goal.saved_amount) >= Number(goal.target_amount)).length



  return (

    <div className="space-y-8">

      <section className="rounded-xl border border-slate-200 p-4"><h2 className="text-lg font-semibold">Goals at a glance</h2><p className="mt-2 text-sm text-slate-600">{goalsLoading ? 'Loading goals…' : goalsError ? 'Goals could not load. Open Goals to retry.' : `${activeGoals.length} active ${activeGoals.length === 1 ? 'goal' : 'goals'} · ${reachedGoals} targets reached`}</p><button onClick={onOpenGoals} className="mt-3 text-sm underline">Manage goals</button></section>

      <section aria-labelledby="dashboard-heading">

        <div className="flex flex-wrap items-start justify-between gap-3">

          <div>

            <h2 id="dashboard-heading" className="text-2xl font-semibold">{user.name}'s dashboard</h2>

            <p className="mt-1 text-sm text-slate-600">Current saved amounts, in your profile currency.</p>

          </div>

          <button type="button" onClick={onOpenProfile} className="text-sm font-medium text-slate-700 underline underline-offset-4">Edit profile</button>

        </div>

        <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">

          {summaryItems.map(([label, key, source]) => (

            <div key={key} className="rounded-xl border border-slate-200 bg-slate-50 p-4">

              <dt className="text-sm text-slate-600">{label}</dt>

              <dd className="mt-1 text-xl font-semibold">{source === 'user' ? user[key] : profile[key]}</dd>

            </div>

          ))}

        </dl>

        <p className="mt-4 text-sm text-slate-600">Risk tolerance: <span className="font-medium text-slate-900 capitalize">{profile.risk_tolerance}</span></p>

      </section>



      <section aria-labelledby="snapshot-heading" className="border-t border-slate-200 pt-7">

        <h2 id="snapshot-heading" className="text-xl font-semibold">Financial snapshot</h2>

        <p className="mt-1 text-sm text-slate-600">Calculated from your saved amounts.</p>

        {display.snapshot === 'ready' ? (

          <>

            <dl className="mt-4 grid gap-3 sm:grid-cols-2">

              {snapshotItems.map(([label, key, unit]) => (

                <div key={key} className="rounded-xl border border-slate-200 p-4">

                  <dt className="text-sm text-slate-600">{label}</dt>

                  <dd className="mt-1 text-xl font-semibold">{analysis[key] == null ? 'Unavailable' : `${analysis[key]}${unit}`}</dd>

                </div>

              ))}

            </dl>

            <details className="mt-4 text-sm text-slate-600"><summary className="cursor-pointer font-medium">How these figures are calculated</summary>
              <p className="mt-2">Savings, debt payments, and expenses are each divided by gross monthly income. Emergency coverage is the fund balance divided by monthly expenses.</p>
              <p className="mt-2">Illustrative research score: <strong>{analysis.health_score == null ? 'Unavailable' : `${analysis.health_score} / 100`}</strong>. This project heuristic is not validated financial advice.</p>
            </details>

          </>

        ) : <p className="mt-4 text-sm text-slate-600">The snapshot could not load. Reload this page to try again.</p>}

      </section>



      <section aria-labelledby="latest-heading" className="border-t border-slate-200 pt-7">

        <h2 id="latest-heading" className="text-xl font-semibold">Latest advisory run</h2>

        {display.latest === 'loading' ? <p role="status" className="mt-2 text-sm text-slate-600">Checking your latest saved run…</p> : null}

        {display.latest === 'error' ? (

          <div className="mt-2 text-sm text-rose-800">

            <p role="alert">Latest advisory status unavailable: {advisoryError}</p>

            <button type="button" onClick={onRetryAdvisory} className="mt-2 font-medium underline underline-offset-4">Retry latest run</button>

          </div>

        ) : null}

        {display.latest === 'saved' ? (

          <>

            {advice && <><h3 className="mt-3 text-lg font-semibold">{advice.summary.title}</h3><p className="mt-1 text-sm text-slate-700">{advice.summary.text}</p></>}
            <p className="mt-2 text-sm text-slate-600">{new Date(advisorySession.created_at).toLocaleString()}</p>

            {advisorySession.is_stale && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{staleMessage(advisorySession)}</p>}

            {otherPriorities.length > 0 ? (

              <><p className="mt-3 text-sm font-medium">Other findings</p><ul className="mt-1 list-inside list-disc space-y-1 text-sm text-slate-800">

                {otherPriorities.map((action) => <li key={action.code}>{action.title}</li>)}

              </ul></>

            ) : !advice && <p className="mt-3 text-sm text-slate-600">No priority finding from this run's rules.</p>}

          </>

        ) : null}

        {display.latest === 'empty' && <p className="mt-2 text-sm text-slate-600">No advisory run saved yet.</p>}

        <button type="button" onClick={onOpenAdvisor} className="mt-4 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700">

          {display.latest === 'empty' ? 'Run analysis' : 'Open Advisor'}

        </button>

      </section>

    </div>

  )

}



export default Dashboard

