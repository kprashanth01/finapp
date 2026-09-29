// Synchronous exclusion covers clicks before a React state update is rendered.
export function createOperationGate() {
  let active = null
  return {
    begin() {
      if (active) return null
      const token = {}
      active = token
      return () => { if (active === token) active = null }
    },
  }
}
