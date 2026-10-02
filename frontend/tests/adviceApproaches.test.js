import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let Panel
let Results
let apiModule
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const component = await server.ssrLoadModule('/src/components/OrchestrationLab.jsx')
  Panel = component.AdviceApproachPanel
  Results = component.AdviceApproachResults
  apiModule = await server.ssrLoadModule('/src/services/api.js')
})
after(async () => { await server?.close() })

const output = (component) => renderToStaticMarkup(component).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')

test('Advisor offers a plain-language comparison without research controls', () => {
  const html = output(createElement(Panel, { userId: 1 }))
  assert.match(html, /Compare planning approaches/)
  assert.match(html, /current saved profile/i)
  assert.doesNotMatch(html, /proxy points|action catalogue/i)
})

test('comparison separates a full standard plan from an incomplete model result', () => {
  const shared = { as_of_date: '2026-10-03', state_fingerprint: 'a'.repeat(64) }
  const result = { ...shared,
    rule_based: { ...shared, status: 'complete', selected_agents: ['budget', 'emergency'], missing_agents: [],
      first_action: { title: 'Review your reserve', text: 'Build emergency savings.' }, detail: 'Build emergency savings.' },
    trained_rl: { ...shared, status: 'partial', selected_agents: ['budget'], missing_agents: ['emergency'],
      first_action: null, detail: 'A complete monthly plan needs the missing agents.' },
  }
  const html = output(createElement(Results, { result }))
  assert.match(html, /Standard plan/)
  assert.match(html, /Experimental model/)
  assert.match(html, /Review your reserve/)
  assert.match(html, /complete model plan/i)
  assert.match(html, /Emergency fund/)
  assert.doesNotMatch(html, /proxy points/i)
})

test('unavailable model leaves the standard plan visible', () => {
  const shared = { as_of_date: '2026-10-03', state_fingerprint: 'a'.repeat(64) }
  const result = { ...shared,
    rule_based: { ...shared, status: 'complete', selected_agents: ['budget'], missing_agents: [],
      first_action: { title: 'Review spending', text: 'Check costs.' }, detail: 'Check costs.' },
    trained_rl: { ...shared, status: 'unavailable', selected_agents: [], missing_agents: [],
      first_action: null, detail: 'The optional trained model is unavailable on this server.' },
  }
  const html = output(createElement(Results, { result }))
  assert.match(html, /Review spending/)
  assert.match(html, /optional trained model is unavailable/i)
})

test('a complete plan with no priority says so without inventing a first step', () => {
  const shared = { as_of_date: '2026-10-03', state_fingerprint: 'a'.repeat(64) }
  const result = { ...shared,
    rule_based: { ...shared, status: 'complete', selected_agents: ['budget'], missing_agents: [],
      first_action: null, detail: 'Allocations are available.' },
    trained_rl: { ...shared, status: 'unavailable', selected_agents: [], missing_agents: [],
      first_action: null, detail: 'Model unavailable.' },
  }
  const html = output(createElement(Results, { result }))
  assert.match(html, /No priority action flagged/)
  assert.match(html, /Allocations are available/)
})

test('comparison requests one owned current snapshot', async () => {
  const original = apiModule.api.get
  let request
  apiModule.api.get = async (...args) => { request = args; return { data: { source: 'saved_profile' } } }
  try {
    await apiModule.getAdviceApproaches(7)
    assert.equal(request[0], '/users/7/advice-approaches')
    assert.ok(request[1].timeout >= 30000)
  } finally { apiModule.api.get = original }
})
