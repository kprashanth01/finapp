import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let summarizeMonths
let MonthlyPlanningSummary
let AccountMonths
let AppShell
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ;({ summarizeMonths } = await server.ssrLoadModule('/src/services/monthlyPlanning.js'))
  MonthlyPlanningSummary = (await server.ssrLoadModule('/src/components/MonthlyPlanningSummary.jsx')).default
  AccountMonths = (await server.ssrLoadModule('/src/components/AccountMonths.jsx')).default
  AppShell = (await server.ssrLoadModule('/src/components/AppShell.jsx')).default
})
after(async () => { await server?.close() })

const months = [
  { period: '2026-07-01', monthly_income: '2200.00', monthly_expenses: '2500.00', fixed_expenses: '1600.00', scheduled_emi: '200.00' },
  { period: '2026-09-01', monthly_income: '3500.00', monthly_expenses: '3200.00', fixed_expenses: '2300.00', scheduled_emi: '300.00' },
]

test('latest recorded cash flow is compared with the saved contribution and low-income obligations', () => {
  const summary = summarizeMonths(months, { monthly_savings_contribution: '500.00' })
  assert.equal(summary.latest.period, '2026-09-01')
  assert.equal(summary.latestRemainderCents, 30000)
  assert.equal(summary.plannedContributionCents, 50000)
  assert.equal(summary.lowest.period, '2026-07-01')
  assert.equal(summary.lowIncomeObligationGapCents, 40000)
  assert.equal(summary.lowIncomeAfterObligationsCents, -40000)
  assert.deepEqual(months.map((month) => month.period), ['2026-07-01', '2026-09-01'])
})

test('monthly guidance names a review action and labels the low-income comparison as hypothetical', () => {
  const html = renderToStaticMarkup(createElement(MonthlyPlanningSummary, {
    months, profile: { monthly_savings_contribution: '500.00' }, onOpenProfile() {},
  }))
  assert.match(html, /Latest entered month/)
  assert.match(html, /300\.00 left after entered spending/)
  assert.match(html, /Profile plans 500\.00 in monthly savings/)
  assert.match(html, /Review planned savings in Profile/)
  assert.match(html, /If the lowest recorded income recurred/)
  assert.match(html, /400\.00 short of those essential obligations/)
  assert.match(html, /worksheet below/)
  assert.match(html, /not a forecast/)
  assert.doesNotMatch(html, /DQN|reward|proxy score/)
})

test('one month and no planned contribution still explain what is known', () => {
  const html = renderToStaticMarkup(createElement(MonthlyPlanningSummary, {
    months: [months[1]], profile: { monthly_savings_contribution: null }, onOpenProfile() {},
  }))
  assert.match(html, /Add a planned monthly savings amount in Profile/)
  assert.doesNotMatch(html, /lowest recorded income recurred/)
})

test('low recorded income above essential obligations shows the remaining amount without calling it savings', () => {
  const html = renderToStaticMarkup(createElement(MonthlyPlanningSummary, {
    months: [{ ...months[0], monthly_income: '3000.00' }, months[1]],
    profile: { monthly_savings_contribution: '100.00' }, onOpenProfile() {},
  }))
  assert.match(html, /400\.00 above those obligations before other spending/)
  assert.doesNotMatch(html, /400\.00 short of those essential obligations/)
})

test('monthly records are available from primary navigation without research advice on the planning screen', () => {
  const shell = renderToStaticMarkup(createElement(AppShell, { activeView: 'months', user: { name: 'Sam' }, connection: 'connected',
    onChangeView() {}, onRetryConnection() {}, onSignOut() {}, children: null }))
  assert.match(shell, /Months/)
  assert.match(shell, /Research/)
  const record = renderToStaticMarkup(createElement(AccountMonths, {
    mode: 'planning', userId: 1, user: { monthly_income: '3500' },
    profile: { monthly_expenses: '3200', monthly_debt_payments: '300', savings: '5000', emergency_fund: '2000',
      existing_debt: '1000', risk_tolerance: 'moderate', investment_horizon_years: 5 },
  }))
  assert.match(record, /Plan for changing income/)
  assert.match(record, /Save this month/)
  assert.match(record, /Balances and payments for this month/)
  assert.doesNotMatch(record, /Additional month details/)
  assert.doesNotMatch(record, /DQN|trained selector|proxy score/)
})
