import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let EvaluationDashboardResults
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  EvaluationDashboardResults = (await server.ssrLoadModule('/src/components/EvaluationDashboard.jsx')).EvaluationDashboardResults
})
after(async () => { await server?.close() })

const evidence = {
  status: 'available',
  experiment: {
    id: 1, model_version: '3158475c12fd', scenario_version: 'coverage-scenarios-v1',
    source: 'generated cases', case_count: 256, recorded_at: '2026-10-01T09:00:00Z',
    limitations: { recommendation_consistency: 'not measured' },
  },
  scope: 'aggregate',
  rows: [{ run_id: 3, method: 'rl', scenario: 'overall', scope: 'aggregate', seed: null,
    case_count: 256, sample_count: 256, metric: 'mean_reward', value: 7.825 }],
  unmeasured_reason: null,
}

test('stored dashboard shows the recorded value and calls consistency unmeasured', () => {
  const text = renderToStaticMarkup(createElement(EvaluationDashboardResults, { evidence }))
    .replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
  assert.match(text, /Trained DQN/)
  assert.match(text, /7\.825/)
  assert.match(text, /256/)
  assert.match(text, /Recommendation consistency.*Not measured/i)
  assert.doesNotMatch(text, /RL is best/)
})

test('unmeasured metric gives a reason and no invented row', () => {
  const text = renderToStaticMarkup(createElement(EvaluationDashboardResults, {
    evidence: { ...evidence, rows: [],
      unmeasured_reason: 'Recommendation consistency was not measured. No validated definition exists.' },
  }))
  assert.match(text, /Recommendation consistency was not measured/)
  assert.doesNotMatch(text, /7\.825/)
})
