import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

let server
let apiModule
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  apiModule = await server.ssrLoadModule('/src/services/api.js')
})
after(async () => { await server?.close() })

test('monthly question sends the topic selected for the displayed review', async () => {
  const { api, askFinancialMonth } = apiModule
  const original = api.post
  const calls = []
  api.post = async (...args) => { calls.push(args); return { data: { answer: 'ok' } } }
  try {
    await askFinancialMonth(7, '2026-06-01', 'How much should I invest?', 'investment')
    assert.equal(calls[0][0], '/users/7/financial-months/2026-06-01/ask')
    assert.deepEqual(calls[0][1], { question: 'How much should I invest?', focus: 'investment' })
    await askFinancialMonth(7, '2026-06-01', 'What changed?')
    assert.equal(calls[1][1].focus, 'all')
  } finally {
    api.post = original
  }
})
