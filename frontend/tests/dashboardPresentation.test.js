import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let Dashboard
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  Dashboard = (await server.ssrLoadModule('/src/components/Dashboard.jsx')).default
})
after(async () => { await server?.close() })

const user = { name: 'Sam', monthly_income: '30000' }
const profile = { monthly_expenses: '20000', monthly_savings_contribution: '5000', savings: '25000', existing_debt: '10000', emergency_fund: '10000', risk_tolerance: 'moderate' }
const analysis = { emergency_fund_months: '0.50', debt_to_income_percent: '10.00', savings_rate_percent: '16.67', expense_to_income_percent: '66.67', health_score: 48 }

function render(session) {
  return renderToStaticMarkup(createElement(Dashboard, {
    user, profile, analysis, advisorySession: session, goals: [], goalsLoading: false,
    onOpenProfile() {}, onOpenGoal() {}, onOpenAdvisor() {}, onOpenGoals() {}, onRunAdvisory() {},
  }))
}

function savedSession(isStale) {
  return { is_stale: isStale, stale_reasons: isStale ? ['inputs'] : [], created_at: '2026-10-01T00:00:00Z', result: {
    state: { as_of_date: '2026-10-01' },
    advice: {
      summary: { title: 'Review emergency reserve', text: 'Reserve first, then goals.', next_action: { view: 'profile', field: 'emergency_fund' } },
      priority_actions: [{ code: 'review_emergency', title: 'Review emergency reserve', reason: 'Coverage is below the illustrative three-month target.', source_refs: [{ agent_id: 'emergency', finding_code: 'emergency_gap' }], next_action: { view: 'profile', field: 'emergency_fund' } }],
      monthly_plan: { capacity: '5000', emergency_allocation: '4000', goal_allocations: [{ requirement: { goal: { id: 1, name: 'Laptop' } }, allocated_monthly: '1000' }], unassigned: '0', hold_reason: null },
    },
    agent_results: [{ agent_id: 'emergency', findings: [{ code: 'emergency_gap', evidence: [{ label: 'Emergency fund coverage', value: '0.50', unit: 'months' }], impact: 'A small reserve leaves less room for an unexpected expense.', suggested_action: 'Use the coordinated plan to build your reserve.' }] }],
  } }
}

test('dashboard shows the current priority, its evidence, and the coordinated monthly allocation first', () => {
  const html = render(savedSession(false))
  assert.match(html, /What should I do this month\?/)
  assert.match(html, /Emergency fund coverage: 0\.50 months/)
  assert.match(html, /A small reserve leaves less room for an unexpected expense/)
  assert.match(html, /Use the coordinated plan to build your reserve/)
  assert.match(html, /Emergency reserve<\/dt><dd>4,000\.00/)
  assert.match(html, /Laptop<\/dt><dd>1,000\.00/)
  assert.ok(html.indexOf('What should I do this month?') < html.indexOf('All saved amounts and calculated ratios'))
})

test('dashboard with changed inputs asks for a new plan and does not show old allocations', () => {
  const html = render(savedSession(true))
  assert.match(html, /Run updated plan/)
  assert.doesNotMatch(html, /Emergency reserve<\/dt><dd>4,000\.00/)
  assert.doesNotMatch(html, /Your first priority/)
  assert.doesNotMatch(html, /Use the coordinated plan to build your reserve/)
})

test('dashboard with no saved plan offers to create one', () => {
  const html = render(null)
  assert.match(html, /Create my monthly plan/)
  assert.doesNotMatch(html, /Your first priority/)
})

test('dashboard offers a separate read-only event preview for real-life changes', () => {
  const html = render(null)
  assert.match(html, /Try a specific financial change/)
  assert.match(html, /Unexpected expense/)
  assert.match(html, /Subscription reduction/)
  assert.match(html, /Extra loan payment/)
  assert.match(html, /Change goal contribution/)
  assert.match(html, /does not change saved information/)
})
