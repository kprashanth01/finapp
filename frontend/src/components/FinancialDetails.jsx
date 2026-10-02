import { useEffect, useState } from 'react'
import { explainApiError, getFinancialDetails, saveFinancialDetails } from '../services/api.js'
import { formatAmount } from '../utils/format.js'

const input = 'mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm'
const label = 'block text-sm font-medium text-slate-700'
const empty = {
  recurring_expenses: { name: '', monthly_amount: '', category: 'essential_fixed' },
  loans: { name: '', loan_type: '', remaining_balance: '', monthly_payment: '',
    annual_interest_rate_percent: '', payment_day: '', rate_change_date: '', new_annual_interest_rate_percent: '' },
  planned_expenses: { name: '', estimated_amount: '', amount_reserved: '', due_date: '', is_essential: false },
}

function optional(value) { return value === '' || value == null ? null : value }
function sumMoney(rows, field) {
  return rows.reduce((cents, row) => cents + Math.round(Number(row[field] || 0) * 100), 0) / 100
}

export function detailsPayload(draft) {
  return {
    income_pattern: optional(draft.income_pattern),
    guaranteed_monthly_income: optional(draft.guaranteed_monthly_income),
    recurring_expenses: draft.recurring_expenses.map(({ id, name, monthly_amount, category }) => ({
      ...(id ? { id } : {}), name: name.trim(), monthly_amount, category,
    })),
    loans: draft.loans.map(({ id, name, loan_type, remaining_balance, monthly_payment,
      annual_interest_rate_percent, payment_day, rate_change_date, new_annual_interest_rate_percent }) => ({
      ...(id ? { id } : {}), name: name.trim(), loan_type: optional(loan_type), remaining_balance: optional(remaining_balance),
      monthly_payment: optional(monthly_payment), annual_interest_rate_percent: optional(annual_interest_rate_percent),
      payment_day: optional(payment_day) == null ? null : Number(payment_day),
      rate_change_date: optional(rate_change_date),
      new_annual_interest_rate_percent: optional(new_annual_interest_rate_percent),
    })),
    planned_expenses: draft.planned_expenses.map(({ id, name, estimated_amount, amount_reserved,
      due_date, is_essential }) => ({ ...(id ? { id } : {}), name: name.trim(), estimated_amount,
      amount_reserved: optional(amount_reserved), due_date, is_essential })),
  }
}

function TextField({ title, value, onChange, type = 'text', required = false, min, max, step, hint }) {
  return <label className={label}>{title}
    <input className={input} type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)}
      required={required} min={min} max={max} step={step} />
    {hint && <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span>}
  </label>
}

export default function FinancialDetails({ userId, user, profile, onOpenMonths }) {
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    setDraft(null)
    setLoading(true)
    getFinancialDetails(userId).then((value) => { if (active) { setDraft(value); setError('') } })
      .catch((failure) => { if (active) setError(explainApiError(failure)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userId])

  function change(name, value) { setDraft((current) => ({ ...current, [name]: value })); setNotice('') }
  function changeRow(section, index, name, value) {
    setDraft((current) => ({ ...current, [section]: current[section].map((row, at) =>
      at === index ? { ...row, [name]: value } : row) }))
    setNotice('')
  }
  function add(section) {
    setDraft((current) => ({ ...current, [section]: [...current[section], { ...empty[section] }] }))
    setNotice('')
  }
  function remove(section, index) {
    setDraft((current) => ({ ...current, [section]: current[section].filter((_, at) => at !== index) }))
    setNotice('')
  }

  async function save(event) {
    event.preventDefault()
    if (!draft || saving) return
    setSaving(true); setError(''); setNotice('')
    try {
      const saved = await saveFinancialDetails(userId, detailsPayload(draft))
      setDraft(saved)
      setNotice('Details saved. Your current plan continues to use the totals in Profile.')
    } catch (failure) { setError(explainApiError(failure)) }
    finally { setSaving(false) }
  }

  return <details className="mt-8 rounded-xl border border-slate-200 p-5">
    <summary className="cursor-pointer text-lg font-semibold">Optional financial details</summary>
    <p className="mt-3 text-sm text-slate-600">Add context when you have it. These records describe your Profile totals; they are not added to your monthly expenses or debt again. Your current plan still uses the Profile totals.</p>
    {loading && <p role="status" className="mt-4 text-sm">Loading details…</p>}
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {!loading && !draft && <button type="button" onClick={() => { setLoading(true); getFinancialDetails(userId)
      .then((value) => { setDraft(value); setError('') }).catch((failure) => setError(explainApiError(failure)))
      .finally(() => setLoading(false)) }} className="mt-3 text-sm underline">Retry details</button>}
    {draft && <form onSubmit={save} className="mt-5 space-y-8">
      <fieldset disabled={saving} className="space-y-8">
        <section className="space-y-3"><h3 className="font-semibold">Income context</h3>
          <p className="text-sm text-slate-600">Your current gross monthly estimate is {formatAmount(user.monthly_income)}. Enter a guaranteed amount only if part of that estimate is truly assured. Recorded income belongs in Months.</p>
          <div className="grid gap-4 sm:grid-cols-2"><label className={label}>Income pattern
            <select className={input} value={draft.income_pattern ?? ''} onChange={(event) => change('income_pattern', event.target.value)}>
              <option value="">Not specified</option><option value="stable">Mostly stable</option>
              <option value="variable">Variable</option><option value="mixed">Stable and variable sources</option>
            </select></label>
            <TextField title="Guaranteed gross monthly income (optional)" type="number" min="0" step="0.01"
              value={draft.guaranteed_monthly_income} onChange={(value) => change('guaranteed_monthly_income', value)} />
          </div><button type="button" onClick={onOpenMonths} className="text-sm font-medium underline">Record income history in Months</button>
        </section>

        <section className="space-y-3"><h3 className="font-semibold">Recurring monthly expenses</h3>
          <p className="text-sm text-slate-600">Break down part of your {formatAmount(profile.monthly_expenses)} monthly total. Leave loan payments out; they are already included in that total.</p>
          {draft.recurring_expenses.map((row, index) => <div key={row.id ?? `new-${index}`} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-4">
            <TextField title="Expense name" value={row.name} required onChange={(value) => changeRow('recurring_expenses', index, 'name', value)} />
            <TextField title="Monthly amount" type="number" min="0.01" step="0.01" value={row.monthly_amount} required onChange={(value) => changeRow('recurring_expenses', index, 'monthly_amount', value)} />
            <label className={label}>Category<select className={input} value={row.category} onChange={(event) => changeRow('recurring_expenses', index, 'category', event.target.value)}>
              <option value="essential_fixed">Essential fixed</option><option value="essential_variable">Essential variable</option><option value="discretionary">Discretionary</option>
            </select></label>
            <button type="button" onClick={() => remove('recurring_expenses', index)} className="self-end text-sm underline">Remove expense</button>
          </div>)}
          <button type="button" onClick={() => add('recurring_expenses')} className="text-sm font-medium underline">Add recurring expense</button>
          <p className="text-xs text-slate-500">Described monthly expenses: {formatAmount(sumMoney(draft.recurring_expenses, 'monthly_amount'))}. Unlisted spending can remain in the Profile total.</p>
        </section>

        <section className="space-y-3"><h3 className="font-semibold">Loans and required payments</h3>
          <p className="text-sm text-slate-600">Describe your {formatAmount(profile.existing_debt)} debt balance and {profile.monthly_debt_payments == null ? 'unknown' : formatAmount(profile.monthly_debt_payments)} monthly debt payment. Update Profile totals first if these amounts are too low. Leave an individual balance or payment blank when unknown; zero means none.</p>
          {draft.loans.map((row, index) => <div key={row.id ?? `new-${index}`} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-3">
            <TextField title="Loan name" value={row.name} required onChange={(value) => changeRow('loans', index, 'name', value)} />
            <TextField title="Loan type (optional)" value={row.loan_type} onChange={(value) => changeRow('loans', index, 'loan_type', value)} />
            <TextField title="Remaining balance (optional)" type="number" min="0" step="0.01" value={row.remaining_balance} onChange={(value) => changeRow('loans', index, 'remaining_balance', value)} />
            <TextField title="Required monthly payment (optional)" type="number" min="0" step="0.01" value={row.monthly_payment} onChange={(value) => changeRow('loans', index, 'monthly_payment', value)} />
            <TextField title="Annual interest rate % (optional)" type="number" min="0" max="999.99" step="0.01" value={row.annual_interest_rate_percent} onChange={(value) => changeRow('loans', index, 'annual_interest_rate_percent', value)} />
            <TextField title="Payment day of month (optional)" type="number" min="1" max="31" step="1" value={row.payment_day} onChange={(value) => changeRow('loans', index, 'payment_day', value)} />
            <TextField title="Rate changes on (optional)" type="date" value={row.rate_change_date} onChange={(value) => changeRow('loans', index, 'rate_change_date', value)} />
            <TextField title="New annual rate % (optional)" type="number" min="0" max="999.99" step="0.01" value={row.new_annual_interest_rate_percent} onChange={(value) => changeRow('loans', index, 'new_annual_interest_rate_percent', value)} />
            <button type="button" onClick={() => remove('loans', index)} className="self-end text-sm underline">Remove loan</button>
          </div>)}
          <button type="button" onClick={() => add('loans')} className="text-sm font-medium underline">Add loan</button>
          <p className="text-xs text-slate-500">Recorded loan balances: {formatAmount(sumMoney(draft.loans, 'remaining_balance'))}{draft.loans.some((row) => row.remaining_balance === '' || row.remaining_balance == null) ? ' (some balances not supplied)' : ''}. Recorded monthly loan payments: {formatAmount(sumMoney(draft.loans, 'monthly_payment'))}{draft.loans.some((row) => row.monthly_payment === '' || row.monthly_payment == null) ? ' (some payments not supplied)' : ''}.</p>
        </section>

        <section className="space-y-3"><h3 className="font-semibold">Upcoming one-time expenses</h3>
          <p className="text-sm text-slate-600">Record a dated cost without adding it to recurring monthly expenses. If it is already tracked as a Goal, keep it there instead of entering it twice. Amount reserved is money already set aside; leave it blank when unknown, and use zero when none is reserved.</p>
          {draft.planned_expenses.map((row, index) => <div key={row.id ?? `new-${index}`} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-3">
            <TextField title="Expense name" value={row.name} required onChange={(value) => changeRow('planned_expenses', index, 'name', value)} />
            <TextField title="Estimated cost" type="number" min="0.01" step="0.01" value={row.estimated_amount} required onChange={(value) => changeRow('planned_expenses', index, 'estimated_amount', value)} />
            <TextField title="Amount reserved (optional)" type="number" min="0" step="0.01" value={row.amount_reserved} onChange={(value) => changeRow('planned_expenses', index, 'amount_reserved', value)} />
            <TextField title="Due date" type="date" value={row.due_date} required onChange={(value) => changeRow('planned_expenses', index, 'due_date', value)} />
            <label className={label}>Importance<select className={input} value={row.is_essential ? 'essential' : 'flexible'} onChange={(event) => changeRow('planned_expenses', index, 'is_essential', event.target.value === 'essential')}>
              <option value="flexible">Flexible plan</option><option value="essential">Essential obligation</option>
            </select></label>
            <button type="button" onClick={() => remove('planned_expenses', index)} className="self-end text-sm underline">Remove upcoming expense</button>
          </div>)}
          <button type="button" onClick={() => add('planned_expenses')} className="text-sm font-medium underline">Add upcoming expense</button>
          <p className="text-xs text-slate-500">Estimated one-time costs: {formatAmount(sumMoney(draft.planned_expenses, 'estimated_amount'))}. Recorded reserved amounts: {formatAmount(sumMoney(draft.planned_expenses, 'amount_reserved'))}{draft.planned_expenses.some((row) => row.amount_reserved === '' || row.amount_reserved == null) ? ' (some amounts not supplied)' : ''}.</p>
        </section>
      </fieldset>
      <button type="submit" disabled={saving} className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? 'Saving…' : 'Save details'}</button>
      {notice && <p role="status" className="text-sm text-emerald-800">{notice}</p>}
    </form>}
  </details>
}
