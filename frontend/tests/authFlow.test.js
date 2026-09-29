import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let AuthScreen
let resolveBootState
let createAuthRequestGate
let subscribeToAuthChanges
let settleAuthSuccess
let api
let defaultApiBaseUrl

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  AuthScreen = (await server.ssrLoadModule('/src/components/AuthScreen.jsx')).default
  ;({ resolveBootState, createAuthRequestGate, subscribeToAuthChanges, settleAuthSuccess } = await server.ssrLoadModule('/src/services/authState.js'))
  ;({ api, defaultApiBaseUrl } = await server.ssrLoadModule('/src/services/api.js'))
})
after(async () => { await server?.close() })

function markup(mode) {
  return renderToStaticMarkup(createElement(AuthScreen, { mode, onMode: () => {}, onSubmit: () => {} }))
}

test('signup asks only for account details, and claim never trusts a browser user ID', () => {
  const signup = markup('signup')
  assert.match(signup, /name="name"/)
  assert.match(signup, /name="email"/)
  assert.match(signup, /name="password"/)
  assert.doesNotMatch(signup, /monthly_income|Gross monthly income/)
  const claim = markup('claim')
  assert.match(claim, /name="code"/)
  assert.match(claim, /one-time|one time/i)
  assert.doesNotMatch(claim, /name="userId"|name="user_id"/)
})

test('boot separates signed-out status from unavailable API, and old auth work cannot win', async () => {
  const signedOut = await resolveBootState(async () => { throw { response: { status: 401 } } })
  assert.deepEqual(signedOut, { status: 'signedOut', user: null })
  const unavailable = await resolveBootState(async () => { throw new Error('offline') })
  assert.equal(unavailable.status, 'unavailable')
  const gate = createAuthRequestGate()
  assert.equal(gate.current(), 0)
  const first = gate.begin()
  const second = gate.begin()
  assert.equal(gate.isCurrent(first), false)
  assert.equal(gate.isCurrent(second), true)
  gate.invalidate()
  assert.equal(gate.isCurrent(second), false)
  assert.equal(gate.current(), 3)
})

test('API uses browser cookies and sends a mutation header', () => {
  assert.equal(api.defaults.withCredentials, true)
  assert.equal(api.defaults.headers['X-FinApp-Request'], '1')
})

test('local API uses the same hostname as the page so strict session cookies are sent', () => {
  assert.equal(defaultApiBaseUrl({ protocol: 'http:', hostname: '127.0.0.1' }), 'http://127.0.0.1:8000')
  assert.equal(defaultApiBaseUrl({ protocol: 'http:', hostname: 'localhost' }), 'http://localhost:8000')
})

test('another tab changing account immediately invalidates its displayed workspace', () => {
  let changes = 0
  const channel = { onmessage: null, close() { this.closed = true } }
  const unsubscribe = subscribeToAuthChanges(channel, () => { changes += 1 })
  channel.onmessage({ data: { type: 'account-changed' } })
  assert.equal(changes, 1)
  channel.onmessage({ data: { type: 'unrelated' } })
  assert.equal(changes, 1)
  unsubscribe()
  assert.equal(channel.closed, true)
})

test('a delayed login success reconciles both tabs after another tab changed the cookie', async () => {
  const gate = createAuthRequestGate()
  const token = gate.begin()
  let releaseLogin
  const delayedLogin = new Promise((resolve) => { releaseLogin = resolve })
  let cookieAccount = 'B'
  const shown = { first: 'B', second: 'B' }
  let broadcasts = 0
  const firstTab = delayedLogin.then(async (account) => {
    cookieAccount = account
    await settleAuthSuccess(gate, token,
      () => { shown.first = account },
      async () => {
        shown.first = (await resolveBootState(async () => cookieAccount)).user
        broadcasts += 1
        shown.second = (await resolveBootState(async () => cookieAccount)).user
      })
  })
  gate.invalidate() // Tab 2 signed in to B while tab 1's login to A was in flight.
  releaseLogin('A')
  await firstTab
  assert.equal(broadcasts, 1)
  assert.deepEqual(shown, { first: 'A', second: 'A' })
})
