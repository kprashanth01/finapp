function Metric({ title, value, unit, formula, missing }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-sm font-medium text-slate-700">{title}</h3>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value == null ? 'Unavailable' : `${value}${unit}`}</p>
      <p className="mt-2 text-xs text-slate-600">{value == null ? missing : formula}</p>
    </div>
  )
}

function FinancialAnalysis({ analysis, user, profile }) {
  if (!analysis) {
    return <p className="mt-8 text-sm text-slate-600">Analysis is unavailable. Check the API connection and try reloading.</p>
  }

  const needsIncome = Number(user.monthly_income) <= 0
  const needsExpenses = Number(profile.monthly_expenses) <= 0

  return (
    <section className="mt-10 border-t border-slate-200 pt-8" aria-labelledby="analysis-heading">
      <h2 id="analysis-heading" className="text-xl font-semibold">3. Financial snapshot</h2>
      <p className="mt-1 text-sm text-slate-600">Calculated from your saved values. No advice or predictions are generated.</p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Metric
          title="Savings rate"
          value={analysis.savings_rate_percent}
          unit="%"
          formula="Monthly savings contribution ÷ gross monthly income"
          missing={needsIncome ? 'Gross monthly income must be above zero.' : 'Add monthly savings contribution to your profile.'}
        />
        <Metric
          title="Debt-to-income ratio"
          value={analysis.debt_to_income_percent}
          unit="%"
          formula="Monthly debt payments ÷ gross monthly income"
          missing={needsIncome ? 'Gross monthly income must be above zero.' : 'Add monthly debt payments to your profile.'}
        />
        <Metric
          title="Expense-to-income ratio"
          value={analysis.expense_to_income_percent}
          unit="%"
          formula="Monthly expenses ÷ gross monthly income"
          missing="Gross monthly income must be above zero."
        />
        <Metric
          title="Emergency fund coverage"
          value={analysis.emergency_fund_months}
          unit=" months"
          formula="Emergency fund balance ÷ monthly expenses"
          missing={needsExpenses ? 'Monthly expenses must be above zero.' : 'Enter an emergency fund and monthly expenses.'}
        />
      </div>

      <div className="mt-5 rounded-lg border border-slate-200 p-5">
        <h3 className="text-sm font-medium text-slate-700">Educational health score</h3>
        <p className="mt-1 text-3xl font-semibold">
          {analysis.health_score == null ? 'Unavailable' : `${analysis.health_score} / 100`}
        </p>
        <p className="mt-2 text-sm text-slate-600">
          {analysis.health_score == null
            ? 'The score needs positive income and expenses plus both monthly savings and debt-payment inputs.'
            : 'Fixed project heuristic: up to 30 points for savings rate, 30 for lower debt payments, and 40 for emergency coverage.'}
        </p>
        <p className="mt-2 text-xs text-slate-500">Full savings points at 20%; debt points fall to zero at 50% DTI; full emergency points at 6 months. These are illustrative thresholds, not validated financial advice.</p>
      </div>
    </section>
  )
}

export default FinancialAnalysis
