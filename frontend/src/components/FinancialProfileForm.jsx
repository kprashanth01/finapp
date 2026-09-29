import { useState } from 'react'

const inputClass = 'mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-200'
const labelClass = 'block text-sm font-medium text-slate-700'

function FinancialProfileForm({ profile, onSave, saving, disabled }) {
  const [fields, setFields] = useState({
    monthly_expenses: profile?.monthly_expenses ?? '',
    savings: profile?.savings ?? '',
    existing_debt: profile?.existing_debt ?? '',
    emergency_fund: profile?.emergency_fund ?? '',
    monthly_savings_contribution: profile?.monthly_savings_contribution ?? '',
    monthly_debt_payments: profile?.monthly_debt_payments ?? '',
    risk_tolerance: profile?.risk_tolerance ?? '',
    financial_goal: profile?.financial_goal ?? '',
    investment_horizon_years: profile?.investment_horizon_years ?? '',
  })

  function update(event) {
    setFields({ ...fields, [event.target.name]: event.target.value })
  }

  function submit(event) {
    event.preventDefault()
    onSave({
      monthly_expenses: fields.monthly_expenses,
      savings: fields.savings,
      existing_debt: fields.existing_debt,
      emergency_fund: fields.emergency_fund,
      monthly_savings_contribution: fields.monthly_savings_contribution === '' ? null : fields.monthly_savings_contribution,
      monthly_debt_payments: fields.monthly_debt_payments === '' ? null : fields.monthly_debt_payments,
      risk_tolerance: fields.risk_tolerance,
      financial_goal: fields.financial_goal.trim() || null,
      investment_horizon_years: fields.investment_horizon_years === '' ? null : Number(fields.investment_horizon_years),
    })
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Financial profile</h2>
        <p className="mt-1 text-sm text-slate-600">Use the same currency for every amount. The monthly flow fields help calculate the analysis below.</p>
      </div>
      <fieldset disabled={saving || disabled} className="grid gap-5 sm:grid-cols-2">
        <label className={labelClass}>
          Monthly expenses (including debt payments)
          <input className={inputClass} name="monthly_expenses" type="number" min="0" step="0.01" value={fields.monthly_expenses} onChange={update} required />
        </label>
        <label className={labelClass}>
          Savings balance
          <input className={inputClass} name="savings" type="number" min="0" step="0.01" value={fields.savings} onChange={update} required />
        </label>
        <label className={labelClass}>
          Outstanding debt balance
          <input className={inputClass} name="existing_debt" type="number" min="0" step="0.01" value={fields.existing_debt} onChange={update} required />
        </label>
        <label className={labelClass}>
          Emergency fund
          <input className={inputClass} name="emergency_fund" type="number" min="0" step="0.01" value={fields.emergency_fund} onChange={update} required />
        </label>
        <label className={labelClass}>
          Monthly savings contribution (optional)
          <input className={inputClass} name="monthly_savings_contribution" type="number" min="0" step="0.01" value={fields.monthly_savings_contribution} onChange={update} />
          <span className="mt-1 block text-xs font-normal text-slate-500">Amount actually saved each month, separate from your savings balance.</span>
        </label>
        <label className={labelClass}>
          Monthly debt payments (optional)
          <input className={inputClass} name="monthly_debt_payments" type="number" min="0" step="0.01" value={fields.monthly_debt_payments} onChange={update} />
          <span className="mt-1 block text-xs font-normal text-slate-500">Total paid toward debt each month; include it in monthly expenses above. It cannot exceed total expenses.</span>
        </label>
        <label className={labelClass}>
          Risk tolerance
          <select className={inputClass} name="risk_tolerance" value={fields.risk_tolerance} onChange={update} required>
            <option value="">Choose one</option>
            <option value="conservative">Conservative</option>
            <option value="moderate">Moderate</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </label>
        <label className={labelClass}>
          Investment horizon in years (optional)
          <input className={inputClass} name="investment_horizon_years" type="number" min="0" max="80" step="1" value={fields.investment_horizon_years} onChange={update} />
        </label>
      </fieldset>
      <button type="submit" disabled={saving || disabled} className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
        {saving ? 'Saving…' : profile ? 'Update profile' : 'Save profile'}
      </button>
    </form>
  )
}

export default FinancialProfileForm
