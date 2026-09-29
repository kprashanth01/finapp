import test from 'node:test'
import assert from 'node:assert/strict'
import { createOperationGate } from '../src/services/operationGate.js'

test('rapid saves and runs cannot overlap before React renders', () => {
  const gate = createOperationGate()
  const first = gate.begin()
  assert.equal(typeof first, 'function')
  assert.equal(gate.begin(), null)
  first()
  const second = gate.begin()
  first() // An old completion must not release a newer operation.
  assert.equal(gate.begin(), null)
  second()
  assert.equal(typeof gate.begin(), 'function')
})
