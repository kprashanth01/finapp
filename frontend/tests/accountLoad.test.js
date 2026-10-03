import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveAccountLoad } from '../src/services/accountLoad.js'

test('a missing profile is a genuine first-use state after the account loads', async () => {
  const result = await resolveAccountLoad(7, {
    getUser: async () => ({ id: 7, name: 'Sam' }),
    getFinancialProfile: async () => { throw { response: { status: 404 } } },
  })
  assert.deepEqual(result, { status: 'ready', user: { id: 7, name: 'Sam' }, profile: null })
})

test('a failed profile request cannot become an empty first-use state', async () => {
  const failure = new Error('connection lost')
  const result = await resolveAccountLoad(7, {
    getUser: async () => ({ id: 7, name: 'Sam' }),
    getFinancialProfile: async () => { throw failure },
  })
  assert.equal(result.status, 'error')
  assert.equal(result.error, failure)
  assert.equal(Object.hasOwn(result, 'profile'), false)
})
