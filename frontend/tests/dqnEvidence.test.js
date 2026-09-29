import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let TrainingEvidenceCard
let Research
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/Research.jsx')
  TrainingEvidenceCard = module.TrainingEvidenceCard
  Research = module.default
})
after(async () => { await server?.close() })

function visibleText(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
}

test('Research shows measured DQN training evidence and one-step limits', () => {
  const metadata = {
    algorithm: 'DQN', model_version: 'dqn-bandit-v1',
    split_counts: { training: 1536, validation: 384, test: 384 },
    selected_step: 12000, total_timesteps: 12000,
    validation_history: [
      { step: 3000, case_count: 384, mean_reward: 7.635, critical_miss_rate: 0.0443 },
      { step: 12000, case_count: 384, mean_reward: 7.827, critical_miss_rate: 0 },
    ],
    test: { case_count: 384, mean_reward: 7.823, critical_miss_rate: 0, mean_agent_calls: 5.435 },
  }
  const text = visibleText(createElement(TrainingEvidenceCard, {
    evidence: { status: 'available', metadata },
  }))
  assert.match(text, /DQN/)
  assert.match(text, /1,536 training/)
  assert.match(text, /384 validation/)
  assert.match(text, /384 held-out test/)
  assert.match(text, /12,000 steps/)
  assert.match(text, /7\.82/)
  assert.match(text, /0\.0%/)
  assert.match(text, /one-step/)
  assert.match(text, /run the trained DQN in Advisor/)
})

test('Research distinguishes a missing DQN artifact from the existing fitted comparison', () => {
  const text = visibleText(createElement(TrainingEvidenceCard, {
    evidence: { status: 'unavailable', reason: 'DQN training artifact is not installed.' },
  }))
  assert.match(text, /not installed/)
  const page = visibleText(createElement(Research, { userId: 1, hasProfile: true }))
  assert.match(page, /fitted proxy selector/)
})
