import AdvisoryPlan from './AdvisoryPlan.jsx'
import ReasoningPanel from './ReasoningPanel.jsx'
import { staleMessage } from '../utils/format.js'
const agentNames = { budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning', risk: 'Risk assessment', investment: 'Investment' }
const capturedInputs = [
  ['Gross monthly income', 'monthly_income'],
  ['Monthly expenses', 'monthly_expenses'],
  ['Monthly savings contribution', 'monthly_savings_contribution'],
  ['Monthly debt payments', 'monthly_debt_payments'],
  ['Outstanding debt', 'existing_debt'],
  ['Emergency fund', 'emergency_fund'],
]

function formatEvidence(item) {
  if (item.value == null) return `${item.label}: unavailable`
  if (item.unit === '%') return `${item.label}: ${item.value}%`
  if (item.unit === 'months') return `${item.label}: ${item.value} months`
  return `${item.label}: ${item.value} (profile currency)`
}

function EvidenceList({ items }) {
  return (
    <ul className="mt-3 flex flex-wrap gap-2" aria-label="Supporting numbers">
      {items.map((item) => (
        <li key={item.label} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
          {formatEvidence(item)}
        </li>
      ))}
    </ul>
  )
}

function AdvisorySession({ session, loading, running, saving, error, onRun, historical, onShowLatest, onOpenProfile, onOpenGoal }) {
  const result = session?.result
  const agents = Object.fromEntries((result?.agent_results ?? []).map((item) => [item.agent_id, item]))

  return (
    <section className="mt-10 border-t border-slate-200 pt-8" aria-labelledby="advisory-heading">
      <h2 id="advisory-heading" className="text-xl font-semibold">Advisory session</h2>
      <p className="mt-1 text-sm text-slate-600">
        Turn your saved profile and goals into a monthly plan. Run again after saving changes to update the findings.
      </p>

      <button
        type="button"
        onClick={onRun}
        disabled={running || loading || saving}
        className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {running ? 'Running…' : historical ? 'Run analysis on current profile' : session ? 'Run analysis again' : 'Run analysis'}
      </button>
      {historical && <button type="button" onClick={onShowLatest} className="ml-3 mt-5 text-sm font-medium text-slate-700 underline underline-offset-4">Back to latest run</button>}

      {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {loading && <p className="mt-4 text-sm text-slate-600">Loading latest saved session…</p>}
      {!loading && !session && <p className="mt-4 text-sm text-slate-600">No advisory session has been run yet.</p>}

      {session && (
        <div className="mt-6 space-y-5">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
            <p className="font-medium">{historical ? 'Earlier saved plan' : 'Latest saved plan'}</p>
            <p className="mt-1 text-slate-600">{new Date(session.created_at).toLocaleString()}</p>
            {session.is_stale && (
              <p className="mt-3 rounded-md bg-amber-50 p-3 text-amber-900">
                {staleMessage(session)}
              </p>
            )}
          </div>

          {result.advice ? <AdvisoryPlan result={result} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} /> : <>
          <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Earlier analysis format. This run keeps its original three-agent findings; run analysis again to include goals and a monthly plan.</p>
          <details open={historical} className="rounded-lg border border-slate-200 p-4">
            <summary className="cursor-pointer text-sm font-medium">Financial inputs captured for this run</summary>
            <p className="mt-3 text-xs text-slate-600">These values were stored with this session. Other profile fields were not recorded in the historical result.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
              {capturedInputs.map(([label, key]) => (
                <div key={key}>
                  <dt className="text-slate-600">{label}</dt>
                  <dd className="font-medium">{result.state[key] == null ? 'Not supplied' : `${result.state[key]} (profile currency)`}</dd>
                </div>
              ))}
            </dl>
          </details>

          <div>
            <h3 className="text-base font-semibold">Priority findings</h3>
            {result.priority_actions.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600">No priority finding was produced by this run's rules. Check the agent details below for available and missing inputs.</p>
            ) : (
              <ol className="mt-3 space-y-3">
                {result.priority_actions.map((action) => (
                  <li key={action.code} className="rounded-lg border border-slate-200 p-4">
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{agentNames[action.agent_id]} check</p>
                    <h4 className="mt-1 font-semibold">{action.title}</h4>
                    <p className="mt-1 text-sm text-slate-700">{action.reason}</p>
                    <EvidenceList items={action.evidence} />
                    {action.limitations.map((limit) => <p key={limit} className="mt-2 text-xs text-slate-500">{limit}</p>)}
                  </li>
                ))}
              </ol>
            )}
          </div>

          </>}
          {result.explanation && <ReasoningPanel key={session.id} userId={session.user_id} sessionId={session.id} />}
          <details className="rounded-lg border border-slate-200 p-4">
            <summary className="cursor-pointer text-sm font-medium">Research details: how agents were selected and what they found</summary>
            <p className="mt-3 text-xs text-slate-500">Session {session.id} · {session.rule_version} · Educational project rules, not validated financial advice or predictions.</p>
            {result.advice && <details className="mt-3"><summary className="cursor-pointer text-sm">Captured profile inputs</summary><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">{[...capturedInputs, ['Savings balance','savings'], ['Risk preference','risk_tolerance'], ['Horizon in years','investment_horizon_years']].map(([label,key]) => <div key={key}><dt className="text-slate-500">{label}</dt><dd>{result.state[key] ?? 'Not supplied'}</dd></div>)}</dl></details>}
            <div className="mt-4 space-y-4">
              {result.decision.selections.map((selection) => {
                const agent = agents[selection.agent_id]
                return (
                  <div key={selection.agent_id} className="border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
                    <h4 className="font-medium">{agentNames[selection.agent_id]} · {selection.selected ? 'selected' : 'skipped'}</h4>
                    <p className="mt-1 text-sm text-slate-600">{selection.reason}</p>
                    {agent && (
                      <>
                        {agent.findings.map((finding) => (
                          <div key={finding.code} className="mt-2 text-sm">
                            <p>{finding.title}: {finding.reason}</p>
                            <EvidenceList items={finding.evidence} />
                          </div>
                        ))}
                        {agent.limitations.map((limit) => <p key={limit} className="mt-2 text-xs text-slate-500">{limit}</p>)}
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </details>
        </div>
      )}
    </section>
  )
}

export default AdvisorySession
