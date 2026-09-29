export async function resolveBootState(getCurrentUser) {
  try { return { status: 'signedIn', user: await getCurrentUser() } }
  catch (error) {
    if (error.response?.status === 401) return { status: 'signedOut', user: null }
    return { status: 'unavailable', user: null }
  }
}

export function createAuthRequestGate() {
  let generation = 0
  return {
    begin() { return ++generation },
    current() { return generation },
    isCurrent(value) { return generation === value },
    invalidate() { generation += 1 },
  }
}

export const identityEpoch = createAuthRequestGate()

export function subscribeToAuthChanges(channel, onChange) {
  channel.onmessage = (event) => {
    if (event.data?.type === 'account-changed') onChange()
  }
  return () => { channel.onmessage = null; channel.close() }
}

export async function settleAuthSuccess(gate, token, applyCurrent, reconcileStale) {
  if (gate.isCurrent(token)) await applyCurrent()
  else await reconcileStale()
}
