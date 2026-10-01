import { useEffect, useState } from 'react'
import { MethodCard, evidenceValue } from './MonthlyDemo.jsx'
import { askFinancialMonth, deleteFinancialMonth, explainApiError, getFinancialMonthAdvice, getFinancialMonths, saveFinancialMonth } from '../services/api.js'
import MonthlyPlanningSummary from './MonthlyPlanningSummary.jsx'

const names = { budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund', risk: 'Risk', investment: 'Investment readiness' }
const todayMonth = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}
const nextMonth = (period) => {
  if (!period) return todayMonth()
  const [year, month] = period.slice(0, 7).split('-').map(Number)
  const next = month === 12 ? `${year + 1}-01` : `${year}-${String(month + 1).padStart(2, '0')}`
  return next > todayMonth() ? todayMonth() : next
}
const amount = (value) => Number(value ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const monthLabel = (period) => new Date(`${period}T12:00:00`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

function startingMonth(user, profile, period = todayMonth()) {
  const emi = profile?.monthly_debt_payments ?? '0'
  return {
    period, monthly_income: user?.monthly_income ?? '',
    fixed_expenses: '0', other_expenses: String(Math.max(0, Number(profile?.monthly_expenses ?? 0) - Number(emi))),
    scheduled_emi: emi, paid_emi: emi, paid_emi_edited: false,
    savings: profile?.savings ?? '', emergency_fund: profile?.emergency_fund ?? '',
    outstanding_debt: profile?.existing_debt ?? '', unfunded_expenses: '0',
    risk_tolerance: profile?.risk_tolerance ?? 'moderate',
    investment_horizon_years: profile?.investment_horizon_years ?? 0,
  }
}

export function monthTotals(draft) {
  const cents = (value) => Math.round(Number(value || 0) * 100)
  const expenses = cents(draft.fixed_expenses) + cents(draft.other_expenses) + cents(draft.scheduled_emi)
  return { monthly_expenses: (expenses / 100).toFixed(2),
    net_cash_flow: ((cents(draft.monthly_income) - expenses) / 100).toFixed(2) }
}

export function updateMonthDraft(draft, name, value) {
  const next = { ...draft, [name]: value }
  if (name === 'paid_emi') next.paid_emi_edited = true
  if (name === 'scheduled_emi' && !draft.paid_emi_edited) next.paid_emi = value
  return next
}

const fieldHelp = {
  fixed_expenses: 'Bills you need to pay even if you spend less elsewhere, such as rent and utilities. Do not include the loan payment.',
  other_expenses: 'All other spending you expect this month. This and essential bills and the loan payment add up to total planned spending.',
  scheduled_emi: 'The loan payment due this month. It is included in total planned spending.',
  paid_emi: 'What you actually paid toward that scheduled loan payment. Change the copied amount if you paid less.',
  outstanding_debt: 'The remaining balance of all loans you still owe at the end of this month. This is not the monthly payment.',
  savings: 'Cash you can access, including the emergency reserve entered below.',
  emergency_fund: 'The part of your accessible savings you have set aside for surprises.',
  unfunded_expenses: 'Bills you actually could not pay this month. A planned shortfall does not automatically mean a bill went unpaid.',
}

function MoneyInput({ label, name, value, onChange, hint }) {
  return <label><span>{label}{fieldHelp[name] && <span className="account-field-help" title={fieldHelp[name]} aria-label={`What does ${label} mean? ${fieldHelp[name]}`} tabIndex={0}>?</span>}</span><input name={name} type="number" inputMode="decimal" min="0" step="0.01" required
    value={value} onChange={onChange} />{hint && <small>{hint}</small>}</label>
}

export function formMonth(row) {
  const other = Math.max(0, Number(row.monthly_expenses) - Number(row.fixed_expenses) - Number(row.scheduled_emi))
  const { monthly_income, fixed_expenses, scheduled_emi, paid_emi, savings, emergency_fund,
    outstanding_debt, unfunded_expenses, risk_tolerance, investment_horizon_years } = row
  return { period: row.period.slice(0, 7), monthly_income, fixed_expenses,
    other_expenses: other.toFixed(2), scheduled_emi, paid_emi, savings, emergency_fund,
    outstanding_debt, unfunded_expenses, risk_tolerance, investment_horizon_years,
    paid_emi_edited: Number(paid_emi) !== Number(scheduled_emi) }
}

export function AccountAdvice({ advice }) {
  const { context, methods, focused_review: focused, month } = advice
  const missed = methods.trained_rl.reward_audit.missed_critical_agents
  const change = context.recent_income_change_ratio == null ? null : Number(context.recent_income_change_ratio) * 100
  const cashFlow = Number(context.net_cash_flow)
  return <section className="account-month-result" aria-labelledby="account-month-result-heading">
    <h4 id="account-month-result-heading">Advice for {monthLabel(advice.month.period)}</h4>
    <div className="account-month-summary"><h5>What your figures show</h5>
      <p>Income: {amount(month.monthly_income)} · Planned spending: {amount(month.monthly_expenses)} (including {amount(month.scheduled_emi)} due on debt).</p>
      <p>{cashFlow < 0 ? `Planned spending is ${amount(-cashFlow)} above income. There is no monthly surplus for extra debt payments or new investments.` : `After planned spending, ${amount(cashFlow)} remains from this month's income.`}</p>
      {change != null && <p>Income changed {change.toFixed(1)}% from the previous recorded month.</p>}
      <small>These are planned amounts. They do not show that a bill went unpaid unless you entered one as unfunded.</small>
    </div>
    <p className="account-month-caveat">The trained DQN chooses which checks to run. The financial findings in both columns come from the same project rules. A missing check means the DQN result is incomplete, even if its selection score was higher.</p>
    {missed.length > 0 && <p role="status" className="account-month-caveat">The DQN did not run the important {missed.map((id) => names[id] ?? id).join(', ')} check. Look at the rule-based column or request that check above.</p>}
    <div className="monthly-demo-methods">
      <MethodCard title="Trained monthly DQN" result={methods.trained_rl} month={month} context={context} />
      <MethodCard title="Rule-based baseline" result={methods.rule_based} month={month} context={context} />
    </div>
    {focused && <section className="account-month-focus"><h5>Your requested review: {names[focused.agent_id]}</h5>
      <p>{focused.selected_by_dqn ? 'The DQN also selected this check.' : 'This check ran because you requested it; the DQN did not select it.'}</p>
      {focused.interpretation && <div className="account-month-interpretation">
        <strong>What this means for your investment decision</strong>
        <p>{focused.interpretation.headline}</p>
        <ul>{focused.interpretation.steps.map((step) => <li key={step}>{step}</li>)}</ul>
      </div>}
      {focused.result.findings.map((finding) => <article key={finding.code}>
        <strong>{finding.title}</strong><p>{finding.reason}</p>
        {finding.evidence?.length > 0 && <details><summary>See the figures used</summary><ul>{finding.evidence.filter((item) => evidenceValue(item) !== null).map((item, index) =>
          <li key={`${item.label}-${index}`}>{item.label}: {evidenceValue(item)}</li>)}</ul></details>}
      </article>)}
    </section>}
    <details className="monthly-demo-limits"><summary>How this was calculated and its limits</summary>
      <p>Model {advice.model_version}; verified artifact {advice.model_artifact_sha256.slice(0, 12)}…</p>
      <p>Income variability from entered months: {(Number(context.income_volatility) * 100).toFixed(1)}%. Usual-income reference: {amount(context.usual_income_reference)} profile currency.</p>
      <ul>{advice.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
    </details>
  </section>
}

export default function AccountMonths({ userId, user, profile, mode = 'research', onOpenProfile }) {
  const planning = mode === 'planning'
  const [months, setMonths] = useState([])
  const [draft, setDraft] = useState(() => startingMonth(user, profile))
  const [selected, setSelected] = useState('')
  const [focus, setFocus] = useState('all')
  const [advice, setAdvice] = useState(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    getFinancialMonths(userId).then((rows) => { if (active) {
      setMonths(rows); setSelected(rows.at(-1)?.period ?? '')
    } }).catch((requestError) => { if (active) setError(explainApiError(requestError)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userId])

  const edit = (event) => setDraft((current) => updateMonthDraft(current, event.target.name, event.target.value))
  const totals = monthTotals(draft)

  async function save(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try {
      const { other_expenses, paid_emi_edited, ...values } = draft
      const saved = await saveFinancialMonth(userId, { ...values, monthly_expenses: totals.monthly_expenses, period: `${draft.period}-01` })
      const rows = await getFinancialMonths(userId)
      setMonths(rows); setSelected(saved.period); setAdvice(null); setAnswer(null)
      setMessage(planning ? `${monthLabel(saved.period)} saved. The planning check above now uses this month.`
        : `${monthLabel(saved.period)} saved. Select this month and press Get advice when ready.`)
    } catch (requestError) { setError(explainApiError(requestError)) }
    finally { setBusy(false) }
  }

  async function remove(period) {
    if (busy || !window.confirm(`Delete your saved figures for ${monthLabel(period)}?`)) return
    setBusy(true); setError(''); setMessage('')
    try {
      await deleteFinancialMonth(userId, period)
      const rows = await getFinancialMonths(userId)
      setMonths(rows); setSelected((current) => current === period ? rows.at(-1)?.period ?? '' : current)
      setAdvice(null); setAnswer(null); setMessage(`${monthLabel(period)} removed.`)
    } catch (requestError) { setError(explainApiError(requestError)) }
    finally { setBusy(false) }
  }

  async function run() {
    if (busy || !selected) return
    setBusy(true); setError(''); setAdvice(null); setAnswer(null)
    try { setAdvice(await getFinancialMonthAdvice(userId, selected, focus)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setBusy(false) }
  }

  async function ask(event) {
    event.preventDefault()
    if (busy || !advice || !question.trim()) return
    setBusy(true); setError(''); setAnswer(null)
    try { setAnswer(await askFinancialMonth(userId, advice.month.period, question.trim(), focus)) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setBusy(false) }
  }

  const additionalFields = <>
    <MoneyInput label="Loan payment actually made" name="paid_emi" value={draft.paid_emi} onChange={edit} />
    <MoneyInput label="Total accessible savings" name="savings" value={draft.savings} onChange={edit} hint="Include the emergency reserve." />
    <MoneyInput label="Emergency reserve" name="emergency_fund" value={draft.emergency_fund} onChange={edit} />
    <MoneyInput label="Loan balance still owed" name="outstanding_debt" value={draft.outstanding_debt} onChange={edit} />
    <MoneyInput label="Expenses you could not fund" name="unfunded_expenses" value={draft.unfunded_expenses} onChange={edit} hint="Enter 0 if none." />
    <label>Risk preference<select name="risk_tolerance" value={draft.risk_tolerance} onChange={edit}>
      <option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option>
    </select></label>
    <label>Investment horizon, years<input name="investment_horizon_years" type="number" min="0" max="80" required value={draft.investment_horizon_years} onChange={edit} /></label>
  </>

  return <section className="account-months" aria-labelledby="account-months-heading">
    <p className="research-small-label">YOUR ENTERED FINANCIAL HISTORY</p>
    <h3 id="account-months-heading">{planning ? 'Plan for changing income' : 'Build your own month-by-month situation'}</h3>
    <p>Enter an ordinary month first, then enter a later month with changed income or expenses. These are your account's records, separate from the current Profile snapshot. You can correct a month at any time.</p>
    {planning && <p>The first form starts with amounts from your current Profile. Check them for the month you chose. Other planned spending starts with all non-debt expenses; move any essential bills you enter out of that amount so they are counted once. Review the copied balances under Additional month details before saving.</p>}
    {planning && !loading && months.length > 0 && <MonthlyPlanningSummary months={months} profile={profile} onOpenProfile={onOpenProfile} />}
    <form onSubmit={save} className="account-month-form">
      <div className="account-month-fields">
        <label>Month<input name="period" type="month" max={todayMonth()} required value={draft.period} onChange={edit} /></label>
        <MoneyInput label="Income received" name="monthly_income" value={draft.monthly_income} onChange={edit} />
        <MoneyInput label="Essential bills (excluding loan)" name="fixed_expenses" value={draft.fixed_expenses} onChange={edit} />
        <MoneyInput label="Other planned spending" name="other_expenses" value={draft.other_expenses} onChange={edit} />
        <MoneyInput label="Loan payment due this month" name="scheduled_emi" value={draft.scheduled_emi} onChange={edit} />
        {!planning && additionalFields}
      </div>
      {planning && <details className="account-month-extra"><summary>Additional month details</summary>
        <p>Confirm balances and the payment actually made if they differ from the values copied from your current Profile.</p>
        <div className="account-month-fields">{additionalFields}</div>
      </details>}
      <div className="account-month-calculated"><span>Total planned spending <small>(calculated from the three spending fields)</small><strong>{amount(totals.monthly_expenses)}</strong></span>
        <span>{Number(totals.net_cash_flow) < 0 ? 'Planned shortfall' : 'Money left after planned spending'} <small>(calculated)</small><strong>{amount(Math.abs(Number(totals.net_cash_flow)))}</strong></span></div>
      <div className="account-month-buttons"><button type="submit" className="primary-action" disabled={busy}>Save this month</button>
        <button type="button" disabled={busy || !months.length || months.at(-1).period.slice(0, 7) >= todayMonth()} onClick={() => {
          setDraft({ ...formMonth(months.at(-1)), period: nextMonth(months.at(-1).period), paid_emi: months.at(-1).scheduled_emi,
            paid_emi_edited: false, unfunded_expenses: '0' })
          setMessage('Copied the previous month. Update income, spending and balances before saving this new month.')
        }}>Start next month</button></div>
    </form>
    {loading ? <p role="status">Loading your recorded months…</p> : months.length ? <>
      <h4>Months you entered</h4>
      <ul className="account-month-list">{months.map((row) => <li key={row.period}>
        <span><strong>{monthLabel(row.period)}</strong> · Income {amount(row.monthly_income)} · Expenses {amount(row.monthly_expenses)}</span>
        <span><button type="button" disabled={busy} onClick={() => { setDraft(formMonth(row)); setSelected(row.period); setAdvice(null); setAnswer(null) }}>Edit</button>
          <button type="button" disabled={busy} onClick={() => remove(row.period)}>Delete</button></span>
      </li>)}</ul>
      {!planning && <div className="account-month-run"><label>Month to review<select value={selected} onChange={(event) => { setSelected(event.target.value); setAdvice(null); setAnswer(null) }}>
        {months.map((row) => <option key={row.period} value={row.period}>{monthLabel(row.period)}</option>)}
      </select></label>
      <label>What do you want advice on?<select value={focus} onChange={(event) => { setFocus(event.target.value); setAdvice(null); setAnswer(null) }}>
        <option value="all">Overall priorities</option>{Object.entries(names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      <button type="button" className="primary-action" disabled={busy} onClick={run}>{busy ? 'Working…' : 'Get advice for this month'}</button></div>}
    </> : <p>No months saved yet. Start with a normal month so a later income change can be measured.</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {!planning && advice && <><AccountAdvice advice={advice} />
      <form className="account-month-question" onSubmit={ask}><h4>Ask about this month</h4>
        <p>Ask in your own words. Answers use this month's entered amounts and recorded checks; the local language model helps word questions it can verify. Your question and answer are not saved.</p>
        <div><input aria-label="Your question about this month" value={question} maxLength={500} required minLength={3}
          onChange={(event) => setQuestion(event.target.value)} placeholder="For example, what should I review after my income dropped?" />
          <button type="submit" className="primary-action" disabled={busy || !question.trim()}>{busy ? 'Answering…' : 'Ask'}</button></div>
        {answer?.answer && <section aria-label="Answer about this month"><strong>{answer.source === 'recorded_evidence' ? 'Answer from your recorded figures' : 'Answer from local model'}</strong><p>{answer.answer}</p>
          <details><summary>Evidence used</summary><ul>{answer.evidence.map((item) => <li key={item.id}><strong>{item.label}:</strong> {item.detail}</li>)}</ul></details></section>}
        {answer?.source === 'unavailable' && <p role="status">{answer.reason} The recorded specialist findings above are still available.</p>}
      </form></>}
  </section>
}
