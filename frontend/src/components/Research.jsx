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
      <p>See which specialists two baseline methods would run for your current saved profile. The same profile is used for both.</p></div>
      {hasProfile ? <button type="button" className="primary-action" onClick={run} disabled={running}>{running ? 'Comparing…' : comparison ? 'Run comparison again' : 'Compare methods'}</button>
        : <button type="button" className="primary-action" onClick={onOpenProfile}>Create a profile</button>}
    </div>
    <div className="research-explainer"><strong>What this score means</strong><p>The score rewards relevant and critical checks, then subtracts points for missed needs and extra agent calls. It does not measure a change in your finances or prove that one method gives better advice.</p></div>
    {!hasProfile && <p className="research-empty">Add a financial profile first. This comparison uses your saved values; it does not create a demo account.</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {comparison && <><p className="research-meta">Based on your saved profile as of {comparison.as_of_date}. Seed {comparison.seed}. No advisory session was saved.</p>
      <div className="research-results"><PolicyResult title="Rule-based selection" explanation="The app’s current, explicit selection logic." outcome={comparison.policies.rule} />
        <PolicyResult title="Random baseline" explanation="A seeded comparison point for later model evaluation." outcome={comparison.policies.random} /></div>
      <p className="research-footnote">A trained RL policy will be compared with these baselines in the next research milestone. The Advisor continues to use the complete rule-based plan.</p></>}
  </section>
}
