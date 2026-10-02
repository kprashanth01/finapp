import { useState } from 'react'
import AdvisoryPlan from './AdvisoryPlan.jsx'
import ExplanationTrail from './ExplanationTrail.jsx'
import ReasoningPanel from './ReasoningPanel.jsx'
import { RewardAuditDetails } from './Research.jsx'
import { explainApiError, getAdviceApproaches, runOrchestration } from '../services/api.js'

const agentNames = {
  budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund',
  goal: 'Goal planning', risk: 'Risk assessment', investment: 'Investment',
}

const modes = [
  ['configured', 'Server default'], ['rule_based', 'Rule based'],
  ['random', 'Seeded random'], ['trained_rl', 'Trained RL'],
]

function ApproachCard({ title, approach }) {
  const complete = approach.status === 'complete'
  return <article className="rounded-xl border border-slate-200 bg-white p-4">
    <h4 className="font-semibold">{title}</h4>
    <p className="mt-1 text-xs text-slate-600">{complete ? 'All required checks ran' : approach.status === 'partial' ? 'Missing required checks' : 'Model unavailable'}</p>
    {complete && <div className="mt-3 text-sm">{approach.first_action
      ? <><p className="font-medium">First step: {approach.first_action.title}</p>
        <p className="mt-1 text-slate-700">{approach.first_action.text}</p></>
      : <><p className="font-medium">No priority action flagged.</p>
        <p className="mt-1 text-slate-700">{approach.detail}</p></>}</div>}
    {approach.status === 'partial' && <p className="mt-3 text-sm text-amber-900">Cannot show a complete model plan. Required checks missing: {approach.missing_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
    {approach.status === 'unavailable' && <p className="mt-3 text-sm text-slate-700">{approach.detail}</p>}
    {approach.selected_agents.length > 0 && <p className="mt-3 text-xs text-slate-600">Checks run: {approach.selected_agents.map((id) => agentNames[id] ?? id).join(', ')}.</p>}
  </article>
}

export function AdviceApproachResults({ result }) {
  return <div className="mt-4" aria-live="polite">
    <p className="text-sm text-slate-600">Both approaches used the same saved picture on {result.as_of_date}. This comparison was not saved.</p>
    <div className="mt-3 grid gap-3 md:grid-cols-2">
      <ApproachCard title="Standard plan" approach={result.rule_based} />
      <ApproachCard title="Experimental model" approach={result.trained_rl} />
    </div>
    <p className="mt-3 text-xs text-slate-600">The experimental model selects which checks run. Those checks use the same financial rules; the model was trained on generated examples, not this account. Use Run analysis above to save a current standard plan.</p>
  </div>
}

export function AdviceApproachPanel({ userId }) {
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function compare() {
    if (running) return
    setRunning(true); setError(''); setResult(null)
    try { setResult(await getAdviceApproaches(userId)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setRunning(false) }
  }

  return <section className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5" aria-labelledby="approaches-heading">
    <h3 id="approaches-heading" className="text-lg font-semibold">Compare planning approaches</h3>
    <p className="mt-1 text-sm text-slate-600">Compare the standard plan with an experimental model on your current saved profile. Your saved plan does not change.</p>
    <button type="button" disabled={running} onClick={compare} className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{running ? 'Comparing…' : 'Compare now'}</button>
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
    {result && <AdviceApproachResults result={result} />}
  </section>
}

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
