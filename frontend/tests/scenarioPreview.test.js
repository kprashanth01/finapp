import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ScenarioPreview
let ScenarioComparison
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/ScenarioPreview.jsx')
  ScenarioPreview = module.default
  ScenarioComparison = module.ScenarioComparison
})
after(async () => { await server?.close() })

const user = { id: 1, monthly_income: '5000.00' }
const profile = { monthly_expenses: '3000.00', monthly_savings_contribution: '500.00', monthly_debt_payments: '200.00' }

function result(income, contribution, reserve, goal) {
  return { state: { monthly_income: income, monthly_expenses: '3000.00', emergency_fund_months: '1.33' },
    advice: { summary: { title: 'Review emergency reserve' }, priority_actions: [], monthly_plan: {
      capacity: contribution, emergency_allocation: reserve, unassigned: '0.00', hold_reason: null,
      goal_allocations: [{ allocated_monthly: goal, funding_gap: String(500 - Number(goal)),
        requirement: { goal: { id: 1, name: 'Laptop' } } }],
    } } }
}

test('scenario form offers editable values and clearly separates a preview from saved data', () => {
  const html = renderToStaticMarkup(createElement(ScenarioPreview, { user, profile, goals: [] }))
  assert.match(html, /What if my income or expenses change\?/)
  assert.match(html, /Try 20% less income/)
  assert.match(html, /Preview changed plan/)
  assert.match(html, /does not change your saved profile or plan/)
  assert.match(html, /name="monthly_income"[^>]*value="5000\.00"/)
  assert.match(html, /name="monthly_savings_contribution"[^>]*value="500\.00"/)
  assert.match(html, /Saved gross monthly income: <strong>5,000\.00<\/strong>/)
  assert.match(html, /Before tax, expected in this month/)
})

test('zero saved income explains the preset and shows the impossible savings assumption', () => {
  const html = renderToStaticMarkup(createElement(ScenarioPreview, {
    user: { ...user, monthly_income: '0.00' },
    profile: { ...profile, monthly_savings_contribution: '1000.00' },
    onOpenIncome() {},
  }))
  assert.match(html, /Saved gross monthly income: <strong>0\.00<\/strong>/)
  assert.match(html, /20% preset needs a positive saved income/)
  assert.match(html, /Update saved income/)
  assert.match(html, /<button type="button" disabled=""[^>]*>Try 20% less income<\/button>/)
  assert.match(html, /at most 0\.00 before tax/)
  assert.match(html, /name="monthly_income"[^>]*value="0\.00"/)
})

test('comparison shows changed priority context, allocation, goal funding, and gross-cash limitation', () => {
  const html = renderToStaticMarkup(createElement(ScenarioComparison, { preview: {
    baseline: result('5000.00', '500.00', '400.00', '100.00'),
    scenario: result('3500.00', '300.00', '300.00', '0.00'),
  } }))
  assert.match(html, /Current saved inputs/)
  assert.match(html, /Hypothetical month/)
  assert.match(html, /Gross income less expenses/)
  assert.match(html, /Emergency reserve/)
  assert.match(html, /Laptop/)
  assert.match(html, /Laptop monthly shortfall/)
  assert.match(html, /400\.00/)
  assert.match(html, /300\.00/)
  assert.match(html, /take-home pay/)
  assert.match(html, /No money is moved/)
})

test('comparison calls out a month where expenses exceed gross income', () => {
  const changed = result('2500.00', '0.00', '0.00', '0.00')
  const html = renderToStaticMarkup(createElement(ScenarioComparison, { preview: {
    baseline: result('5000.00', '500.00', '400.00', '100.00'), scenario: changed,
  } }))
  assert.match(html, /expenses exceed gross income/)
  assert.match(html, /Review spending or income/)
})
