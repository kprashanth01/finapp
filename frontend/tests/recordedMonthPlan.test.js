import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let RecordedMonthPlan
let monthSavingsLimit
let unpaidObligations
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  RecordedMonthPlan = (await server.ssrLoadModule('/src/components/RecordedMonthPlan.jsx')).default
  ;({ monthSavingsLimit, unpaidObligations } = await server.ssrLoadModule('/src/services/monthlyPlanning.js'))
})
after(async () => { await server?.close() })

const month = { period: '2026-09-01', monthly_income: '3500.00', monthly_expenses: '3000.00',
  scheduled_emi: '300.00', paid_emi: '300.00', unfunded_expenses: '0.00' }

test('month plan asks for actual savings and distinguishes recorded figures from current goals', () => {
  const html = renderToStaticMarkup(createElement(RecordedMonthPlan, {
    months: [month], userId: 1, onOpenProfile() {}, onOpenGoal() {},
  }))
  assert.match(html, /Preview a plan for a recorded month/)
  assert.match(html, /Amount you can actually set aside/)
  assert.match(html, /500\.00/)
  assert.match(html, /current saved goals/)
  assert.match(html, /does not change your Profile or saved Advisor plan/)
  assert.doesNotMatch(html, /DQN|reward|proxy score/)
})

test('gross remainder is only an upper bound and a shortfall permits no funded allocation', () => {
  assert.equal(monthSavingsLimit(month), 50000)
  assert.equal(monthSavingsLimit({ ...month, monthly_income: '1500.00' }), 0)
  assert.equal(monthSavingsLimit({ ...month, monthly_income: '3000.00' }), 0)
})

test('a missed loan payment or unfunded bill stops a funded preview', () => {
  assert.equal(unpaidObligations({ ...month, paid_emi: '100.00', unfunded_expenses: '0.00' }), 'loan')
  assert.equal(unpaidObligations({ ...month, paid_emi: '300.00', unfunded_expenses: '50.00' }), 'bills')
  assert.equal(unpaidObligations({ ...month, paid_emi: '300.00', unfunded_expenses: '0.00' }), null)
})

test('a selected month with a cash shortfall says no new savings can be funded', () => {
  const html = renderToStaticMarkup(createElement(RecordedMonthPlan, {
    months: [{ ...month, monthly_income: '1500.00' }], userId: 1,
    onOpenProfile() {}, onOpenGoal() {},
  }))
  assert.match(html, /Entered spending exceeded income by 1,500\.00/)
  assert.match(html, /no room in these figures for a new savings contribution/)
})
