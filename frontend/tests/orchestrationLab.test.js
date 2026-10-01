import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let OrchestrationLab
let OrchestrationResult
let apiModule
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/OrchestrationLab.jsx')
  OrchestrationLab = module.default
  OrchestrationResult = module.OrchestrationResult
  apiModule = await server.ssrLoadModule('/src/services/api.js')
})

test('trained RL request allows a cold model load without relaxing all API timeouts', async () => {
  const original = apiModule.api.post
  let captured
  apiModule.api.post = async (...args) => { captured = args; return { data: { action: 1 } } }
  try {
    await apiModule.runOrchestration(7, 'rl', 42)
    assert.equal(captured[2].timeout, 30000)
    await apiModule.runOrchestration(7, 'trained_rl', 42)
    assert.equal(captured[2].timeout, 30000)
    await apiModule.runOrchestration(7, 'configured', 42)
    assert.deepEqual(captured[1], { seed: 42 })
    assert.equal(captured[2].timeout, 30000)
    await apiModule.runOrchestration(7, 'random', 42)
    assert.equal(captured[2].timeout, 5000)
  } finally {
    apiModule.api.post = original
  }
})

test('a slow first model load reports a timeout rather than a disconnected API', () => {
  assert.match(apiModule.explainApiError({ code: 'ECONNABORTED' }), /timed out/i)
})
after(async () => { await server?.close() })

function text(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
}

test('Advisor exposes all selection modes and explains the experimental run', () => {
  const output = text(createElement(OrchestrationLab, { userId: 1 }))
  assert.match(output, /Choose how agents are selected/)
  assert.match(output, /Server default/)
  assert.match(output, /Rule based/)
  assert.match(output, /Seeded random/)
  assert.match(output, /Trained RL/)
  assert.match(output, /not saved/)
  assert.match(output, /monthly plan/)
})

test('a partial result names chosen agents and withheld plan dependencies', () => {
  const result = {
    mode: 'rl', action: 0, action_version: 'agent-subset-v1', policy_version: 'dqn-bandit-v1',
    as_of_date: '2026-09-29', selected_agents: ['budget'], total_reward: 0.85,
    summary: { title: 'Partial analysis', text: 'A complete monthly plan needs the missing agents listed below.' },
    plan_readiness: { can_build_full_plan: false, missing_agents: ['emergency', 'investment'] },
    agent_results: [{ agent_id: 'budget', findings: [{ code: 'budget_ratios', title: 'Budget ratios', reason: 'Saved income and expenses.', evidence: [
      { label: 'Expense-to-income ratio', value: '60.00', unit: '%' },
      { label: 'Outstanding debt', value: '1000.00', unit: 'currency' },
    ], limitations: [] }], limitations: [] }],
    reward_audit: { components: { relevant_coverage: 1 }, relevant_agents: ['budget'], missed_critical_agents: [], unneeded_agents: [], checks: [] },
    advice: null,
  }
  const output = text(createElement(OrchestrationResult, { result }))
  assert.match(output, /Action 0/)
  assert.match(output, /Budget/)
  assert.match(output, /Emergency fund/)
  assert.match(output, /Investment/)
  assert.match(output, /Partial analysis/)
  assert.match(output, /Budget ratios/)
  assert.match(output, /0\.85/)
  assert.match(output, /60\.00%/)
  assert.match(output, /1000\.00 \(profile currency\)/)
  assert.doesNotMatch(output, /Your monthly savings plan/)
})
