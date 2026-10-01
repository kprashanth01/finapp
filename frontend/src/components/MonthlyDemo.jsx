import { useState } from 'react'
import { explainApiError, getMonthlyDemo } from '../services/api.js'

const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning',
  risk: 'Risk', investment: 'Investment readiness',
}

const scoreNames = {
  relevant_coverage: 'Relevant checks covered', critical_coverage: 'Critical checks covered',
  missed_critical_penalty: 'Missed critical checks', unneeded_agent_penalty: 'Unneeded specialists',
  agent_call_penalty: 'Specialist call cost',
}

const money = (value) => value == null ? 'Unavailable' : Number(value).toLocaleString('en-US', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})

export function MethodCard({ title, result }) {
  const partial = result.recommendation.status === 'partial'
  return <article className="monthly-demo-method">
    <div className="monthly-demo-method-head"><div><h4>{title}</h4>
      <p>{partial ? 'Partial specialist findings' : 'Complete coordinated plan available'}</p></div>
      <strong>{Number(result.reward).toFixed(2)} <small>proxy points</small></strong></div>
    <p className="research-small-label">SELECTED SPECIALISTS · ACTION {result.action}</p>
    <div className="research-agent-list">{result.selected_agents.map((id) =>
      <span key={id}>{agentNames[id] ?? id}</span>)}</div>
    {partial && <p className="monthly-demo-partial">A full coordinated plan needs {result.recommendation.plan_readiness.missing_agents.map(
      (id) => agentNames[id] ?? id).join(', ')}. The findings below come only from specialists that ran.</p>}
    <h5>What they advise reviewing</h5>
    {result.priority_actions.length ? <ul className="monthly-demo-actions">{result.priority_actions.map((action) =>
      <li key={`${action.agent_id}-${action.finding_code ?? action.code}`}>
        <strong>{action.title}</strong><p>{action.reason}</p>
        {action.evidence?.length > 0 && <details><summary>See recorded evidence</summary><ul>{action.evidence.map((item, index) =>
          <li key={`${item.label}-${index}`}>{item.label}: {item.value} {item.unit}</li>)}</ul></details>}
      </li>)}</ul> : <p>No priority finding was recorded by these selected specialists.</p>}
    <p className="monthly-demo-audit">Critical checks missed: {result.reward_audit.missed_critical_agents.length
      ? result.reward_audit.missed_critical_agents.map((id) => agentNames[id] ?? id).join(', ') : 'none under this proxy'}.</p>
    <details className="monthly-demo-breakdown"><summary>How this proxy score adds up</summary>
      <dl>{Object.entries(result.reward_components).map(([key, value]) => <div key={key}>
        <dt>{scoreNames[key] ?? key}</dt><dd>{Number(value).toFixed(2)}</dd>
      </div>)}</dl>
      <p>This audit scores agent selection. It does not reveal the neural network's internal reasoning.</p>
    </details>
  </article>
}

export function MonthlyDemoCase({ demo, monthIndex, onMonthChange }) {
  const month = demo.months.find((item) => item.month_index === monthIndex) ?? demo.months[1]
  const previous = demo.months[0]
  const trained = month.methods.trained_rl
  const rule = month.methods.rule_based
  const newAgents = monthIndex === 2 ? trained.selected_agents.filter(
    (id) => !previous.methods.trained_rl.selected_agents.includes(id)) : []
  const difference = Number(trained.reward) - Number(rule.reward)
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
    {difference > 0 && <p className="monthly-demo-interpretation">For this month, the DQN's selection proxy is {difference.toFixed(2)} points higher. It selected {trained.selected_agents.length} specialists versus {rule.selected_agents.length} for the fixed rule and missed {trained.reward_audit.missed_critical_agents.length} critical checks under this proxy. This does not establish better financial advice.</p>}
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
