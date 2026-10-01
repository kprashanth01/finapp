import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let MonthlyDemoCase
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  MonthlyDemoCase = (await server.ssrLoadModule('/src/components/MonthlyDemo.jsx')).MonthlyDemoCase
})
after(async () => { await server?.close() })

test('monthly demo shows recorded DQN findings and the partial-plan limit', () => {
  const action = { title: 'Review this month\'s budget', reason: 'Income fell sharply.',
    evidence: [{ label: 'Recent income change', value: '-62.74', unit: '%' }] }
  const method = (selected, reward, status) => ({
    action: 22, selected_agents: selected, reward,
    priority_actions: [action], reward_audit: { critical_agents: ['budget'], missed_critical_agents: [] },
    reward_components: {}, recommendation: {
      status, plan_readiness: { missing_agents: status === 'partial' ? ['investment'] : [] },
    },
  })
  const demo = {
    source: { model_version: 'dynamic-dqn-monthly-v1', synthetic_id: 1034, scenario: 'B', artifact_sha256: 'abc' },
    persona: 'salaried_with_loan',
    months: [
      { month_index: 1, monthly_state: { monthly_income: '168744.03', income_volatility: '0.35' }, methods: { trained_rl: method(['budget'], 6, 'partial'), rule_based: method(['budget'], 6, 'complete') } },
      { month_index: 2, monthly_state: { monthly_income: '62867.67', monthly_expenses: '94111.36', scheduled_emi: '12970.78', emergency_fund: '45397.72', income_change_ratio: '-0.6274', income_volatility: '0.35' },
        methods: { trained_rl: method(['budget', 'debt', 'emergency', 'risk'], 11.4, 'partial'), rule_based: method(['budget', 'debt', 'emergency', 'risk', 'investment'], 10.5, 'complete') } },
    ],
    limitations: ['This is one synthetic held-out user, not the signed-in account.', 'The score is not a financial outcome.'],
  }
  const text = renderToStaticMarkup(createElement(MonthlyDemoCase, { demo, monthIndex: 2, onMonthChange() {} }))
    .replace(/<[^>]+>/g, ' ').replaceAll('&#x27;', "'").replace(/\s+/g, ' ')
  assert.match(text, /62,867\.67/)
  assert.match(text, /35%/)
  assert.match(text, /Trained monthly DQN/)
  assert.match(text, /Rule-based baseline/)
  assert.match(text, /Review this month.s budget/)
  assert.match(text, /Partial specialist findings/)
  assert.match(text, /not the signed-in account/)
  assert.match(text, /not a financial outcome/)
})
