import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let FinancialDetails
let detailsPayload

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/FinancialDetails.jsx')
  FinancialDetails = module.default
  detailsPayload = module.detailsPayload
})
after(async () => { await server?.close() })

test('Profile offers optional detail without making the base profile depend on it', () => {
  const html = renderToStaticMarkup(createElement(FinancialDetails, {
    userId: 1, user: { monthly_income: '50000.00' },
    profile: { monthly_expenses: '30000.00', existing_debt: '100000.00' },
    onOpenMonths() {},
  }))
  assert.match(html, /Optional financial details/)
  assert.match(html, /not added to your monthly expenses or debt again/)
  assert.match(html, /current plan still uses the Profile totals/)
})

test('detail submission preserves row identity and leaves unknown values unknown', () => {
  const payload = detailsPayload({
    income_pattern: '', guaranteed_monthly_income: '',
    recurring_expenses: [{ id: 7, name: ' Rent ', monthly_amount: '14000', category: 'essential_fixed' }],
    loans: [{ name: 'Loan', loan_type: '', remaining_balance: '', monthly_payment: '',
      annual_interest_rate_percent: '', payment_day: '', rate_change_date: '',
      new_annual_interest_rate_percent: '' }],
    planned_expenses: [{ name: ' Trip ', estimated_amount: '20000', amount_reserved: '',
      due_date: '2027-06-01', is_essential: false }],
  })
  assert.equal(payload.income_pattern, null)
  assert.equal(payload.guaranteed_monthly_income, null)
  assert.deepEqual(payload.recurring_expenses[0], {
    id: 7, name: 'Rent', monthly_amount: '14000', category: 'essential_fixed',
  })
  assert.equal(payload.loans[0].payment_day, null)
  assert.equal(payload.loans[0].monthly_payment, null)
  assert.equal(payload.loans[0].remaining_balance, null)
  assert.equal(payload.loans[0].annual_interest_rate_percent, null)
  assert.equal(payload.planned_expenses[0].name, 'Trip')
  assert.equal(payload.planned_expenses[0].amount_reserved, null)
  assert.equal('monthly_expenses' in payload, false)
})
