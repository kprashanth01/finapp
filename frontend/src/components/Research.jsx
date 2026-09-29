import { useState } from 'react'
import { compareResearchPolicies, explainApiError } from '../services/api.js'

const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning',
  risk: 'Risk', investment: 'Investment readiness',
}

const scoreNames = {
  relevant_coverage: 'Relevant checks covered',
  critical_coverage: 'Critical needs covered',
  missed_critical_penalty: 'Missed critical needs',
  unneeded_agent_penalty: 'Unneeded checks',
  agent_call_penalty: 'Agent call cost',
}

function PolicyResult({ title, explanation, outcome }) {
  return <article className="research-result">
    <div className="research-result-head"><div><h3>{title}</h3><p>{explanation}</p></div><strong>{outcome.total_reward.toFixed(2)} <small>points</small></strong></div>
    <p className="research-small-label">AGENTS SELECTED</p>
    <div className="research-agent-list">{outcome.selected_agents.map((id) => <span key={id}>{agentNames[id] ?? id}</span>)}</div>
    <details className="research-details"><summary>See score and findings</summary>
      <dl className="research-score-list">{Object.entries(outcome.reward_components).map(([key, value]) => <div key={key}><dt>{scoreNames[key] ?? key}</dt><dd>{value > 0 ? '+' : ''}{value.toFixed(2)}</dd></div>)}</dl>
      <div className="research-findings">{outcome.findings.map((finding, index) => <p key={`${finding.agent_id}-${index}`}><strong>{finding.title}:</strong> {finding.reason}</p>)}</div>
    </details>
  </article>
}

function Benchmark({ training }) {
  const benchmark = training.held_out_benchmark
  if (!benchmark) return null
  const labels = { learned: 'Trained selector', rule: 'Rule-based', random: 'Random', oracle: 'Best proxy score' }
  return <section className="research-benchmark" aria-labelledby="benchmark-heading">
    <h3 id="benchmark-heading">How it did on separate test cases</h3>
    <p>{benchmark.case_count} generated cases were kept out of training. These scores measure the project’s own selection rules, not financial outcomes.</p>
    <div className="research-table-scroll"><table>
      <thead><tr><th scope="col">Method</th><th scope="col">Average score</th><th scope="col">Cases with a missed critical check</th><th scope="col">Average agents</th></tr></thead>
      <tbody>{Object.entries(benchmark.policies).map(([key, result]) => <tr key={key}>
        <th scope="row">{labels[key] ?? key}</th><td>{result.mean_reward.toFixed(2)}</td>
        <td>{(result.critical_miss_rate * 100).toFixed(1)}%</td><td>{result.mean_agent_calls.toFixed(1)}</td>
      </tr>)}</tbody>
    </table></div>
    <p className="research-benchmark-note">The rule-based method defines most of the reward, so this benchmark cannot establish that the trained selector gives better advice. “Best proxy score” is an upper bound for these cases.</p>
  </section>
}

export default function Research({ userId, hasProfile, onOpenProfile }) {
  const [comparison, setComparison] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (running) return
    setRunning(true); setError('')
    try { setComparison(await compareResearchPolicies(userId)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setRunning(false) }
  }

  return <section className="research-page" aria-labelledby="research-heading">
    <div className="research-intro"><div><h2 id="research-heading">Agent selection, explained</h2>
      <p>Compare the trained selector with the rule-based and random methods on your current saved profile.</p></div>
      {hasProfile ? <button type="button" className="primary-action" onClick={run} disabled={running}>{running ? 'Comparing…' : comparison ? 'Run comparison again' : 'Compare methods'}</button>
        : <button type="button" className="primary-action" onClick={onOpenProfile}>Create a profile</button>}
    </div>
    <div className="research-explainer"><strong>What this score means</strong><p>The score rewards relevant and critical checks, then subtracts points for missed needs and extra agent calls. It does not measure a change in your finances or prove that one method gives better advice.</p></div>
    {!hasProfile && <p className="research-empty">Add a financial profile first. This comparison uses your saved values; it does not create a demo account.</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {comparison && <><p className="research-meta">Based on your saved profile as of {comparison.as_of_date}. Seed {comparison.seed}. No advisory session was saved.</p>
      {comparison.model.status === 'available' ? <><div className="research-results">
        <PolicyResult title="Trained selector" explanation="A one-step model fitted to the project’s proxy score." outcome={comparison.policies.learned} />
        <PolicyResult title="Rule-based selection" explanation="The app’s current, explicit selection logic." outcome={comparison.policies.rule} />
        <PolicyResult title="Random baseline" explanation="A seeded comparison point." outcome={comparison.policies.random} />
      </div><Benchmark training={comparison.model.training} /></> : <><p className="research-error" role="status">{comparison.model.reason}</p>
        <div className="research-results"><PolicyResult title="Rule-based selection" explanation="The app’s current, explicit selection logic." outcome={comparison.policies.rule} />
          <PolicyResult title="Random baseline" explanation="A seeded comparison point." outcome={comparison.policies.random} /></div></>}
      <p className="research-footnote">The Advisor continues to use the complete rule-based plan. This comparison does not save an advisory session or change your profile.</p></>}
  </section>
}
