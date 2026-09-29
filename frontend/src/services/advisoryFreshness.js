const financialFields = [
  'monthly_expenses',
  'savings',
  'existing_debt',
  'emergency_fund',
  'monthly_savings_contribution',
  'monthly_debt_payments',
  'risk_tolerance',
  'financial_goal',
  'investment_horizon_years',
]

export function canStartRun({ saving, loading, running }) {
  return !saving && !loading && !running
}

export function canStartSave({ saving, running }) {
  return !saving && !running
}

export function hasIncomeChanged(before, after) {
  return Number(before.monthly_income) !== Number(after.monthly_income)
}

export function hasProfileFinancialChanges(before, after) {
  if (!before) return true
  return financialFields.some((field) => String(before[field] ?? '') !== String(after[field] ?? ''))
}

export function markSessionStale(session, changed) {
  return session && changed ? { ...session, is_stale: true, stale_reasons: [...new Set([...(session.stale_reasons ?? []), 'inputs'])] } : session
}
