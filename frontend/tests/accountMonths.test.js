import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let AccountMonths
let AccountAdvice
let updateMonthDraft
let monthTotals
let formMonth
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/AccountMonths.jsx')
  AccountMonths = module.default
  AccountAdvice = module.AccountAdvice
  updateMonthDraft = module.updateMonthDraft
  monthTotals = module.monthTotals
  formMonth = module.formMonth
})
after(async () => { await server?.close() })

test('monthly entry is an account-owned blank history with editable financial fields', () => {
  const html = renderToStaticMarkup(createElement(AccountMonths, {
    userId: 1, user: { monthly_income: '5000' }, profile: { monthly_expenses: '3000', monthly_debt_payments: '200',
      savings: '8000', emergency_fund: '3000', existing_debt: '1000', risk_tolerance: 'moderate' },
  }))
  assert.match(html, /Build your own month-by-month situation/)
  assert.match(html, /Income received/)
  assert.match(html, /Loan payment actually made/)
  assert.match(html, /Save this month/)
  assert.match(html, /Start next month/)
  assert.match(html, /Essential bills/)
  assert.match(html, /Loan balance still owed/)
  assert.match(html, /What does.*mean/)
  assert.match(html, /Total planned spending.*calculated/)
  assert.match(html, /Loading your recorded months/)
})

test('monthly totals derive from entered parts and due payment fills actual payment until changed', () => {
  let draft = { monthly_income: '30000', fixed_expenses: '16000', other_expenses: '9000',
    scheduled_emi: '5000', paid_emi: '5000', paid_emi_edited: false }
  assert.deepEqual(monthTotals(draft), { monthly_expenses: '30000.00', net_cash_flow: '0.00' })
  draft = updateMonthDraft(draft, 'scheduled_emi', '6000')
  assert.equal(draft.paid_emi, '6000')
  assert.equal(monthTotals(draft).monthly_expenses, '31000.00')
  draft = updateMonthDraft(draft, 'paid_emi', '4000')
  draft = updateMonthDraft(draft, 'scheduled_emi', '6500')
  assert.equal(draft.paid_emi, '4000')
})

test('editing a saved month derives spending parts without sending its read-only id', () => {
  const draft = formMonth({ id: 99, period: '2026-06-01', monthly_income: '30000.00',
    monthly_expenses: '70000.00', fixed_expenses: '16500.01', scheduled_emi: '5000.00', paid_emi: '5000.00',
    savings: '5000.00', emergency_fund: '0.00', outstanding_debt: '100000.00', unfunded_expenses: '0.00',
    risk_tolerance: 'conservative', investment_horizon_years: 15 })
  assert.equal(draft.other_expenses, '48499.99')
  assert.equal(monthTotals(draft).monthly_expenses, '70000.00')
  assert.equal('id' in draft, false)
  assert.equal(formMonth({ ...draft, period: '2026-06-01', monthly_expenses: '70000.00', paid_emi: '2500.00' }).paid_emi_edited, true)
})

test('zero-income result names the DQN miss and exposes the rule and requested specialist', () => {
  const result = (agents, missed, status) => ({ action: 1, selected_agents: agents, reward: 3,
    priority_actions: [{ agent_id: 'budget', finding_code: 'pressure', title: 'Review this month\'s budget', reason: 'Income fell.', evidence: [] }],
    reward_audit: { missed_critical_agents: missed }, reward_components: {},
    recommendation: { status, plan_readiness: { missing_agents: status === 'partial' ? ['debt', 'investment'] : [] } },
  })
  const advice = { month: { period: '2026-09-01', monthly_income: '30000', monthly_expenses: '70000', scheduled_emi: '5000' }, model_version: 'test', model_artifact_sha256: 'abcdefabcdef',
    context: { history_months_used: 2, recent_income_change_ratio: '-1', net_cash_flow: '-40000',
      income_volatility: '1', usual_income_reference: '6000' },
    methods: { trained_rl: result(['budget', 'emergency', 'risk'], ['debt'], 'partial'),
      rule_based: result(['budget', 'debt', 'emergency', 'risk', 'investment'], [], 'complete') },
    focused_review: { agent_id: 'debt', selected_by_dqn: false,
      result: { findings: [{ code: 'debt', title: 'Review current debt obligations', reason: 'Income is below expenses.',
        evidence: [{ label: 'Payment-to-income ratio', value: '16.6666666666667', unit: '%' },
          { label: 'Emergency coverage', value: '0', unit: 'months' },
          { label: 'Interest rate', value: null, unit: '%' }] }] } },
    limitations: ['The DQN was trained on generated people.'] }
  const text = renderToStaticMarkup(createElement(AccountAdvice, { advice })).replace(/<[^>]+>/g, ' ')
  assert.match(text, /DQN did not run the important Debt check/)
  assert.match(text, /DQN did not select it/)
  assert.match(text, /Review current debt obligations/)
  assert.match(text, /Rule-based baseline/)
  assert.match(text, /40,000\.00/)
  assert.match(text, /16\.67%/)
  assert.match(text, /0\.00 months/)
  assert.doesNotMatch(text, /Interest rate:/)
  assert.doesNotMatch(text, /proxy points|ACTION 1|16\.666666/)

  const investmentView = renderToStaticMarkup(createElement(AccountAdvice, { advice: {
    ...advice, focused_review: { agent_id: 'investment', selected_by_dqn: false,
      result: { findings: [{ code: 'investment_prerequisites', title: 'Investment readiness',
        reason: 'The emergency reserve is below target.', evidence: [] }] },
      interpretation: { status: 'deferred',
        headline: 'Money left after planned spending is not an investment recommendation.',
        steps: ['Build an accessible emergency reserve before deciding on a new investment.',
          'Confirm your loan interest rate before choosing between repayment and investing.'] } },
  } })).replace(/<[^>]+>/g, ' ')
  assert.match(investmentView, /What this means for your investment decision/)
  assert.match(investmentView, /not an investment recommendation/)
  assert.match(investmentView, /loan interest rate/)
})
