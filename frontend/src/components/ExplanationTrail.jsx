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

function RecommendationBreakdown({ recommendation, trace }) {
  const detail = recommendation.explainability
  const agents = detail?.agents ?? Array.from(new Set(recommendation.findings.map((item) => item.agent_id)))
  const linked = recommendation.findings.flatMap(({ finding }) => finding.evidence)
  const labels = new Set(linked.map((item) => item.label))
  const metrics = detail?.evidence ?? [...linked, ...recommendation.context.filter((item) => !labels.has(item.label))]
  const bases = trace.selections.filter((item) => agents.includes(item.agent_id))
  const orchestration = detail?.orchestration ?? `${trace.policy_explanation} ${bases.map((item) => `${agentNames[item.agent_id] ?? item.agent_id}: ${item.basis}`).join(' ')}`
  const limits = detail?.limitations ?? recommendation.limitations
  return <dl className="mt-3 space-y-2 text-sm">
    <div><dt className="font-semibold">What</dt><dd>{detail?.what ?? `${recommendation.title}: ${recommendation.text}`}</dd></div>
    <div><dt className="font-semibold">Why</dt><dd>{detail?.why ?? recommendation.findings.map(({ finding }) => finding.reason).join(' ')}</dd></div>
    <div><dt className="font-semibold">Evidence</dt><dd>{metrics.length ? <ul className="explanation-metrics">{metrics.map((item, index) =>
      <li key={`${item.key ?? item.label}-${index}`}>{metricText(item)}</li>)}</ul> : 'No supporting metric was recorded.'}</dd></div>
    <div><dt className="font-semibold">Agents</dt><dd className="explanation-source">From {agents.map((id) => agentNames[id] ?? id).join(' + ')}</dd></div>
    <div><dt className="font-semibold">Orchestration</dt><dd>{orchestration}</dd></div>
    <div><dt className="font-semibold">Limitations</dt><dd>{limits.length ? <ul>{limits.map((item, index) => <li key={index}>{item}</li>)}</ul> : 'No additional limitation was recorded for this recommendation.'}</dd></div>
  </dl>
}

export default function ExplanationTrail({ trace }) {
  if (!trace) return null
  const selected = trace.selections.filter((item) => item.selected)
  const first = trace.recommendations[0]
  const total = Object.values(trace.reward_components).reduce((sum, amount) => sum + amount, 0)
  return <section className="explanation-trail" aria-labelledby="explanation-heading">
    <div className="explanation-heading"><h3 id="explanation-heading">How this result was reached</h3></div>
    <div className="explanation-flow">
      <div className="explanation-step"><small>1 · Current financial state</small>
        <p>These values were captured for this run. {first ? 'The metrics supporting the recommendation appear below.' : 'No complete recommendation was produced.'}</p></div>
      <div className="explanation-step"><small>2 · Agent analysis</small>
        <p>{trace.policy_explanation}</p>
        <p className="explanation-agent-line">Ran: {selected.map((item) => agentNames[item.agent_id] ?? item.agent_id).join(', ')}.</p></div>
      <div className="explanation-step"><small>3 · Recommendation</small>
        {first ? <><strong>{first.title}</strong><p>{first.text}</p><details className="explanation-recommendation-details"><summary>Why this recommendation?</summary><RecommendationBreakdown recommendation={first} trace={trace} /></details></>
          : <p>No priority finding was returned by the selected agents.</p>}
        {trace.missing_agents.length > 0 && <p className="explanation-missing">A complete plan needs {trace.missing_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}</div>
    </div>
    <details className="explanation-details"><summary>Explore every selection, finding, and limit</summary>
      <p>Action {trace.action}. Reward: <strong>{total.toFixed(2)} project points</strong>. Points reflect selected checks and call costs under this project's rules, not a financial outcome.</p>
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
          <RecommendationBreakdown recommendation={item} trace={trace} />
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
