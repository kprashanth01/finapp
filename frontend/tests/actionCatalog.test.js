import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ActionCatalogDetails
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ActionCatalogDetails = (await server.ssrLoadModule('/src/components/Research.jsx')).ActionCatalogDetails
})
after(async () => { await server?.close() })

const catalog = {
  action_version: 'agent-subset-v1', action_count: 3,
  selection_semantics: 'one_step_subset',
  agents: ['budget', 'debt'],
  actions: [
    { id: 0, agents: ['budget'] },
    { id: 1, agents: ['debt'] },
    { id: 2, agents: ['budget', 'debt'] },
  ],
}

test('Research shows the current action ID and explains one-step subset semantics', () => {
  const markup = renderToStaticMarkup(createElement(ActionCatalogDetails, {
    catalog, selected: ['debt', 'budget'],
  }))
  assert.match(markup, /Action ID 2/)
  assert.match(markup, /Budget and Debt/)
  assert.match(markup, /one decision on the same financial state/i)
  assert.match(markup, /no sequence of financial state changes/i)
  assert.match(markup, /All 3 action mappings/)
  assert.match(markup, /agent-subset-v1/)
})

test('Research prompts for a selection before showing an action ID', () => {
  const markup = renderToStaticMarkup(createElement(ActionCatalogDetails, {
    catalog, selected: [],
  }))
  assert.match(markup, /Choose at least one agent/)
  assert.doesNotMatch(markup, /Action ID [0-9]/)
})
