import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let RecordedMonthPlan
let monthSavingsLimit
let unpaidObligations
let estimateMonthContribution
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  RecordedMonthPlan = (await server.ssrLoadModule('/src/components/RecordedMonthPlan.jsx')).default
  ;({ monthSavingsLimit, unpaidObligations, estimateMonthContribution } = await server.ssrLoadModule('/src/services/monthlyPlanning.js'))
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

test('worksheet requires explicit costs and held cash, then caps the possible plan amount', () => {
  assert.equal(estimateMonthContribution(month, '', ''), null)
  assert.equal(estimateMonthContribution(month, '0', ''), null)
  assert.deepEqual(estimateMonthContribution(month, '0', '0'),
    { possibleCents: 50000, overByCents: 0 })
  assert.deepEqual(estimateMonthContribution(month, '75.25', '100.00'),
    { possibleCents: 32475, overByCents: 0 })
  assert.deepEqual(estimateMonthContribution(month, '600', '100'),
    { possibleCents: 0, overByCents: 20000 })
  assert.deepEqual(estimateMonthContribution({ ...month, monthly_income: '1500' }, '0', '0'),
    { possibleCents: 0, overByCents: 0 })
  assert.equal(estimateMonthContribution(month, '-1', '0'), null)
  assert.equal(estimateMonthContribution(month, '0.001', '0'), null)
})

test('recorded-month plan explains the worksheet and keeps a manual amount available', () => {
  const html = renderToStaticMarkup(createElement(RecordedMonthPlan, {
    months: [month], userId: 1, onOpenProfile() {}, onOpenGoal() {},
  }))
  assert.match(html, /Work out an amount to plan with/)
  assert.match(html, /Costs not included in recorded spending/)
  assert.match(html, /Keep unallocated from this remainder/)
  assert.match(html, /Enter 0 if none/)
  assert.match(html, /Amount you can actually set aside/)
  assert.match(html, /not a savings recommendation/)
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
