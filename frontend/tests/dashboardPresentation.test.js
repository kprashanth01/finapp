import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let Dashboard
let RecommendationContent
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  Dashboard = (await server.ssrLoadModule('/src/components/Dashboard.jsx')).default
  RecommendationContent = (await server.ssrLoadModule('/src/components/UserRecommendations.jsx')).RecommendationContent
})
after(async () => { await server?.close() })

const user = { name: 'Sam', monthly_income: '30000' }
const profile = { monthly_expenses: '20000', monthly_savings_contribution: '5000', savings: '25000', existing_debt: '10000', emergency_fund: '10000', risk_tolerance: 'moderate' }
const analysis = { emergency_fund_months: '0.50', debt_to_income_percent: '10.00', savings_rate_percent: '16.67', expense_to_income_percent: '66.67', health_score: 48 }

function render(session, currentAnalysis = analysis) {
  return renderToStaticMarkup(createElement(Dashboard, {
    user, profile, analysis: currentAnalysis, advisorySession: session, goals: [], goalsLoading: false,
    onOpenProfile() {}, onOpenGoal() {}, onOpenAdvisor() {}, onOpenGoals() {}, onRunAdvisory() {},
  }))
}

function examplePicture() {
  const fact = (value, source = 'profile.monthly_expenses') => ({ value, source, status: 'known', note: 'Saved value.' })
  return {
    as_of_date: '2026-10-03',
    income: { observed_months: 0, recent_period: null, expected_monthly: fact('2500'),
      guaranteed_monthly: fact(null), observed_average: fact(null), observed_recent: fact(null),
      observed_minimum: fact(null), variability_percent: fact(null), conservative_reference: fact(null) },
    spending: { gross_cash_flow: fact('-500', 'current_income_estimate_minus_profile_expenses'),
      available_surplus_upper_bound: fact('0'), monthly_total: fact('3000'),
      known_essential_fixed: fact('1000'), known_essential_variable: fact('0'), known_essential: fact('1200'),
      known_discretionary: fact('0'), unclassified_monthly: fact('1800'), exact_essential: fact(null),
      exact_discretionary: fact(null), entered_savings_capacity: fact('500'), savings_rate_percent: fact('20'),
      debt_to_income_percent: fact('8') },
    reserve: { total_expense_coverage_months: fact('0.50'), essential_coverage_months: fact(null),
      funding_gap: fact('7500'), target_months: '3' },
    goal_funding_gap: fact('900'), planned_due_90_days: fact('800'), unreserved_due_90_days: fact('200'),
    obligations: [
      { id: 1, kind: 'planned_expense', name: 'Insurance', amount: '800', unreserved_amount: '200',
        due_date: '2026-10-10', is_essential: true, is_overdue: false },
      { id: 2, kind: 'loan_payment', name: 'Car loan', amount: '200', unreserved_amount: null,
        due_date: '2026-10-08', is_essential: true, is_overdue: false },
    ],
    goals: [{ id: 3, name: 'Laptop', remaining_amount: '900', target_date: '2026-12-01', priority: 'high' }],
    limitations: [],
  }
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
  assert.match(html, /<details[^>]*><summary[^>]*>Explore what-if changes<\/summary>[\s\S]*Try a specific financial change/)
  assert.match(html, /Try a specific financial change/)
  assert.match(html, /Unexpected expense/)
  assert.match(html, /Subscription reduction/)
  assert.match(html, /Extra loan payment/)
  assert.match(html, /Change goal contribution/)
  assert.match(html, /does not change saved information/)
})

test('dashboard separates current recommendations from the saved monthly allocation', () => {
  const html = render(savedSession(false))
  assert.match(html, /user-recommendations-heading/)
  assert.match(html, /Saved monthly allocation plan/)
  assert.ok(html.indexOf('What should I do this month?') < html.indexOf('Saved monthly allocation plan'))
})

test('dashboard keeps detailed calculations in an optional section', () => {
  const html = render(savedSession(false), { ...analysis, picture: examplePicture() })
  assert.match(html, /<details[^>]*><summary[^>]*>Explore saved numbers and calculations<\/summary>[\s\S]*All saved amounts and calculated ratios/)
})

test('dashboard presents the monthly shortfall, reserve, due costs, and goals before the saved plan', () => {
  const html = render(savedSession(false), { ...analysis, picture: examplePicture() })
  assert.match(html, /Your month at a glance/)
  assert.match(html, /Gross monthly shortfall/)
  assert.match(html, /500\.00/)
  assert.match(html, /Emergency reserve/)
  assert.match(html, /Insurance/)
  assert.match(html, /200\.00 not marked reserved/)
  assert.match(html, /Car loan/)
  assert.match(html, /already included in monthly expenses/)
  assert.match(html, /Laptop/)
  assert.ok(html.indexOf('Your month at a glance') < html.indexOf('What should I do this month?'))
  assert.ok(html.indexOf('Upcoming obligations') < html.indexOf('Saved monthly allocation plan'))
})

test('dashboard offers a conversation about current finances without requiring a saved run', () => {
  const html = render(null, { ...analysis, picture: examplePicture() })
  assert.match(html, /Ask about your current finances/)
  assert.match(html, /What should I prioritize\?/)
  assert.match(html, /Can I afford an upcoming expense\?/)
  assert.match(html, /What if my income falls\?/)
  assert.ok(html.indexOf('Ask about your current finances') < html.indexOf('Saved monthly allocation plan'))
})

test('current recommendation shows the ranked action, calculation source, and assumptions', () => {
  const item = {
    priority: 1, code: 'planned_cost_1', urgency: 'urgent', area: 'upcoming_cost',
    action: 'Review payment for Insurance', reason: 'Insurance is overdue with 700.00 not marked as reserved.',
    supporting_calculations: [{ label: 'Amount not marked reserved', value: '700.00', unit: 'currency', source: 'saved_planned_expense' }],
    priority_factors: ['Marked essential', 'Overdue'], assumptions: ['Reserved means entered as set aside, not verified cash.'],
    target_view: 'profile', target_id: null,
  }
  const html = renderToStaticMarkup(createElement(RecommendationContent, {
    data: { as_of_date: '2026-10-03', recommendations: [item], limitations: ['Gross income is before tax.'] },
  }))
  assert.match(html, /Priority 1 · urgent · upcoming cost/)
  assert.match(html, /Review payment for Insurance/)
  assert.match(html, /Amount not marked reserved/)
  assert.match(html, /Source: Profile upcoming costs/)
  assert.match(html, /Marked essential/)
  assert.match(html, /not verified cash/)
  assert.match(html, /Gross income is before tax/)
})

test('the first three actions are visible before the remaining actions disclosure', () => {
  const recommendations = Array.from({ length: 4 }, (_, index) => ({
    priority: index + 1, code: `action_${index}`, urgency: 'normal', area: 'goals',
    action: `Action ${index + 1}`, reason: `Reason ${index + 1}`,
    supporting_calculations: [], priority_factors: [], assumptions: [], target_view: 'goals', target_id: index + 1,
  }))
  const html = renderToStaticMarkup(createElement(RecommendationContent, {
    data: { as_of_date: '2026-10-03', recommendations, limitations: [] },
  }))
  assert.ok(html.indexOf('Action 2') < html.indexOf('more action to review'))
  assert.ok(html.indexOf('Action 3') < html.indexOf('more action to review'))
  assert.ok(html.indexOf('Action 4') > html.indexOf('more action to review'))
})
