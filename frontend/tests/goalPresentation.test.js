import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let AdvisoryPlan
let GoalForm
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  AdvisoryPlan = (await server.ssrLoadModule('/src/components/AdvisoryPlan.jsx')).default
  GoalForm = (await server.ssrLoadModule('/src/components/GoalForm.jsx')).default
})
after(async () => { await server?.close() })

function savedResult(savedAmount, months) {
  return {
    state: { as_of_date: '2026-09-29' },
    advice: {
      summary: { title: 'Review goal', text: 'Saved plan', next_action: { view: 'goals' } },
      monthly_plan: { capacity: '500', emergency_allocation: '0', unassigned: '0', hold_reason: null,
        goal_allocations: [{ status: 'budget_covered', allocated_monthly: '416.67', funding_gap: '0',
          requirement: { goal: { id: 1, name: 'Course', target_amount: '6000', saved_amount: savedAmount,
            target_date: '2027-09-24', priority: 'high' }, remaining_amount: String(6000 - Number(savedAmount)),
            required_monthly: '416.67', approximate_months: months, status: 'future' } }] },
      investment: { status: 'ready_to_consider', category: 'moderate', reasons: [] }, priority_actions: [],
    },
  }
}

function visibleText(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')
}

test('past and current plans display their own saved progress and month estimate', () => {
  const earlier = savedResult('1000', 12)
  const current = savedResult('3000', 6)
  const pastText = visibleText(createElement(AdvisoryPlan, { result: earlier }))
  const currentText = visibleText(createElement(AdvisoryPlan, { result: current }))
  assert.match(pastText, /Saved at this run 1,000\.00/)
  assert.match(pastText, /Target amount 6,000\.00/)
  assert.match(pastText, /Approximate months remaining 12/)
  assert.match(currentText, /Saved at this run 3,000\.00/)
  assert.match(currentText, /Approximate months remaining 6/)
  assert.doesNotMatch(pastText, /Saved at this run 3,000\.00/)
})

test('saved-goal input explains exclusive earmarks and the verification limit', () => {
  const markup = renderToStaticMarkup(createElement(GoalForm, {}))
  const text = visibleText(createElement(GoalForm, {}))
  const savedInput = markup.match(/<input\b[^>]*name="saved_amount"[^>]*>/)[0]
  assert.match(savedInput, /aria-describedby="goal-earmark-help"/)
  assert.match(text, /Exclude your emergency reserve and money already assigned to another goal/)
  assert.match(text, /The app cannot verify whether these amounts overlap/)
})

test('Advisor shows specialist findings as situation, impact, and next step after the coordinated plan', () => {
  const result = savedResult('1000', 12)
  result.agent_results = ['budget', 'debt', 'emergency', 'goal', 'risk', 'investment'].map((agent_id) => ({
    agent_id, findings: [{ code: agent_id, title: `${agent_id} check`, reason: `Recorded ${agent_id} situation.`,
      impact: `Why ${agent_id} matters.`, suggested_action: `Review ${agent_id} next.`,
      evidence: [{ label: 'Coverage', value: '1.25', unit: 'months' }], limitations: [] }],
  }))
  const text = visibleText(createElement(AdvisoryPlan, { result }))
  assert.match(text, /What each check found/)
  assert.ok(text.indexOf('Your monthly savings plan') < text.indexOf('What each check found'))
  for (const agent of result.agent_results) {
    assert.match(text, new RegExp(`Recorded ${agent.agent_id} situation`))
    assert.match(text, new RegExp(`Why ${agent.agent_id} matters`))
    assert.match(text, new RegExp(`Review ${agent.agent_id} next`))
  }
  assert.match(text, /Coverage: 1\.25 months/)
})

test('underfunded goal explains the deadline and allocation choices from its saved plan', () => {
  const result = savedResult('0', 12)
  const allocation = result.advice.monthly_plan.goal_allocations[0]
  allocation.status = 'underfunded'
  allocation.allocated_monthly = '200.00'
  allocation.funding_gap = '300.00'
  allocation.requirement.required_monthly = '500.00'
  const text = visibleText(createElement(AdvisoryPlan, { result }))
  assert.match(text, /Keep the target date/)
  assert.match(text, /this goal needs 300\.00 more per month than this plan assigns/)
  assert.match(text, /Keep the current goal allocation/)
  assert.match(text, /about 30 months/)
  assert.match(text, /Mar 2029/)
  assert.match(text, /does not mean that extra money is available/)
  assert.match(text, /not to an extra pool of money/)
  assert.match(text, /Review monthly savings contribution/)
})

test('zero goal allocation shows no projected completion date', () => {
  const result = savedResult('0', 12)
  const allocation = result.advice.monthly_plan.goal_allocations[0]
  allocation.status = 'underfunded'
  allocation.allocated_monthly = '0.00'
  allocation.funding_gap = '500.00'
  allocation.requirement.required_monthly = '500.00'
  const text = visibleText(createElement(AdvisoryPlan, { result }))
  assert.match(text, /No completion date can be estimated from a zero monthly allocation/)
  assert.doesNotMatch(text, /around Mar 2029/)
})

test('goal timing uses the historical plan date and stays hidden for a covered goal', () => {
  const earlier = savedResult('0', 12)
  const allocation = earlier.advice.monthly_plan.goal_allocations[0]
  allocation.status = 'underfunded'
  allocation.allocated_monthly = '200.00'
  allocation.funding_gap = '300.00'
  allocation.requirement.required_monthly = '500.00'
  const later = structuredClone(earlier)
  later.state.as_of_date = '2027-09-29'
  assert.match(visibleText(createElement(AdvisoryPlan, { result: earlier })), /Mar 2029/)
  assert.match(visibleText(createElement(AdvisoryPlan, { result: later })), /Mar 2030/)
  assert.doesNotMatch(visibleText(createElement(AdvisoryPlan, { result: savedResult('1000', 12) })), /Keep the target date/)
})
