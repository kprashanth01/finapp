import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let Results
let AppShell
let payload
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/LoanReadiness.jsx')
  Results = module.LoanReadinessResults
  payload = module.loanScenarioPayload
  AppShell = (await server.ssrLoadModule('/src/components/AppShell.jsx')).default
})
after(async () => { await server?.close() })

test('loan readiness is a primary workspace view', () => {
  const html = renderToStaticMarkup(createElement(AppShell, {
    activeView: 'loan-readiness', user: { name: 'Sam' }, connection: 'connected', children: 'content',
  }))
  assert.match(html, /Loan Readiness/)
  assert.match(html, /aria-current="page"/)
})

test('loan inputs preserve unknown credit and only save explicitly entered criteria', () => {
  const values = payload({ name: 'Work vehicle', loan_type: 'vehicle', lender_name: '', amount: '200000',
    annual_interest_rate_percent: '12', tenure_months: '24', quoted_monthly_payment: '',
    credit_score: '', credit_history_months: '', credit_utilization_percent: '',
    income_documents_ready: '', missed_payments_last_12_months: '',
    criteria: [{ kind: 'minimum_history_months', value: '6', source_name: 'Offer sheet', source_url: '' }],
  })
  assert.equal(values.credit_score, null)
  assert.equal(values.lender_name, null)
  assert.equal(values.criteria.length, 1)
  assert.equal(values.criteria[0].source_name, 'Offer sheet')
})

test('readiness results lead with low-month capacity, requirements, sources and actions', () => {
  const row = { key: 'reserve', name: 'Emergency reserve', current_value: '1.19 months',
    required_value: '3 months of total expenses', status: 'NEEDS_IMPROVEMENT', priority: 2,
    source_type: 'illustrative_project', source_label: 'Illustrative project criterion — not a lender policy.',
    explanation: 'The reserve is below the app target.', action: 'Build a cash buffer.' }
  const point = { income: '12000', total_expenses_including_existing_emi: '21000', existing_emi_included: '3000',
    planned_savings: null, proposed_emi: '9414.69', remaining_before_savings: '-18414.69',
    remaining_after_savings: null, period: '2026-08-01' }
  const assessment = { summary: 'The proposed EMI produces a gross shortfall.', evaluated_at: '2026-10-03T10:00:00Z',
    estimated_emi: '9414.69', total_repayment: '225952.56', emi_source: 'calculated',
    income: { observed_months: 5, average: '25800', median: '27000', minimum: '12000', maximum: '40000',
      variability_percent: '38.00', latest_change: '15000', first_period: '2026-05-01', latest_period: '2026-09-01' },
    current_month: { ...point, income: '27000', remaining_before_savings: '-3414.69', period: null },
    typical_month: { ...point, income: '27000', remaining_before_savings: '-3414.69', period: null },
    low_income_month: point, recorded_months: [point], reserve_coverage_months: '1.19', reserve_gap: '38000',
    known_essential_expenses: '20000', known_discretionary_expenses: '1000', unclassified_expenses: '0',
    existing_debt: '60000', existing_monthly_emi: '3000', requirements: [row], priority_actions: [row],
    goal_monthly_needs: [], agent_findings: [], assumptions: ['Gross income before tax.'],
    changes_since_previous: ['Emergency reserve coverage changed from 1.00 to 1.19'] }
  const html = renderToStaticMarkup(createElement(Results, { assessment }))
  assert.match(html, /Low-income month/)
  assert.match(html, /18,414\.69/)
  assert.match(html, /Areas to strengthen/)
  assert.match(html, /Build a cash buffer/)
  assert.match(html, /Illustrative project criterion/)
  assert.match(html, /Last evaluated/)
  assert.match(html, /What changed/)
  assert.doesNotMatch(html, /guaranteed approval/i)
})
