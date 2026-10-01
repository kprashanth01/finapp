import { useState } from 'react'
import { explainApiError, getMonthlyDemo } from '../services/api.js'

const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning',
  risk: 'Risk', investment: 'Investment readiness',
}

const money = (value) => value == null ? 'Unavailable' : Number(value).toLocaleString('en-US', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})

export const evidenceValue = (item) => {
  if (item.value == null || item.value === '') return null
  if (!Number.isFinite(Number(item.value))) return String(item.value)
  const formatted = money(item.value)
  return item.unit === '%' ? `${formatted}%` : item.unit === 'currency' ? `${formatted} profile currency` : `${formatted} ${item.unit ?? ''}`.trim()
}

function plainReason(action, month, context) {
  if (!month || !context) return action.reason
  const gap = Number(context.net_cash_flow)
  if (action.agent_id === 'budget' && gap < 0) return `Planned spending is ${money(-gap)} above this month's income. Review what can change.`
  if (action.agent_id === 'debt' && gap < 0) return `You still owe ${money(month.outstanding_debt)} and a payment of ${money(month.scheduled_emi)} is due while spending is above income.`
  if (action.agent_id === 'emergency' && Number(month.emergency_fund) === 0) return 'You recorded no savings set aside for unexpected costs.'
  return action.reason
}

export function MethodCard({ title, result, month, context }) {
  const partial = result.recommendation.status === 'partial'
  return <article className="monthly-demo-method">
    <div className="monthly-demo-method-head"><div><h4>{title}</h4>
      <p>{partial ? 'Partial specialist findings' : 'All checks needed for a full plan ran'}</p></div></div>
    <p className="research-small-label">CHECKS THIS METHOD RAN</p>
    <div className="research-agent-list">{result.selected_agents.map((id) =>
      <span key={id}>{agentNames[id] ?? id}</span>)}</div>
    {partial && <p className="monthly-demo-partial">This result is incomplete because it did not run {result.recommendation.plan_readiness.missing_agents.map(
      (id) => agentNames[id] ?? id).join(', ')}. The notes below cover only the checks shown above.</p>}
    <h5>What the checks found</h5>
    {result.priority_actions.length ? <ul className="monthly-demo-actions">{result.priority_actions.map((action) =>
      <li key={`${action.agent_id}-${action.finding_code ?? action.code}`}>
        <strong>{action.title}</strong><p>{plainReason(action, month, context)}</p>
        {action.evidence?.length > 0 && <details><summary>Why this was flagged and figures used</summary><p>{action.reason}</p><ul>{action.evidence.filter((item) => evidenceValue(item) !== null).map((item, index) =>
          <li key={`${item.label}-${index}`}>{item.label}: {evidenceValue(item)}</li>)}</ul></details>}
      </li>)}</ul> : <p>No priority finding was recorded by these selected specialists.</p>}
    {result.reward_audit.missed_critical_agents.length > 0 && <p className="monthly-demo-audit">Important check not run: {result.reward_audit.missed_critical_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
  </article>
}

export function MonthlyDemoCase({ demo, monthIndex, onMonthChange }) {
  const month = demo.months.find((item) => item.month_index === monthIndex) ?? demo.months[1]
  const previous = demo.months[0]
  const trained = month.methods.trained_rl
  const rule = month.methods.rule_based
  const newAgents = monthIndex === 2 ? trained.selected_agents.filter(
    (id) => !previous.methods.trained_rl.selected_agents.includes(id)) : []
  const change = Number(month.monthly_state.income_change_ratio)
  return <div className="monthly-demo-case">
    <div className="monthly-demo-months" role="group" aria-label="Synthetic month">
      {demo.months.map((item) => <button type="button" key={item.month_index}
        aria-pressed={item.month_index === monthIndex}
        onClick={() => onMonthChange(item.month_index)}>
        Month {item.month_index}{item.month_index === 1 ? ' · before drop' : ' · income drop'}
      </button>)}
    </div>
    <p className="monthly-demo-observation">Model inputs include this month's income, the recent change, and a configured income variability of {(Number(month.monthly_state.income_volatility) * 100).toFixed(0)}% for this synthetic scenario.</p>
    <div className="monthly-demo-state">
      <div><small>Monthly income</small><strong>{money(month.monthly_state.monthly_income)}</strong>
        {monthIndex === 2 && Number.isFinite(change) && <span>{Math.abs(change * 100).toFixed(1)}% below prior month</span>}</div>
      <div><small>Scheduled expenses</small><strong>{money(month.monthly_state.monthly_expenses)}</strong></div>
      <div><small>Debt payment</small><strong>{money(month.monthly_state.scheduled_emi)}</strong></div>
      <div><small>Emergency reserve</small><strong>{money(month.monthly_state.emergency_fund)}</strong></div>
    </div>
    {newAgents.length > 0 && <p className="monthly-demo-change">As income fell, the trained DQN changed its selection and added {newAgents.map(
      (id) => agentNames[id] ?? id).join(', ')}.</p>}
    <div className="monthly-demo-methods">
      <MethodCard title="Trained monthly DQN" result={trained} />
      <MethodCard title="Rule-based baseline" result={rule} />
    </div>
    <p className="monthly-demo-interpretation">The DQN ran {trained.selected_agents.length} checks and the fixed rule ran {rule.selected_agents.length}. Compare which findings they cover; this demonstration does not establish that either gives better financial advice.</p>
    <details className="monthly-demo-limits"><summary>Model source and limits</summary>
      <p>Held-out synthetic user {demo.source.synthetic_id}, scenario {demo.source.scenario}. Model {demo.source.model_version}; artifact {demo.source.artifact_sha256.slice(0, 12)}…</p>
      <ul>{demo.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
    </details>
  </div>
}

export default function MonthlyDemo({ userId }) {
  const [demo, setDemo] = useState(null)
  const [monthIndex, setMonthIndex] = useState(2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (loading) return
    setLoading(true); setError('')
    try { setDemo(await getMonthlyDemo(userId)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setLoading(false) }
  }

  return <section className="monthly-demo" aria-labelledby="monthly-demo-heading">
    <div className="monthly-demo-intro"><div>
      <p className="research-small-label">LIVE TRAINED-MODEL RESEARCH DEMO</p>
      <h3 id="monthly-demo-heading">A salaried worker's income falls</h3>
      <p>Run the saved monthly DQN and fixed rule on the same two generated months. See which specialists ran and the findings they produced. This example is separate from your account.</p>
    </div><button type="button" className="primary-action" disabled={loading} onClick={run}>
      {loading ? 'Running both methods…' : demo ? 'Run again' : 'Run monthly DQN demo'}
    </button></div>
    {loading && <p role="status">Loading the verified model and replaying the held-out case. The first run may take a few seconds.</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {demo && <MonthlyDemoCase demo={demo} monthIndex={monthIndex} onMonthChange={setMonthIndex} />}
  </section>
}
