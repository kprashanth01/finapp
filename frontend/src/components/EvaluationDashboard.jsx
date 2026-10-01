import { useEffect, useState } from 'react'
import { explainApiError, getResearchMeasurements } from '../services/api.js'

const methodLabels = { random: 'Seeded random', rule_based: 'Rule based', rl: 'Trained DQN' }
const scenarioLabels = {
  overall: 'All generated cases',
  low_reserve: 'Reserve below 3 months',
  high_or_unknown_debt_payment: 'High or unknown debt payment',
  unfinished_goal: 'Unfinished goal',
  expenses_at_or_above_income: 'Expenses at or above income',
}
const metricLabels = {
  mean_reward: 'Mean proxy reward', reward_variance: 'Reward variance',
  risk_coverage_rate: 'Risk check selected', goal_alignment_rate: 'Goal check on unfinished goals',
  recommendation_consistency: 'Recommendation consistency',
  recommendation_conflicts: 'Recommendation conflicts',
  mean_agent_calls: 'Average agents selected', mean_execution_ms: 'Mean execution time',
  critical_miss_rate: 'Missed critical check', relevant_coverage_rate: 'Relevant checks covered',
  full_plan_rate: 'Full plan possible', goal_case_count: 'Cases with unfinished goals',
}

const initialFilters = { method: '', scenario: 'overall', metric: 'mean_reward', scope: 'aggregate' }
const labelFor = (labels, key) => labels[key] ?? key.replaceAll('_', ' ')

function measuredValue(row) {
  const raw = Number(row.value).toLocaleString('en-US', { maximumFractionDigits: 6 })
  if (row.metric.endsWith('_rate')) return <>{raw} <small>({(row.value * 100).toFixed(2)}%)</small></>
  if (row.metric === 'mean_execution_ms') return <>{raw} <small>ms</small></>
  return raw
}

export function EvaluationDashboardResults({ evidence }) {
  if (evidence.status !== 'available') return <p role="status">{evidence.reason}</p>
  return <>
    <p className="research-metrics-provenance">
      Experiment #{evidence.experiment.id} · {evidence.experiment.case_count} generated cases · imported {new Date(evidence.experiment.recorded_at).toLocaleString()}.
      {evidence.scope === 'seed' ? ' Individual random seeds are shown.' : ' Aggregate measurements are shown.'}
    </p>
    {evidence.experiment.limitations?.recommendation_consistency === 'not measured' &&
      <p className="research-metrics-unmeasured"><strong>Recommendation consistency:</strong> Not measured in this experiment. The source has no validated comparison of recommendations.</p>}
    {evidence.rows.length ? <div className="research-table-scroll research-metrics-table"><table>
      <thead><tr><th scope="col">Method</th><th scope="col">Scenario</th><th scope="col">Metric</th>
        <th scope="col">Stored value</th><th scope="col">Cases</th><th scope="col">Selections</th><th scope="col">Run</th></tr></thead>
      <tbody>{evidence.rows.map((row) => <tr key={`${row.run_id}:${row.metric}`}>
        <th scope="row">{labelFor(methodLabels, row.method)}</th>
        <td>{labelFor(scenarioLabels, row.scenario)}</td>
        <td>{labelFor(metricLabels, row.metric)}</td>
        <td className="research-metrics-value"><data value={row.value}>{measuredValue(row)}</data></td>
        <td>{row.case_count}</td><td>{row.sample_count}</td>
        <td>{row.scope === 'seed' ? `Seed ${row.seed}` : 'Aggregate'}</td>
      </tr>)}</tbody>
    </table></div> : <p role="status" className="research-metrics-empty">
      {evidence.unmeasured_reason || 'No measurement was recorded for this filter combination.'}
    </p>}
    <p className="research-metrics-note">Scenario groups overlap. The random aggregate pools five seeds, so its selection count exceeds its unique case count. These values use the project’s proxy reward and generated cases; they do not measure financial improvement or establish a best method. Execution time is machine-specific.</p>
    <details className="research-metrics-details"><summary>Experiment provenance and metric definitions</summary>
      <p>Scenario version: <code>{evidence.experiment.scenario_version}</code>. Model checksum: <code>{evidence.experiment.model_version}</code>.</p>
      <p>Source: {evidence.experiment.source}. The recorded timestamp is when the report was imported; the source does not record measurement time.</p>
      <dl>{Object.entries(evidence.experiment.metric_definitions ?? {}).map(([name, definition]) => <div key={name}>
        <dt>{labelFor(metricLabels, name)}</dt><dd>{definition}</dd>
      </div>)}</dl>
    </details>
  </>
}

export default function EvaluationDashboard({ userId }) {
  const [filters, setFilters] = useState(initialFilters)
  const [evidence, setEvidence] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    getResearchMeasurements(userId, filters, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setEvidence(value) })
      .catch((requestError) => {
        if (!controller.signal.aborted) setError(explainApiError(requestError))
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [userId, filters])

  const options = evidence?.status === 'available' ? evidence.filters : null
  function change(name, value) {
    setFilters((current) => ({
      ...current, [name]: value,
      ...((name === 'scenario' && value !== 'overall') ||
        (name === 'method' && value !== '' && value !== 'random') ? { scope: 'aggregate' } : {}),
    }))
  }

  return <section className="research-metrics" aria-labelledby="research-metrics-heading">
    <p className="research-small-label">RECORDED EXPERIMENT</p>
    <h3 id="research-metrics-heading">Explore measured results</h3>
    <p>Filter the imported experiment by method, scenario, and metric. Every value below comes from a recorded research run.</p>
    {options && <div className="research-metrics-controls">
      <label>Method<select value={filters.method} onChange={(event) => change('method', event.target.value)}>
        <option value="">All methods</option>
        {options.methods.map((name) => <option key={name} value={name}>{labelFor(methodLabels, name)}</option>)}
      </select></label>
      <label>Scenario<select value={filters.scenario} onChange={(event) => change('scenario', event.target.value)}>
        <option value="">All scenarios</option>
        {options.scenarios.map((name) => <option key={name} value={name}>{labelFor(scenarioLabels, name)}</option>)}
      </select></label>
      <label>Metric<select value={filters.metric} onChange={(event) => change('metric', event.target.value)}>
        <option value="">All measured metrics</option>
        {options.metrics.map((item) => <option key={item.name} value={item.name}>
          {labelFor(metricLabels, item.name)}{item.available ? '' : ' · not measured'}
        </option>)}
      </select></label>
      <label>Result set<select value={filters.scope} onChange={(event) => change('scope', event.target.value)}>
        <option value="aggregate">Aggregates</option>
        <option value="seed" disabled={filters.scenario !== 'overall' || (filters.method !== '' && filters.method !== 'random')}>
          Individual random seeds
        </option>
      </select></label>
    </div>}
    {loading && <p role="status">Loading stored measurements…</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {!loading && !error && evidence && <EvaluationDashboardResults evidence={evidence} />}
  </section>
}
