import assert from 'node:assert/strict'
import test from 'node:test'
import { getDashboardDisplayState } from '../src/services/dashboardState.js'

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
