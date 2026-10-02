import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let CurrentChatReply
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  CurrentChatReply = (await server.ssrLoadModule('/src/components/CurrentChat.jsx')).CurrentChatReply
})
after(async () => { await server?.close() })

const fact = (value) => ({ value })
const picture = (cash) => ({
  income: { expected_monthly: fact('5000') },
  spending: { monthly_total: fact('3000'), gross_cash_flow: fact(cash),
    available_surplus_upper_bound: fact(cash), entered_savings_capacity: fact('500') },
  reserve: { funding_gap: fact('5000') },
  planned_due_90_days: fact('0'), unreserved_due_90_days: fact('0'),
})

test('a conversational scenario shows the calculated comparison and changed first action', () => {
  const item = { question: 'What if I earn 2000 next month?', response: {
    source: 'current_picture', as_of_date: '2026-10-03', topic: 'scenario',
    answer: 'Preview only, not saved.', evidence: [],
    before_priority: 'Review emergency reserve', after_priority: 'Review cash shortfall',
    scenario: { event: { kind: 'income_decrease', amount: '3000' },
      before: picture('2000'), after: picture('-1000'),
      one_time_cash_need: '0', one_time_cash_inflow: '0',
      illustrative_current_month_cash_after_event: null,
      loan_effect: null, goal_effect: null, limitations: ['Not saved.'] },
  } }
  const html = renderToStaticMarkup(createElement(CurrentChatReply, { item }))
  assert.match(html, /Temporary scenario/)
  assert.match(html, /Review emergency reserve/)
  assert.match(html, /Review cash shortfall/)
  assert.match(html, /Saved picture/)
  assert.match(html, /With this event/)
  assert.match(html, /-1,000\.00/)
})
