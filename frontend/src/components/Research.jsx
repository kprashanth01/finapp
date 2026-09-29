import { useEffect, useState } from 'react'
import {
  compareResearchPolicies, explainApiError, getResearchActions, getResearchTrainingEvidence,
  runManualResearchAction,
} from '../services/api.js'

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

function checkValueText(check) {
  if (check.input_status === 'not_applicable') return 'Not applicable.'
  const criterion = check.unit === 'months' ? `Critical below ${check.threshold} months.`
    : check.unit === '%' ? `Critical at ${check.threshold}% or above (or when debt exists and the ratio is unavailable).`
      : 'Critical when at least one goal is unfinished.'
  if (check.input_status === 'unavailable') return `Unavailable. ${criterion}`
  const value = check.unit === 'goals'
    ? `${check.value} unfinished ${check.value === '1' ? 'goal' : 'goals'}`
    : check.unit === '%' ? `${check.value}%` : `${check.value} ${check.unit}`
  return `${value}. ${criterion}`
}

export function RewardAuditDetails({ audit, collapsible = false }) {
  const content = <>
    <dl className="research-score-list">{Object.entries(audit.components).map(([key, value]) => <div key={key}>
      <dt>{scoreNames[key] ?? key}</dt><dd>{value > 0 ? '+' : ''}{value.toFixed(2)}</dd>
    </div>)}</dl>
    <p>Relevant under this project score: {audit.relevant_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>
    {audit.missed_critical_agents.length > 0 && <p>Missed critical checks: {audit.missed_critical_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
    {audit.unneeded_agents.length > 0 && <p>Unneeded checks under this score: {audit.unneeded_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
    <ul className="research-audit-checks">{audit.checks.map((check) => <li key={check.agent_id}>
      <strong>{check.label}</strong>{' '}
      <span>{checkValueText(check)}</span>
      {check.critical && <span className="research-audit-status">{check.selected
        ? `Covered critical check: ${agentNames[check.agent_id] ?? check.agent_id}`
        : `Missed critical check: ${agentNames[check.agent_id] ?? check.agent_id}`}</span>}
      <p>{check.note}</p>
    </li>)}</ul>
    <p className="research-audit-caveat">This proxy score does not measure financial improvement or prove which method gives better advice.</p>
  </>
  return collapsible
    ? <details className="research-score-audit"><summary>Why this score?</summary>{content}</details>
    : <div className="research-score-audit"><h4>Why this score?</h4>{content}</div>
}

function PolicyResult({ title, explanation, outcome }) {
  return <article className="research-result">
    <div className="research-result-head"><div><h3>{title}</h3><p>{explanation}</p></div><strong>{outcome.total_reward.toFixed(2)} <small>points</small></strong></div>
    <p className="research-small-label">AGENTS SELECTED</p>
    <div className="research-agent-list">{outcome.selected_agents.map((id) => <span key={id}>{agentNames[id] ?? id}</span>)}</div>
    <details className="research-details"><summary>See score and findings</summary>
      <RewardAuditDetails audit={outcome.reward_audit} />
      <div className="research-findings">{outcome.findings.map((finding, index) => <p key={`${finding.agent_id}-${index}`}><strong>{finding.title}:</strong> {finding.reason}</p>)}</div>
    </details>
  </article>
}

function Benchmark({ training }) {
  const benchmark = training.held_out_benchmark
  if (!benchmark) return null
  const labels = { learned: 'Fitted proxy selector', rule: 'Rule-based', random: 'Random', oracle: 'Best proxy score' }
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

export function TrainingEvidenceCard({ evidence }) {
  if (!evidence) return <section className="research-training" aria-label="DQN training evidence"><p role="status">Loading RL training evidence…</p></section>
  if (evidence.status !== 'available') return <section className="research-training" aria-label="DQN training evidence">
    <h3>RL training evidence</h3><p role="status">{evidence.reason}</p>
  </section>
  const run = evidence.metadata
  const count = (value) => Number(value).toLocaleString('en-US')
  return <section className="research-training" aria-labelledby="training-evidence-heading">
    <div className="research-training-head"><div>
      <p className="research-small-label">OFFLINE EXPERIMENT</p>
      <h3 id="training-evidence-heading">How the RL selector was trained</h3>
    </div><span>{run.algorithm} · {run.model_version}</span></div>
    <p>A neural selector learned from actions and rewards in generated financial scenarios. The cases were split into {count(run.split_counts.training)} training, {count(run.split_counts.validation)} validation, and {count(run.split_counts.test)} held-out test cases.</p>
    <div className="research-training-summary">
      <div><small>Chosen checkpoint</small><strong>{count(run.selected_step)} steps</strong><span>Selected on validation cases</span></div>
      <div><small>Held-out proxy score</small><strong>{run.test.mean_reward.toFixed(2)}</strong><span>Across {count(run.test.case_count)} new cases</span></div>
      <div><small>Missed critical checks</small><strong>{(run.test.critical_miss_rate * 100).toFixed(1)}%</strong><span>Under this project's reward rule</span></div>
    </div>
    <details className="research-training-details"><summary>See validation progression and limits</summary>
      <div className="research-table-scroll"><table>
        <thead><tr><th scope="col">Training step</th><th scope="col">Validation proxy score</th><th scope="col">Missed critical checks</th></tr></thead>
        <tbody>{run.validation_history.map((row) => <tr key={row.step}>
          <th scope="row">{count(row.step)}</th><td>{row.mean_reward.toFixed(2)}</td>
          <td>{(row.critical_miss_rate * 100).toFixed(1)}%</td>
        </tr>)}</tbody>
      </table></div>
    </details>
    <p className="research-training-limit">Each episode makes one agent-selection decision. This is a one-step experiment using a rule-defined proxy reward, not evidence of improved financial outcomes. You can now run the trained DQN in Advisor's experimental selector; the comparison below still uses the earlier fitted proxy selector.</p>
  </section>
}

function ManualExperiment({ userId }) {
  const [catalog, setCatalog] = useState(null)
  const [selected, setSelected] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setCatalog(null); setSelected([]); setResult(null); setError(''); setLoading(true)
    getResearchActions(userId).then((actions) => { if (active) setCatalog(actions) })
      .catch((requestError) => { if (active) setError(explainApiError(requestError)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userId])

  function toggle(agentId) {
    setSelected((current) => current.includes(agentId) ? current.filter((id) => id !== agentId) : [...current, agentId])
    setResult(null)
  }

  async function run(event) {
    event.preventDefault()
    if (running || !selected.length) return
    setRunning(true); setError(''); setResult(null)
    try { setResult(await runManualResearchAction(userId, selected)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setRunning(false) }
  }

  return <details className="research-manual">
    <summary>Try your own agent selection</summary>
    <p>Choose specialists to run on your saved profile. This shows their findings without changing your profile or saving an Advisor plan.</p>
    {loading && <p role="status">Loading available agents…</p>}
    {error && <p className="research-error" role="alert">{error}</p>}
    {catalog && <form onSubmit={run}>
      <fieldset disabled={running}><legend>Select at least one agent</legend>
        <div className="research-manual-choices">{catalog.agents.map((id) => <label key={id}>
          <input type="checkbox" checked={selected.includes(id)} onChange={() => toggle(id)} />
          <span>{agentNames[id] ?? id}</span>
        </label>)}</div>
      </fieldset>
      <button type="submit" className="primary-action" disabled={running || selected.length === 0}>
        {running ? 'Running…' : 'Run selected agents'}
      </button>
      <small>{catalog.action_count} available combinations · Action version {catalog.action_version}</small>
    </form>}
    {result && <div className="research-manual-result" aria-live="polite">
      <h3>Action ID {result.action}: {result.selected_agents.map((id) => agentNames[id] ?? id).join(', ')}</h3>
      <p className={result.plan_readiness.can_build_full_plan ? 'research-ready' : 'research-incomplete'}>
        {result.plan_readiness.can_build_full_plan
          ? 'This selection includes the agents needed for a complete Advisor plan. This experiment did not generate or save one.'
          : `A complete Advisor plan also needs: ${result.plan_readiness.missing_agents.map((id) => agentNames[id] ?? id).join(', ')}.`}
      </p>
      <p>Selection score: <strong>{result.total_reward.toFixed(2)}</strong> project points. This score does not measure financial improvement.</p>
      <RewardAuditDetails audit={result.reward_audit} collapsible />
      <div className="research-manual-findings">{result.agent_results.map((agent) => <section key={agent.agent_id}>
        <h4>{agentNames[agent.agent_id] ?? agent.agent_id}</h4>
        {agent.findings.length ? agent.findings.map((finding) => <div key={finding.code}>
          <strong>{finding.title}</strong><p>{finding.reason}</p>
          {finding.evidence?.length > 0 && <ul>{finding.evidence.map((item, index) => <li key={index}>
            {item.label}: {item.value}{item.unit ? ` ${item.unit}` : ''}
          </li>)}</ul>}
        </div>) : <p>No findings returned.</p>}
      </section>)}</div>
    </div>}
  </details>
}

export default function Research({ userId, hasProfile, onOpenProfile }) {
  const [comparison, setComparison] = useState(null)
  const [trainingEvidence, setTrainingEvidence] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [seed, setSeed] = useState('42')

  useEffect(() => {
    let active = true
    setTrainingEvidence(null)
    getResearchTrainingEvidence(userId)
      .then((value) => { if (active) setTrainingEvidence(value) })
      .catch((requestError) => { if (active) setTrainingEvidence({ status: 'unavailable', reason: explainApiError(requestError) }) })
    return () => { active = false }
  }, [userId])

  async function run(event) {
    event.preventDefault()
    if (running) return
    setRunning(true); setError('')
    try { setComparison(await compareResearchPolicies(userId, Number(seed))) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setRunning(false) }
  }

  return <section className="research-page" aria-labelledby="research-heading">
    <div className="research-intro"><div><h2 id="research-heading">Agent selection, explained</h2>
      <p>Inspect the DQN training run, then compare the earlier fitted proxy selector with rule-based and random methods on your saved profile.</p></div>
      {hasProfile ? <form className="research-compare-controls" onSubmit={run}>
        <label>Random seed<input type="number" min="0" max="1000000000" step="1" required value={seed}
          onChange={(event) => setSeed(event.target.value)} /></label>
        <button type="submit" className="primary-action" disabled={running}>{running ? 'Comparing…' : comparison ? 'Run comparison again' : 'Compare methods'}</button>
      </form>
        : <button type="button" className="primary-action" onClick={onOpenProfile}>Create a profile</button>}
    </div>
    <div className="research-explainer"><strong>What this score means</strong><p>The score rewards relevant and critical checks, then subtracts points for missed needs and extra agent calls. It does not measure a change in your finances or prove that one method gives better advice.</p></div>
    <TrainingEvidenceCard evidence={trainingEvidence} />
    {!hasProfile && <p className="research-empty">Add a financial profile first. This comparison uses your saved values; it does not create a demo account.</p>}
    {hasProfile && <ManualExperiment userId={userId} />}
    {error && <p role="alert" className="research-error">{error}</p>}
    {comparison && <><p className="research-meta">Based on your saved profile as of {comparison.as_of_date}. Seed {comparison.seed}. No advisory session was saved.</p>
      {comparison.model.status === 'available' ? <><div className="research-results">
        <PolicyResult title="Fitted proxy selector" explanation="This earlier fitted model predicts all action scores. The score audit explains the points, not the model’s internal cause." outcome={comparison.policies.learned} />
        <PolicyResult title="Rule-based selection" explanation="The app’s explicit selection logic; the score uses overlapping conditions." outcome={comparison.policies.rule} />
        <PolicyResult title="Random baseline" explanation={`A repeatable random choice using seed ${comparison.seed}.`} outcome={comparison.policies.random} />
      </div><Benchmark training={comparison.model.training} /></> : <><p className="research-error" role="status">{comparison.model.reason}</p>
        <div className="research-results"><PolicyResult title="Rule-based selection" explanation="The app’s explicit selection logic; the score uses overlapping conditions." outcome={comparison.policies.rule} />
          <PolicyResult title="Random baseline" explanation={`A repeatable random choice using seed ${comparison.seed}.`} outcome={comparison.policies.random} /></div></>}
      <p className="research-footnote">The saved Advisor plan remains rule based. Advisor also offers read-only experimental mode runs, including the trained DQN. This comparison does not save an advisory session or change your profile.</p></>}
  </section>
}
