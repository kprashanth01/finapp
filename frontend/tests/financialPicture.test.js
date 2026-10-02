import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let FinancialPicture
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  FinancialPicture = (await server.ssrLoadModule('/src/components/FinancialPicture.jsx')).default
})
after(async () => { await server?.close() })

test('financial picture shows source, unknowns, and gross surplus limit', () => {
  const fact = (value, source = 'recorded_months.last_12', status = 'known') =>
    ({ value, source, status, note: 'Sample note.' })
  const html = renderToStaticMarkup(createElement(FinancialPicture, { picture: {
    as_of_date: '2026-10-02',
    income: { observed_months: 0, recent_period: null, expected_monthly: fact('5000', 'user.current_income_estimate'),
      guaranteed_monthly: fact(null), observed_average: fact(null), observed_recent: fact(null),
      observed_minimum: fact(null), variability_percent: fact(null), conservative_reference: fact(null) },
    spending: { gross_cash_flow: fact('2000', 'current_income_estimate_minus_profile_expenses'),
      available_surplus_upper_bound: fact('2000', 'gross_cash_flow', 'estimate'), monthly_total: fact('3000'),
      known_essential_fixed: fact('1000', 'expense_details', 'partial'), known_essential_variable: fact('0', 'expense_details', 'partial'),
      known_essential: fact('1000', 'expense_details', 'partial'), known_discretionary: fact('0'),
      unclassified_monthly: fact(null), exact_essential: fact(null), exact_discretionary: fact(null),
      entered_savings_capacity: fact(null), savings_rate_percent: fact(null), debt_to_income_percent: fact(null) },
    reserve: { funding_gap: fact('5000'), total_expense_coverage_months: fact('1.33'),
      essential_coverage_months: fact(null) },
    goal_funding_gap: fact('0'), planned_due_90_days: fact('0'), unreserved_due_90_days: fact(null),
    goals: [], obligations: [], limitations: [],
  } }))
  assert.match(html, /Deeper financial analysis/)
  assert.match(html, /Possible surplus ceiling/)
  assert.match(html, /Unknown/)
  assert.match(html, /Known essential spending/)
  assert.match(html, /known so far/)
  assert.match(html, /Source: Recorded Months/)
})
