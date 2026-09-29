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
