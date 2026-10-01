import assert from 'node:assert/strict'
import test from 'node:test'
import { getDashboardDecision, getDashboardDisplayState } from '../src/services/dashboardState.js'

test('a profile refresh hides values until the corresponding analysis is ready', () => {
  const state = getDashboardDisplayState({
    saving: true,
    analysis: { expense_to_income_percent: 60 },
    advisorySession: { id: 1 },
  })

  assert.equal(state.updating, true)
})

test('a failed latest-run request is never presented as an empty history', () => {
  const state = getDashboardDisplayState({
    analysis: {},
    advisoryError: 'Request failed',
    advisorySession: null,
  })

  assert.equal(state.latest, 'error')
})

test('loading, saved, and confirmed empty latest-run states remain distinct', () => {
  assert.equal(getDashboardDisplayState({ advisoryLoading: true }).latest, 'loading')
  assert.equal(getDashboardDisplayState({ advisorySession: { id: 1 } }).latest, 'saved')
  assert.equal(getDashboardDisplayState({ advisorySession: null }).latest, 'empty')
})

test('an outdated run cannot supply a current dashboard decision or allocation', () => {
  const oldRun = { is_stale: true, result: { advice: {
    priority_actions: [{ title: 'Review emergency reserve' }],
    monthly_plan: { capacity: '500.00', emergency_allocation: '500.00' },
  } } }

  assert.equal(getDashboardDecision(oldRun), null)
})

test('a current dashboard decision retains the coordinated allocation and its supporting fact', () => {
  const session = { is_stale: false, result: {
    advice: {
      summary: { title: 'Review emergency reserve' },
      priority_actions: [
        { code: 'review_emergency', title: 'Review emergency reserve', reason: 'Coverage is below the illustrative target.', source_refs: [{ agent_id: 'emergency', finding_code: 'emergency_gap' }], next_action: { view: 'profile', field: 'emergency_fund' } },
        { code: 'review_goal_1', title: 'Review laptop goal', reason: 'Monthly plan is short.', source_refs: [], next_action: { view: 'goals', goal_id: 1 } },
      ],
      monthly_plan: { capacity: '500.00', emergency_allocation: '400.00', goal_allocations: [{ requirement: { goal: { id: 1, name: 'Laptop' } }, allocated_monthly: '100.00' }], unassigned: '0.00', hold_reason: null },
    },
    agent_results: [{ agent_id: 'emergency', findings: [{ code: 'emergency_gap', evidence: [{ label: 'Emergency fund coverage', value: '1.33', unit: 'months' }] }] }],
  } }

  const decision = getDashboardDecision(session)
  assert.equal(decision.primary.title, 'Review emergency reserve')
  assert.deepEqual(decision.evidence, { label: 'Emergency fund coverage', value: '1.33', unit: 'months' })
  assert.equal(decision.otherPriorities[0].title, 'Review laptop goal')
  assert.deepEqual(decision.plan, session.result.advice.monthly_plan)
})

test('a missing contribution stays unknown in the dashboard plan', () => {
  const session = { is_stale: false, result: { advice: {
    summary: { title: 'Add a monthly savings budget' }, priority_actions: [],
    monthly_plan: { capacity: null, emergency_allocation: null, goal_allocations: [], unassigned: null, hold_reason: null },
  }, agent_results: [] } }
  assert.equal(getDashboardDecision(session).plan.capacity, null)
})
