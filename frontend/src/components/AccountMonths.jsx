import { useEffect, useState } from 'react'
import { MethodCard } from './MonthlyDemo.jsx'
import { askFinancialMonth, deleteFinancialMonth, explainApiError, getFinancialMonthAdvice, getFinancialMonths, saveFinancialMonth } from '../services/api.js'

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
    monthly_expenses: profile?.monthly_expenses ?? '', fixed_expenses: '0',
    scheduled_emi: emi, paid_emi: emi,
    savings: profile?.savings ?? '', emergency_fund: profile?.emergency_fund ?? '',
    outstanding_debt: profile?.existing_debt ?? '', unfunded_expenses: '0',
    risk_tolerance: profile?.risk_tolerance ?? 'moderate',
    investment_horizon_years: profile?.investment_horizon_years ?? 0,
  }
}

function MoneyInput({ label, name, value, onChange, hint }) {
  return <label>{label}<input name={name} type="number" inputMode="decimal" min="0" step="0.01" required
    value={value} onChange={onChange} />{hint && <small>{hint}</small>}</label>
}

export function AccountAdvice({ advice }) {
  const { context, methods, focused_review: focused } = advice
  const missed = methods.trained_rl.reward_audit.missed_critical_agents
  const change = context.recent_income_change_ratio == null ? null : Number(context.recent_income_change_ratio) * 100
  return <section className="account-month-result" aria-labelledby="account-month-result-heading">
    <h4 id="account-month-result-heading">Advice for {monthLabel(advice.month.period)}</h4>
    <p>Based on the amounts you entered for this month and {context.history_months_used - 1} earlier recorded {context.history_months_used === 2 ? 'month' : 'months'}.
      {change == null ? ' No adjacent prior month was available for an income-change calculation.' : ` Income changed ${change.toFixed(1)}% from the prior month.`}
      {' '}Scheduled cash flow: {amount(context.net_cash_flow)} profile currency.</p>
    <p className="account-month-caveat">The trained DQN chooses specialists. Their findings use the recorded figures and project rules. A partial selection is not a complete coordinated plan.</p>
    {missed.length > 0 && <p role="status" className="account-month-caveat">The DQN missed a critical {missed.map((id) => names[id] ?? id).join(', ')} check under this project's proxy. Review the rule baseline and request that specialist above before acting on the partial DQN findings.</p>}
    <div className="monthly-demo-methods">
      <MethodCard title="Trained monthly DQN" result={methods.trained_rl} />
      <MethodCard title="Rule-based baseline" result={methods.rule_based} />
    </div>
    {focused && <section className="account-month-focus"><h5>Your requested review: {names[focused.agent_id]}</h5>
      <p>{focused.selected_by_dqn ? 'The DQN also selected this specialist.' : 'This specialist ran on your request; the DQN did not select it. Its findings do not change the DQN selection or score.'}</p>
      {focused.result.findings.map((finding) => <article key={finding.code}>
        <strong>{finding.title}</strong><p>{finding.reason}</p>
        {finding.evidence?.length > 0 && <details><summary>See the figures used</summary><ul>{finding.evidence.map((item, index) =>
          <li key={`${item.label}-${index}`}>{item.label}: {item.value ?? 'Unavailable'} {item.unit}</li>)}</ul></details>}
      </article>)}
    </section>}
    <details className="monthly-demo-limits"><summary>How this was calculated and its limits</summary>
      <p>Model {advice.model_version}; verified artifact {advice.model_artifact_sha256.slice(0, 12)}…</p>
      <p>Income variability from entered months: {(Number(context.income_volatility) * 100).toFixed(1)}%. Usual-income reference: {amount(context.usual_income_reference)} profile currency.</p>
      <ul>{advice.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
    </details>
  </section>
}

export default function AccountMonths({ userId, user, profile }) {
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

  const edit = (event) => setDraft((current) => ({ ...current, [event.target.name]: event.target.value }))
  const formMonth = (row) => ({ ...row, period: row.period.slice(0, 7) })

  async function save(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try {
      const saved = await saveFinancialMonth(userId, { ...draft, period: `${draft.period}-01` })
      const rows = await getFinancialMonths(userId)
      setMonths(rows); setSelected(saved.period); setAdvice(null); setAnswer(null)
      setMessage(`${monthLabel(saved.period)} saved. Select this month and press Get advice when ready.`)
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
    try { setAnswer(await askFinancialMonth(userId, advice.month.period, question.trim())) }
    catch (requestError) { setError(explainApiError(requestError)) }
    finally { setBusy(false) }
  }

  return <section className="account-months" aria-labelledby="account-months-heading">
    <p className="research-small-label">YOUR ENTERED FINANCIAL HISTORY</p>
    <h3 id="account-months-heading">Build your own month-by-month situation</h3>
    <p>Enter an ordinary month first, then enter a later month with changed income or expenses. These are your account's records, separate from the current Profile snapshot. You can correct a month at any time.</p>
    <form onSubmit={save} className="account-month-form">
      <div className="account-month-fields">
        <label>Month<input name="period" type="month" max={todayMonth()} required value={draft.period} onChange={edit} /></label>
        <MoneyInput label="Income received" name="monthly_income" value={draft.monthly_income} onChange={edit} />
        <MoneyInput label="Total scheduled expenses" name="monthly_expenses" value={draft.monthly_expenses} onChange={edit} hint="Include the debt payment." />
        <MoneyInput label="Fixed expenses" name="fixed_expenses" value={draft.fixed_expenses} onChange={edit} hint="Excluding the debt payment." />
        <MoneyInput label="Scheduled debt payment" name="scheduled_emi" value={draft.scheduled_emi} onChange={edit} />
        <MoneyInput label="Debt payment actually made" name="paid_emi" value={draft.paid_emi} onChange={edit} />
        <MoneyInput label="Total liquid savings" name="savings" value={draft.savings} onChange={edit} hint="Include the emergency reserve." />
        <MoneyInput label="Emergency reserve" name="emergency_fund" value={draft.emergency_fund} onChange={edit} />
        <MoneyInput label="Outstanding debt" name="outstanding_debt" value={draft.outstanding_debt} onChange={edit} />
        <MoneyInput label="Expenses you could not fund" name="unfunded_expenses" value={draft.unfunded_expenses} onChange={edit} hint="Enter 0 if none." />
        <label>Risk preference<select name="risk_tolerance" value={draft.risk_tolerance} onChange={edit}>
          <option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option>
        </select></label>
        <label>Investment horizon, years<input name="investment_horizon_years" type="number" min="0" max="80" required value={draft.investment_horizon_years} onChange={edit} /></label>
      </div>
      <div className="account-month-buttons"><button type="submit" className="primary-action" disabled={busy}>Save this month</button>
        <button type="button" disabled={busy} onClick={() => setDraft(startingMonth(user, profile, nextMonth(months.at(-1)?.period)))}>Start next month</button></div>
    </form>
    {loading ? <p role="status">Loading your recorded months…</p> : months.length ? <>
      <h4>Months you entered</h4>
      <ul className="account-month-list">{months.map((row) => <li key={row.period}>
        <span><strong>{monthLabel(row.period)}</strong> · Income {amount(row.monthly_income)} · Expenses {amount(row.monthly_expenses)}</span>
        <span><button type="button" disabled={busy} onClick={() => { setDraft(formMonth(row)); setSelected(row.period); setAdvice(null); setAnswer(null) }}>Edit</button>
          <button type="button" disabled={busy} onClick={() => remove(row.period)}>Delete</button></span>
      </li>)}</ul>
      <div className="account-month-run"><label>Month to review<select value={selected} onChange={(event) => { setSelected(event.target.value); setAdvice(null); setAnswer(null) }}>
        {months.map((row) => <option key={row.period} value={row.period}>{monthLabel(row.period)}</option>)}
      </select></label>
      <label>What do you want advice on?<select value={focus} onChange={(event) => { setFocus(event.target.value); setAdvice(null); setAnswer(null) }}>
        <option value="all">Overall priorities</option>{Object.entries(names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      <button type="button" className="primary-action" disabled={busy} onClick={run}>{busy ? 'Working…' : 'Get advice for this month'}</button></div>
    </> : <p>No months saved yet. Start with a normal month so a later income change can be measured.</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="research-error">{error}</p>}
    {advice && <><AccountAdvice advice={advice} />
      <form className="account-month-question" onSubmit={ask}><h4>Ask about this month</h4>
        <p>Ask in your own words. The local language model uses this month's entered amounts and recorded specialist findings. Your question and answer are not saved.</p>
        <div><input aria-label="Your question about this month" value={question} maxLength={500} required minLength={3}
          onChange={(event) => setQuestion(event.target.value)} placeholder="For example, what should I review after my income dropped?" />
          <button type="submit" className="primary-action" disabled={busy || !question.trim()}>{busy ? 'Answering…' : 'Ask'}</button></div>
        {answer?.answer && <section aria-label="Answer about this month"><strong>Answer from local model</strong><p>{answer.answer}</p>
          <details><summary>Evidence used</summary><ul>{answer.evidence.map((item) => <li key={item.id}><strong>{item.label}:</strong> {item.detail}</li>)}</ul></details></section>}
        {answer?.source === 'unavailable' && <p role="status">{answer.reason} The recorded specialist findings above are still available.</p>}
      </form></>}
  </section>
}
