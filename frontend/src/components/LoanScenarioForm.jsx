import { useEffect, useState } from 'react'

const field = 'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm'
const label = 'block text-sm font-medium text-slate-700'

export const blankLoan = {
  name: '', loan_type: 'personal', lender_name: '', amount: '', annual_interest_rate_percent: '',
  tenure_months: '24', quoted_monthly_payment: '', credit_score: '', credit_history_months: '',
  credit_utilization_percent: '', income_documents_ready: '', missed_payments_last_12_months: '', criteria: [],
}

const kinds = [
  ['minimum_history_months', 'Minimum recorded income months'],
  ['minimum_monthly_income', 'Minimum monthly income'],
  ['maximum_debt_service_percent', 'Maximum debt service %'],
  ['minimum_reserve_months', 'Minimum reserve months'],
  ['minimum_credit_score', 'Minimum credit score'],
  ['maximum_credit_utilization_percent', 'Maximum credit utilization %'],
  ['income_documents_required', 'Income documents required (1=yes)'],
  ['maximum_missed_payments', 'Maximum missed payments'],
]

function optional(value) { return value === '' || value == null ? null : value }

export function loanScenarioPayload(draft) {
  return {
    name: draft.name.trim(), loan_type: draft.loan_type.trim(), lender_name: optional((draft.lender_name ?? '').trim()),
    amount: draft.amount, annual_interest_rate_percent: optional(draft.annual_interest_rate_percent),
    tenure_months: Number(draft.tenure_months), quoted_monthly_payment: optional(draft.quoted_monthly_payment),
    credit_score: optional(draft.credit_score) == null ? null : Number(draft.credit_score),
    credit_history_months: optional(draft.credit_history_months) == null ? null : Number(draft.credit_history_months),
    credit_utilization_percent: optional(draft.credit_utilization_percent),
    income_documents_ready: optional(draft.income_documents_ready) == null ? null : draft.income_documents_ready === 'yes',
    missed_payments_last_12_months: optional(draft.missed_payments_last_12_months) == null ? null : Number(draft.missed_payments_last_12_months),
    criteria: draft.criteria.map((item) => ({ kind: item.kind, value: item.value,
      source_name: optional(item.source_name?.trim()), source_url: optional(item.source_url?.trim()) })),
  }
}

function Input({ title, value, onChange, type = 'text', required = false, min, max, step, hint }) {
  return <label className={label}>{title}<input className={field} value={value ?? ''} onChange={(e) => onChange(e.target.value)}
    type={type} required={required} min={min} max={max} step={step} />{hint && <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span>}</label>
}

export default function LoanScenarioForm({ scenario, onSave, onDelete, saving, error, onOpenProfile, onOpenMonths }) {
  const [draft, setDraft] = useState(scenario ? { ...blankLoan, ...scenario,
    income_documents_ready: scenario.income_documents_ready == null ? '' : scenario.income_documents_ready ? 'yes' : 'no' } : blankLoan)
  useEffect(() => {
    setDraft(scenario ? { ...blankLoan, ...scenario,
      income_documents_ready: scenario.income_documents_ready == null ? '' : scenario.income_documents_ready ? 'yes' : 'no' } : { ...blankLoan })
  }, [scenario])
  function change(key, value) { setDraft((old) => ({ ...old, [key]: value })) }
  function changeCriterion(index, key, value) {
    setDraft((old) => ({ ...old, criteria: old.criteria.map((item, at) => at === index ? { ...item, [key]: value } : item) }))
  }
  function submit(event) { event.preventDefault(); onSave(loanScenarioPayload(draft)) }
  return <form onSubmit={submit} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
    <div><h3 className="text-xl font-semibold">Loan details</h3>
      <p className="mt-1 text-sm text-slate-600">Describe a loan you are considering. Saving it does not apply to a lender or add it to your existing debt.</p></div>
    <fieldset disabled={saving} className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Input title="Scenario name" value={draft.name} onChange={(v) => change('name', v)} required />
        <label className={label}>Loan type<select className={field} value={draft.loan_type} onChange={(e) => change('loan_type', e.target.value)}>
          {['personal', 'vehicle', 'home', 'education', 'business', 'other'].map((type) => <option key={type} value={type}>{type[0].toUpperCase() + type.slice(1)}</option>)}</select></label>
        <Input title="Lender or provider (optional)" value={draft.lender_name} onChange={(v) => change('lender_name', v)}
          hint="A name does not load or verify that lender’s rules." />
        <Input title="Desired loan amount" value={draft.amount} onChange={(v) => change('amount', v)} type="number" min="0.01" step="0.01" required />
        <Input title="Annual interest rate % (if known)" value={draft.annual_interest_rate_percent} onChange={(v) => change('annual_interest_rate_percent', v)} type="number" min="0" max="100" step="0.01" />
        <Input title="Tenure in months" value={draft.tenure_months} onChange={(v) => change('tenure_months', v)} type="number" min="1" max="480" step="1" required />
        <Input title="Monthly payment quote (optional)" value={draft.quoted_monthly_payment} onChange={(v) => change('quoted_monthly_payment', v)} type="number" min="0.01" step="0.01"
          hint="If entered, the quote is used for capacity. Confirm what fees it includes." />
      </div>
      <div className="rounded-xl bg-slate-50 p-4"><h4 className="font-semibold">Use your saved finances</h4>
        <p className="mt-1 text-sm text-slate-600">The assessment reads your Profile totals, existing loan payments, goals and recorded Months each time. Existing EMI is already inside total spending.</p>
        <div className="mt-2 flex gap-4 text-sm"><button type="button" className="font-medium text-teal-800 underline" onClick={onOpenProfile}>Update Profile and debt</button>
          <button type="button" className="font-medium text-teal-800 underline" onClick={onOpenMonths}>Record income months</button></div>
      </div>
      <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-semibold">Credit, repayments and documents (optional)</summary>
        <p className="mt-2 text-sm text-slate-600">Only enter information you know. Blank fields stay unknown; the app never creates a credit score.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Input title="Credit score you obtained" value={draft.credit_score} onChange={(v) => change('credit_score', v)} type="number" min="0" max="1000" step="1" />
          <Input title="Credit history in months" value={draft.credit_history_months} onChange={(v) => change('credit_history_months', v)} type="number" min="0" max="1200" step="1" />
          <Input title="Credit utilization %" value={draft.credit_utilization_percent} onChange={(v) => change('credit_utilization_percent', v)} type="number" min="0" max="100" step="0.01" />
          <Input title="Missed payments in last 12 months" value={draft.missed_payments_last_12_months} onChange={(v) => change('missed_payments_last_12_months', v)} type="number" min="0" max="12" step="1" />
          <label className={label}>Requested income documents ready?<select className={field} value={draft.income_documents_ready} onChange={(e) => change('income_documents_ready', e.target.value)}>
            <option value="">Not provided</option><option value="yes">Yes</option><option value="no">No</option></select></label>
        </div>
      </details>
      <details className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer font-semibold">Criteria you obtained from a lender (optional)</summary>
        <p className="mt-2 text-sm text-slate-600">Enter only a criterion you have actually received. Each remains labeled user-entered and unverified; no lender policy is filled in automatically.</p>
        <div className="mt-4 space-y-4">{draft.criteria.map((item, index) => <div key={`${item.kind}-${index}`} className="grid gap-3 rounded-lg bg-slate-50 p-4 sm:grid-cols-2">
          <label className={label}>Criterion<select className={field} value={item.kind} onChange={(e) => changeCriterion(index, 'kind', e.target.value)}>
            {kinds.map(([kind, title]) => <option key={kind} value={kind}>{title}</option>)}</select></label>
          <Input title="Required value" value={item.value} onChange={(v) => changeCriterion(index, 'value', v)} type="number" min="0" step="0.01" required />
          <Input title="Source name or document" value={item.source_name} onChange={(v) => changeCriterion(index, 'source_name', v)} />
          <Input title="Source URL (optional)" value={item.source_url} onChange={(v) => changeCriterion(index, 'source_url', v)} type="url" />
          <button type="button" className="justify-self-start text-sm text-rose-800 underline" onClick={() => change('criteria', draft.criteria.filter((_, at) => at !== index))}>Remove criterion</button>
        </div>)}
        <button type="button" className="text-sm font-semibold text-teal-800 underline" onClick={() => change('criteria', [...draft.criteria,
          { kind: 'minimum_history_months', value: '', source_name: '', source_url: '' }])}>Add a criterion</button></div>
      </details>
    </fieldset>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900">{error}</p>}
    <div className="flex flex-wrap gap-3"><button type="submit" disabled={saving} className="rounded-lg bg-teal-800 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : scenario ? 'Save and refresh readiness' : 'Save loan and assess'}</button>
      {scenario && <button type="button" disabled={saving} className="text-sm text-rose-800 underline" onClick={onDelete}>Delete this scenario</button>}</div>
  </form>
}
