import test from 'node:test'
import assert from 'node:assert/strict'
import {
  canStartRun,
  canStartSave,
  hasIncomeChanged,
  hasProfileFinancialChanges,
  markSessionStale,
} from '../src/services/advisoryFreshness.js'

test('saves and runs cannot overlap', () => {
  assert.equal(canStartRun({ saving: true, loading: false, running: false }), false)
  assert.equal(canStartRun({ saving: false, loading: true, running: false }), false)
  assert.equal(canStartSave({ saving: false, running: true }), false)
  assert.equal(canStartRun({ saving: false, loading: false, running: false }), true)
  assert.equal(canStartSave({ saving: false, running: false }), true)
})

test('only a changed saved financial value marks the prior session stale', () => {
  const before = { monthly_expenses: '3000.00', emergency_fund: '4000.00', risk_tolerance: 'moderate' }
  assert.equal(hasProfileFinancialChanges(before, { ...before }), false)
  assert.equal(hasProfileFinancialChanges(before, { ...before, emergency_fund: '12000.00' }), true)
  assert.equal(hasIncomeChanged({ monthly_income: '5000.00' }, { monthly_income: '5000' }), false)
  assert.equal(hasIncomeChanged({ monthly_income: '5000.00' }, { monthly_income: '5200.00' }), true)

  const session = { id: 1, is_stale: false, result: { priority_actions: ['old finding'] } }
  assert.deepEqual(markSessionStale(session, true), { ...session, is_stale: true, stale_reasons: ['inputs'] })
  assert.deepEqual(markSessionStale(session, false), session)
  assert.deepEqual(markSessionStale(null, true), null)
})
