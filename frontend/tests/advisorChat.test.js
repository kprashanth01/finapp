import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let AdvisorChat
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  AdvisorChat = (await server.ssrLoadModule('/src/components/AdvisorChat.jsx')).default
})
after(async () => { await server?.close() })

test('chat describes local model answers and remains scoped to the selected saved run', () => {
  const html = renderToStaticMarkup(createElement(AdvisorChat, { userId: 1, sessionId: 2, stale: true }))
  assert.match(html, /Ask about this saved run/)
  assert.match(html, /Why should I focus on my emergency fund/)
  assert.match(html, /Which part of my finances needs attention/)
  assert.match(html, /These answers describe the saved run/)
  assert.match(html, /local AI model/)
  assert.doesNotMatch(html, /without calling an AI model/)
  assert.match(html, /profile has changed/)
  assert.match(html, /not saved to history/)
  assert.doesNotMatch(html, /OpenAI/)
})
