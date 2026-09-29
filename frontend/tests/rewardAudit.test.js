import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let RewardAuditDetails
let Research
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/Research.jsx')
  RewardAuditDetails = module.RewardAuditDetails
  Research = module.default
})
after(async () => { await server?.close() })

function visibleText(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
}

test('Research explains score inputs and missing data in saved-profile terms', () => {
  assert.equal(typeof RewardAuditDetails, 'function')
  const audit = {
    version: 'selection-proxy-v1',
    components: { relevant_coverage: 2, critical_coverage: 2,
      missed_critical_penalty: -3, unneeded_agent_penalty: 0, agent_call_penalty: -0.3 },
    relevant_agents: ['budget', 'debt', 'emergency', 'risk', 'investment'],
    critical_agents: ['debt', 'emergency'], missed_critical_agents: ['debt'],
    unneeded_agents: [],
    checks: [
      { agent_id: 'emergency', label: 'Emergency reserve coverage', value: '1.33',
        unit: 'months', operator: '<', threshold: '3', input_status: 'available',
        critical: true, selected: true, note: 'Below the illustrative three-month reserve target.' },
      { agent_id: 'debt', label: 'Debt payment ratio', value: null,
        unit: '%', operator: '>=', threshold: '20', input_status: 'unavailable',
        critical: true, selected: false,
        note: 'Debt exists, but the payment ratio is unavailable; this proxy treats the Debt check as critical.' },
    ],
  }
  const text = visibleText(createElement(RewardAuditDetails, { audit }))
  assert.match(text, /Critical needs covered \+2\.00/)
  assert.match(text, /Missed critical needs -3\.00/)
  assert.match(text, /Emergency reserve coverage 1\.33 months\. Critical below 3 months/)
  assert.match(text, /Debt payment ratio Unavailable/)
  assert.match(text, /Missed critical check: Debt/)
  assert.match(text, /does not measure financial improvement/)
})

test('Research exposes the random seed used for a repeatable comparison', () => {
  const markup = renderToStaticMarkup(createElement(Research, { userId: 1, hasProfile: true }))
  assert.match(markup, /Random seed/)
  assert.match(markup, /type="number"[^>]*value="42"/)
})
