import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let EventComparison
let buildEventPayload
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  const module = await server.ssrLoadModule('/src/components/EventScenario.jsx')
  EventComparison = module.EventComparison
  buildEventPayload = module.buildEventPayload
})
after(async () => { await server?.close() })

const fact = (value) => ({ value })
function picture(expenses, oneTime) {
  return {
    income: { expected_monthly: fact('5000') },
    spending: { monthly_total: fact(expenses), gross_cash_flow: fact('2000'),
      available_surplus_upper_bound: fact('2000'), entered_savings_capacity: fact('500') },
    reserve: { funding_gap: fact('5000') },
    planned_due_90_days: fact(oneTime),
    unreserved_due_90_days: fact(oneTime),
  }
}

test('one-time event comparison keeps recurring expenses separate and names cash needed', () => {
  const html = renderToStaticMarkup(createElement(EventComparison, { result: {
    event: { kind: 'upcoming_expense', due_date: '2026-11-01' },
    before: picture('3000', '0'), after: picture('3000', '900'),
    one_time_cash_need: '700', illustrative_current_month_cash_after_event: null,
    loan_effect: null, goal_effect: null, limitations: ['Not a forecast.'],
  } }))
  assert.match(html, /One-time cash needed beyond the entered reserved amount/)
  assert.match(html, /700\.00/)
  assert.match(html, /Recurring monthly expenses/)
  assert.match(html, /not added to recurring monthly expenses/)
  assert.doesNotMatch(html, /Illustrative gross cash after this month/)
  assert.match(html, /Not a forecast/)
})

test('event payload sends only fields relevant to the chosen change', () => {
  const values = { kind: 'subscription_reduction', amount: '60', expense_id: '4',
    loan_id: '8', goal_id: '9', due_date: '2027-01-01', reserved_amount: '20', name: 'Other' }
  assert.deepEqual(buildEventPayload(values), { kind: 'subscription_reduction', amount: '60', expense_id: 4 })
  assert.deepEqual(buildEventPayload({ ...values, kind: 'upcoming_expense', name: 'Trip' }), {
    kind: 'upcoming_expense', amount: '60', reserved_amount: '20', name: 'Trip', due_date: '2027-01-01',
  })
})
