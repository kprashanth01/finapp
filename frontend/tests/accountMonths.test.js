import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let AccountMonths
let AccountAdvice
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/AccountMonths.jsx')
  AccountMonths = module.default
  AccountAdvice = module.AccountAdvice
})
after(async () => { await server?.close() })

test('monthly entry is an account-owned blank history with editable financial fields', () => {
  const html = renderToStaticMarkup(createElement(AccountMonths, {
    userId: 1, user: { monthly_income: '5000' }, profile: { monthly_expenses: '3000', monthly_debt_payments: '200',
      savings: '8000', emergency_fund: '3000', existing_debt: '1000', risk_tolerance: 'moderate' },
  }))
  assert.match(html, /Build your own month-by-month situation/)
  assert.match(html, /Income received/)
  assert.match(html, /Debt payment actually made/)
  assert.match(html, /Save this month/)
  assert.match(html, /Start next month/)
  assert.match(html, /Loading your recorded months/)
})

test('zero-income result names the DQN miss and exposes the rule and requested specialist', () => {
  const result = (agents, missed, status) => ({ action: 1, selected_agents: agents, reward: 3,
    priority_actions: [{ agent_id: 'budget', finding_code: 'pressure', title: 'Review this month\'s budget', reason: 'Income fell.', evidence: [] }],
    reward_audit: { missed_critical_agents: missed }, reward_components: {},
    recommendation: { status, plan_readiness: { missing_agents: status === 'partial' ? ['debt', 'investment'] : [] } },
  })
  const advice = { month: { period: '2026-09-01' }, model_version: 'test', model_artifact_sha256: 'abcdefabcdef',
    context: { history_months_used: 2, recent_income_change_ratio: '-1', net_cash_flow: '-3500',
      income_volatility: '1', usual_income_reference: '6000' },
    methods: { trained_rl: result(['budget', 'emergency', 'risk'], ['debt'], 'partial'),
      rule_based: result(['budget', 'debt', 'emergency', 'risk', 'investment'], [], 'complete') },
    focused_review: { agent_id: 'debt', selected_by_dqn: false,
      result: { findings: [{ code: 'debt', title: 'Review current debt obligations', reason: 'Income is below expenses.', evidence: [] }] } },
    limitations: ['The DQN was trained on generated people.'] }
  const text = renderToStaticMarkup(createElement(AccountAdvice, { advice })).replace(/<[^>]+>/g, ' ')
  assert.match(text, /DQN missed a critical Debt check/)
  assert.match(text, /DQN did not select it/)
  assert.match(text, /Review current debt obligations/)
  assert.match(text, /Rule-based baseline/)
})
