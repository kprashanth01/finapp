import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let EvaluationReportCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  EvaluationReportCard = (await server.ssrLoadModule('/src/components/Research.jsx')).EvaluationReportCard
})
after(async () => { await server?.close() })

test('Research shows the measured three-way report and its limits', () => {
  const report = JSON.parse(readFileSync(new URL('../../backend/app/rl/evaluation_report.json', import.meta.url)))
  const text = renderToStaticMarkup(createElement(EvaluationReportCard, {
    evidence: { status: 'available', report },
  })).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
  assert.match(text, /same 256 generated financial cases/)
  assert.match(text, /Seeded random/)
  assert.match(text, /Rule based/)
  assert.match(text, /Trained DQN/)
  assert.match(text, /7\.83/)
  assert.match(text, /Average paired score difference \(DQN − rule\)/)
  assert.match(text, /proxy points per case/)
  assert.match(text, /Average paired agent-call difference \(DQN − rule\): -0\.0625 agents per case/)
  assert.match(text, /DQN − rule score/)
  assert.match(text, /one agent selection per case/)
  assert.match(text, /does not establish|cannot establish/)
  assert.match(text, /Recommendation consistency and conflicts are not measured/)
  assert.match(text, /python -m app\.rl\.evaluation/)
})

test('Research reports stale evaluation evidence without fake results', () => {
  const text = renderToStaticMarkup(createElement(EvaluationReportCard, {
    evidence: { status: 'unavailable', reason: 'Evaluation report is missing.' },
  }))
  assert.match(text, /Evaluation report is missing/)
  assert.doesNotMatch(text, /Trained DQN/)
})
