export function formatAmount(value) {
  return value == null ? 'Not supplied' : Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function staleMessage(session) {
  const reasons = session?.stale_reasons ?? []
  if (!session?.is_stale) return ''
  const labels = { inputs: 'Saved inputs changed.', planning_date: 'The planning date has moved on.', rule_version: 'An updated analysis method is available.' }
  return `${reasons.length ? reasons.map((r) => labels[r]).join(' ') : 'Saved inputs changed.'} Run analysis again to update this saved plan.`
}
