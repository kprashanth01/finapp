const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', goal: 'Goal planning',
  risk: 'Risk assessment', investment: 'Investment readiness',
}

const scoreNames = {
  relevant_coverage: 'Relevant checks', critical_coverage: 'Critical checks covered',
  missed_critical_penalty: 'Missed critical checks',
  unneeded_agent_penalty: 'Unneeded checks', agent_call_penalty: 'Agent call cost',
}

function metricText(item) {
  if (item.value == null) return `${item.label}: unavailable`
  if (item.unit === '%') return `${item.label}: ${item.value}%`
  if (item.unit === 'currency' || item.unit === 'profile currency') return `${item.label}: ${item.value} (profile currency)`
  return `${item.label}: ${item.value}${item.unit ? ` ${item.unit}` : ''}`
}

function RecommendationEvidence({ recommendation }) {
  const evidence = recommendation.findings.flatMap(({ agent_id, finding }) =>
    finding.evidence.map((item) => ({ ...item, agent_id })))
  const evidenceLabels = new Set(evidence.map((item) => item.label))
  const context = recommendation.context.filter((item) => !evidenceLabels.has(item.label)).slice(0, 5)
  return <>
    <p className="explanation-source">From {Array.from(new Set(recommendation.findings.map((item) => agentNames[item.agent_id] ?? item.agent_id))).join(' + ')}</p>
    <ul className="explanation-metrics">
      {evidence.map((item, index) => <li key={`${item.agent_id}-${item.label}-${index}`}>{metricText(item)}</li>)}
      {context.map((item) => <li key={item.key}>{metricText(item)}</li>)}
    </ul>
  </>
}

export default function ExplanationTrail({ trace }) {
  if (!trace) return null
  const selected = trace.selections.filter((item) => item.selected)
  const first = trace.recommendations[0]
  const total = Object.values(trace.reward_components).reduce((sum, amount) => sum + amount, 0)
  return <section className="explanation-trail" aria-labelledby="explanation-heading">
    <div className="explanation-heading"><div><p className="research-small-label">TRACEABLE RESULT</p>
      <h3 id="explanation-heading">How this result was reached</h3></div><span>Action {trace.action}</span></div>
    <div className="explanation-flow">
      <div className="explanation-step"><small>1 · Saved state</small>
        <p>These values were captured for this run. {first ? 'The numbers supporting the first finding appear below.' : 'No complete recommendation was produced.'}</p></div>
      <div className="explanation-step"><small>2 · Selection</small>
        <p>{trace.policy_explanation}</p>
        <p className="explanation-agent-line">Ran: {selected.map((item) => agentNames[item.agent_id] ?? item.agent_id).join(', ')}.</p></div>
      <div className="explanation-step"><small>3 · Finding → recommendation</small>
        {first ? <><strong>{first.title}</strong><p>{first.text}</p><RecommendationEvidence recommendation={first} /></>
          : <p>No priority finding was returned by the selected agents.</p>}
        {trace.missing_agents.length > 0 && <p className="explanation-missing">A complete plan needs {trace.missing_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}</div>
      <div className="explanation-step"><small>4 · Proxy score</small>
        <strong>{total.toFixed(2)} project points</strong>
        <p>Points reflect selected checks and call costs under this project's rules, not a financial outcome.</p></div>
    </div>
    <details className="explanation-details"><summary>Explore every selection, finding, and limit</summary>
      <h4>Why each agent ran or was skipped</h4>
      <div className="explanation-selections">{trace.selections.map((item) => <div key={item.agent_id}>
        <strong>{agentNames[item.agent_id] ?? item.agent_id} · {item.selected ? 'ran' : 'skipped'}</strong>
        <p>{item.basis}</p>
        <ul>{item.context.map((metric) => <li key={metric.key}>{metricText(metric)}</li>)}</ul>
      </div>)}</div>
      <h4>Recommendations and their agent findings</h4>
      {trace.recommendations.length ? <ol className="explanation-recommendations">{trace.recommendations.map((item, index) =>
        <li key={`${item.kind}-${index}`}><strong>{item.title}</strong><p>{item.text}</p>
          {item.findings.map(({ agent_id, finding }) => <div key={`${agent_id}-${finding.code}`} className="explanation-finding">
            <span>{agentNames[agent_id] ?? agent_id} · {finding.title}</span><p>{finding.reason}</p></div>)}
          <RecommendationEvidence recommendation={item} />
          {item.limitations.length > 0 && <p className="explanation-limit">{item.limitations.join(' ')}</p>}
        </li>)}</ol> : <p>No actionable finding was returned by this selection.</p>}
      <h4>Proxy reward components</h4>
      <dl className="explanation-score-list">{Object.entries(trace.reward_components).map(([name, value]) =>
        <div key={name}><dt>{scoreNames[name] ?? name}</dt><dd>{value > 0 ? '+' : ''}{value.toFixed(2)}</dd></div>)}</dl>
      <h4>Limits and missing information</h4>
      <ul className="explanation-limits">{trace.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      <p className="explanation-version">{trace.version} · Profile fingerprint {trace.state_fingerprint.slice(0, 12)}…</p>
    </details>
  </section>
}
