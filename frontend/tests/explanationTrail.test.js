import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ExplanationTrail
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ExplanationTrail = (await server.ssrLoadModule('/src/components/ExplanationTrail.jsx')).default
})
after(async () => { await server?.close() })

const trace = {
  version: 'explanation-v1', method: 'rl', action: 5, seed: null,
  state_fingerprint: '1234567890abcdef',
  policy_explanation: 'The DQN predicted action 5. Saved values are context, not causal feature attribution.',
  selections: [
    { agent_id: 'emergency', selected: true, basis: 'Selected by DQN; individual feature influence is unavailable.',
      context: [{ key: 'emergency_fund_months', label: 'Emergency fund coverage', value: '1.33', unit: 'months' }] },
    { agent_id: 'budget', selected: false, basis: 'Skipped by DQN.',
      context: [{ key: 'monthly_income', label: 'Gross monthly income', value: '5000', unit: 'profile currency' }] },
  ],
  recommendations: [{ kind: 'partial_finding', title: 'Review emergency reserve',
    text: 'Coverage is below the illustrative three-month target.',
    findings: [{ agent_id: 'emergency', finding: { code: 'emergency_gap', title: 'Review emergency reserve',
      reason: 'Coverage is low.', evidence: [
        { label: 'Emergency fund coverage', value: '1.33', unit: 'months' },
        { label: 'Gap to illustrative target', value: '5000.00', unit: 'currency' },
      ], limitations: ['Illustrative target.'] } }],
    context: [], limitations: ['Illustrative target.'] }],
  reward_components: { relevant_coverage: 1, missed_critical_penalty: -3, agent_call_penalty: -0.15 },
  missing_agents: ['budget'],
  limitations: ['A complete monthly plan was withheld because required agents did not run.'],
}

function text(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
}

test('trace connects real findings, agent, numbers, action, and reward without causal claims', () => {
  const output = text(createElement(ExplanationTrail, { trace }))
  assert.match(output, /How this result was reached/)
  assert.match(output, /Action 5/)
  assert.match(output, /context, not causal feature attribution/)
  assert.match(output, /Review emergency reserve/)
  assert.match(output, /From Emergency fund/)
  assert.match(output, /Emergency fund coverage: 1\.33 months/)
  assert.match(output, /Gap to illustrative target: 5000\.00 \(profile currency\)/)
  assert.match(output, /complete plan needs Budget/)
  assert.match(output, /-2\.15 project points/)
  assert.match(output, /feature influence is unavailable/)
})

test('old saved sessions without a trace remain readable', () => {
  assert.equal(renderToStaticMarkup(createElement(ExplanationTrail, { trace: null })), '')
})
