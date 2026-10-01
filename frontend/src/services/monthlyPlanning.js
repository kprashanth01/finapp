const cents = (value) => Math.round(Number(value ?? 0) * 100)

export function summarizeMonths(months, profile) {
  if (!months.length) return null
  const recent = [...months].sort((a, b) => a.period.localeCompare(b.period)).slice(-12)
  const latest = recent.at(-1)
  const lowest = recent.reduce((low, month) => cents(month.monthly_income) < cents(low.monthly_income) ? month : low)
  const latestRemainderCents = cents(latest.monthly_income) - cents(latest.monthly_expenses)
  const latestObligationsCents = cents(latest.fixed_expenses) + cents(latest.scheduled_emi)
  const lowIncomeAfterObligationsCents = cents(lowest.monthly_income) - latestObligationsCents
  return {
    latest, lowest, sampleCount: recent.length, latestRemainderCents, latestObligationsCents,
    plannedContributionCents: profile?.monthly_savings_contribution == null ? null : cents(profile.monthly_savings_contribution),
    lowIncomeAfterObligationsCents,
    lowIncomeObligationGapCents: Math.max(0, -lowIncomeAfterObligationsCents),
  }
}
