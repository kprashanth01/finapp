import { useState } from 'react'
import AdvisoryPlan from './AdvisoryPlan.jsx'
import ExplanationTrail from './ExplanationTrail.jsx'
import ReasoningPanel from './ReasoningPanel.jsx'
import { RewardAuditDetails } from './Research.jsx'
import { explainApiError, runOrchestration } from '../services/api.js'

const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund',
  goal: 'Goal planning', risk: 'Risk assessment', investment: 'Investment',
}

const modes = [
  ['configured', 'Server default'], ['rule_based', 'Rule based'],
  ['random', 'Seeded random'], ['trained_rl', 'Trained RL'],
]

function evidenceText(item) {
  if (item.value == null) return `${item.label}: unavailable`
  if (item.unit === '%') return `${item.label}: ${item.value}%`
  if (item.unit === 'currency') return `${item.label}: ${item.value} (profile currency)`
  return `${item.label}: ${item.value}${item.unit ? ` ${item.unit}` : ''}`
}

export function OrchestrationResult({ result, userId, onOpenProfile = () => {}, onOpenGoal = () => {} }) {
  const complete = result.plan_readiness.can_build_full_plan
  return <div className="orchestration-result" aria-live="polite">
    <div className="orchestration-result-head">
      <div><p className="research-small-label">{result.mode === 'rl' ? 'Trained RL' : modes.find(([id]) => id === result.mode)?.[1]} · Action {result.action}</p>
        <h3>{result.summary.title}</h3><p>{result.summary.text}</p></div>
      <div className="orchestration-score"><strong>{result.total_reward.toFixed(2)}</strong><span>proxy points</span></div>
    </div>
    <details className="orchestration-meta"><summary>Run details</summary><p>Saved profile as of {result.as_of_date} · {result.policy_version} · Action catalogue {result.action_version}</p></details>
    <ExplanationTrail trace={result.explanation} />
    {result.explanation && userId != null && <ReasoningPanel key={`${result.state_fingerprint}:${result.mode}:${result.action}:${result.seed}`} userId={userId} liveResult={result} />}
    {!result.explanation && <div className="orchestration-selected"><h4>Agents that ran</h4>
      <ul>{result.selected_agents.map((id) => <li key={id}>{agentNames[id] ?? id}</li>)}</ul></div>
    }
    {!complete && <p className="orchestration-partial">A complete monthly plan was withheld. It also needs: {result.plan_readiness.missing_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
    <details className="orchestration-findings"><summary>All raw agent findings</summary>
      {result.agent_results.map((agent) => <section key={agent.agent_id}>
        <h5>{agentNames[agent.agent_id] ?? agent.agent_id}</h5>
        {agent.findings.length ? agent.findings.map((finding) => <div key={finding.code}>
          <strong>{finding.title}</strong><p>{finding.reason}</p>
          {finding.evidence?.length > 0 && <ul>{finding.evidence.map((item, index) => <li key={index}>{evidenceText(item)}</li>)}</ul>}
        </div>) : <p>No finding returned from this agent.</p>}
        {agent.limitations?.map((limit) => <p key={limit} className="orchestration-limit">{limit}</p>)}
      </section>)}
    </details>
    {complete && result.advice && <details className="orchestration-plan"><summary>See coordinated plan from these agents</summary>
      <AdvisoryPlan result={result} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} showExplanation={false} /></details>}
    <RewardAuditDetails audit={result.reward_audit} collapsible />
    <p className="orchestration-disclaimer">This experimental run is not saved. The score follows project rules and does not measure financial improvement or prove advice quality.</p>
  </div>
}

export default function OrchestrationLab({ userId, onOpenProfile, onOpenGoal }) {
  const [mode, setMode] = useState('configured')
  const [seed, setSeed] = useState('42')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function run(event) {
    event.preventDefault()
    if (running) return
    setRunning(true); setError(''); setResult(null)
    try { setResult(await runOrchestration(userId, mode, Number(seed))) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setRunning(false) }
  }

  return <details className="orchestration-lab">
    <summary>Compare agent selection methods (research)</summary>
    <div><h2>Choose how agents are selected</h2>
      <p>Run a method on your saved profile. The result can differ from your saved monthly plan. Experimental runs are not saved in history.</p></div>
    <form onSubmit={run} className="orchestration-controls">
      <label>Selection method<select value={mode} disabled={running} onChange={(event) => { setMode(event.target.value); setResult(null); setError('') }}>
        {modes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {mode === 'random' && <label>Random seed<input type="number" min="0" max="1000000000" step="1" required value={seed} disabled={running} onChange={(event) => setSeed(event.target.value)} /></label>}
      <button className="primary-action" type="submit" disabled={running}>{running ? 'Running…' : 'Run selected method'}</button>
    </form>
    {mode === 'configured' && <p className="orchestration-mode-note">Server default uses the method configured for this app. The result shows which policy ran; a complete plan appears only when all required checks ran.</p>}
    {mode === 'trained_rl' && <p className="orchestration-mode-note">Trained RL uses the committed DQN model. It may choose fewer agents, so a complete monthly plan is shown only when all required checks ran.</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {result && <OrchestrationResult result={result} userId={userId} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} />}
  </details>
}
