import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ReasoningPanel
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ReasoningPanel = (await server.ssrLoadModule('/src/components/ReasoningPanel.jsx')).default
})
after(async () => { await server?.close() })

test('explanation is opt-in and discloses which saved facts leave the app', () => {
  const html = renderToStaticMarkup(createElement(ReasoningPanel, { userId: 1, sessionId: 2 }))
  assert.match(html, /Generate explanation/)
  assert.match(html, /sent to OpenAI only if a model is configured and you press the button/)
  assert.match(html, /Account name and email fields are excluded/)
  assert.doesNotMatch(html, /AI-written synthesis/)
})
