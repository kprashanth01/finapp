import { useEffect, useState } from 'react'
import { askLoanScenario, assessLoanScenario, createLoanScenario, deleteLoanScenario,
  explainApiError, getLoanScenarios, previewLoanScenario, updateLoanScenario } from '../services/api.js'
import { formatAmount } from '../utils/format.js'
import LoanScenarioForm from './LoanScenarioForm.jsx'
import LoanReadinessResults from './LoanReadinessResults.jsx'

export { loanScenarioPayload } from './LoanScenarioForm.jsx'
export { default as LoanReadinessResults } from './LoanReadinessResults.jsx'

const previewBlank = { income_next_month: '', one_time_extra: '', amount: '', annual_interest_rate_percent: '', tenure_months: '' }
const smallInput = 'mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm'

function LoanPreview({ userId, scenarioId, assessment }) {
  const [draft, setDraft] = useState(previewBlank)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => { setDraft({ ...previewBlank }); setResult(null); setError('') }, [scenarioId, assessment?.input_fingerprint])
  useEffect(() => {
    const entries = Object.entries(draft).filter(([, value]) => value !== '')
    if (!entries.length) { setResult(null); setError(''); setLoading(false); return }
    if (draft.income_next_month !== '' && draft.one_time_extra !== '') {
      setError('Test a changed monthly income or one-time extra cash, one at a time.')
      setResult(null); setLoading(false); return
    }
    let active = true
    const timer = setTimeout(async () => {
      setLoading(true); setError('')
      try {
        const values = Object.fromEntries(entries.map(([key, value]) =>
          [key, key === 'tenure_months' ? Number(value) : value]))
        const next = await previewLoanScenario(userId, scenarioId, values)
        if (active) setResult(next)
      } catch (failure) { if (active) { setResult(null); setError(explainApiError(failure)) } }
      finally { if (active) setLoading(false) }
    }, 350)
    return () => { active = false; clearTimeout(timer) }
  }, [draft, scenarioId, userId])
  function edit(key, value) { setDraft((current) => ({ ...current, [key]: value })) }
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6" aria-labelledby="loan-what-if-heading">
    <h3 id="loan-what-if-heading" className="text-xl font-semibold">What if things change?</h3>
    <p className="mt-1 text-sm text-slate-600">Try one future income change or extra cash, and adjust the proposed loan terms. The preview does not save any amount.</p>
    <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[['income_next_month', 'Income next month', 'Try a lower or higher monthly income'],
        ['one_time_extra', 'Extra cash this month', 'One-time only; not recurring income'],
        ['amount', 'Different loan amount', 'Leave blank to keep saved amount'],
        ['annual_interest_rate_percent', 'Different annual rate %', 'A new rate recalculates the EMI'],
        ['tenure_months', 'Different tenure (months)', 'A new tenure recalculates the EMI']].map(([key, title, hint]) =>
        <label key={key} className="block text-sm font-medium text-slate-700">{title}<input className={smallInput} type="number" min={key === 'tenure_months' || key === 'amount' ? '1' : '0'} step={key === 'tenure_months' ? '1' : '0.01'}
          value={draft[key]} onChange={(e) => edit(key, e.target.value)} /><span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span></label>)}
    </div>
    {loading && <p role="status" className="mt-4 text-sm text-slate-600">Updating preview…</p>}
    {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-900">{error}</p>}
    {result && <div className="mt-5 rounded-xl border border-teal-200 bg-teal-50 p-4">
      <h4 className="font-semibold text-teal-950">Temporary result</h4>
      <p className="mt-1 text-sm text-slate-700">{result.explanation}</p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-3 text-sm"><div><dt>Current gross room before savings</dt><dd className="font-semibold">{formatAmount(result.before.current_month.remaining_before_savings)}</dd></div>
        <div><dt>Preview gross room before savings</dt><dd className="font-semibold">{formatAmount(result.after.current_month.remaining_before_savings)}</dd></div>
        <div><dt>Preview proposed EMI</dt><dd className="font-semibold">{formatAmount(result.after.estimated_emi)}</dd></div></dl>
      {result.one_time_extra != null && <p className="mt-3 text-sm">Illustrative cash this month after current expenses and proposed EMI: <strong>{formatAmount(result.one_time_cash_after_expenses_and_emi)}</strong>. Reserve coverage stays {result.after.reserve_coverage_months ?? 'unknown'} months until a deposit is actually saved.</p>}
      <p className="mt-3 text-sm"><strong>Readiness: </strong>{result.after.summary}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{result.priority_advice.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>}
  </section>
}

const suggestions = ['Am I ready for this loan?', 'Can I afford this EMI?', 'Which requirement am I not meeting?',
  'What if I earn only 12000 next month?', 'What if I earn 20000 extra this month?', 'What changed in my readiness?']

function LoanChat({ userId, scenarioId }) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState([])
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setQuestion(''); setTurns([]); setError('') }, [scenarioId])
  async function ask(value) {
    const text = value.trim()
    if (text.length < 3 || asking) return
    setAsking(true); setError(''); setQuestion('')
    try {
      const reply = await askLoanScenario(userId, scenarioId, text)
      setTurns((old) => [...old, { question: text, reply }])
    } catch (failure) { setQuestion(text); setError(explainApiError(failure)) }
    finally { setAsking(false) }
  }
  return <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:p-6" aria-labelledby="loan-chat-heading">
    <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Your financial assistant</p>
    <h3 id="loan-chat-heading" className="mt-1 text-xl font-semibold">Ask about this loan assessment</h3>
    <p className="mt-1 text-sm text-slate-700">Answers use the same calculated readiness and saved facts shown above. They do not predict a lender decision. Questions are not saved.</p>
    <div className="mt-4 flex flex-wrap gap-2" aria-label="Suggested loan questions">{suggestions.map((item) =>
      <button type="button" key={item} disabled={asking} onClick={() => ask(item)} className="rounded-full border border-teal-300 bg-white px-3 py-1.5 text-sm disabled:opacity-50">{item}</button>)}</div>
    {turns.length > 0 && <ol className="mt-4 space-y-3" aria-label="Loan questions and answers">{turns.map((turn, index) =>
      <li key={index} className="rounded-xl bg-white p-4"><p className="text-sm font-semibold">You: {turn.question}</p>
        <p className="mt-2 text-sm text-slate-800">{turn.reply.answer}</p>
        {turn.reply.evidence.length > 0 && <details className="mt-2 text-xs text-slate-600"><summary className="cursor-pointer font-medium">See assessment facts used</summary>
          <ul className="mt-2 list-disc pl-5">{turn.reply.evidence.map((fact) => <li key={fact.key}>{fact.name}: {fact.current_value ?? 'not provided'} · {fact.source_label}</li>)}</ul></details>}</li>)}</ol>}
    <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(question) }}><label className="sr-only" htmlFor="loan-chat-question">Your loan question</label>
      <input id="loan-chat-question" value={question} onChange={(e) => setQuestion(e.target.value)} disabled={asking}
        className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Ask about your readiness…" />
      <button type="submit" disabled={asking || question.trim().length < 3} className="rounded-lg bg-teal-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{asking ? 'Answering…' : 'Ask'}</button></form>
    {error && <p role="alert" className="mt-2 text-sm text-rose-800">{error}</p>}
  </section>
}

export default function LoanReadiness({ userId, profile, onOpenProfile, onOpenMonths }) {
  const [scenarios, setScenarios] = useState([])
  const [selected, setSelected] = useState(null)
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(true)
  const [assessing, setAssessing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  useEffect(() => {
    if (!profile) { setLoading(false); return }
    let active = true
    getLoanScenarios(userId).then(async (items) => {
      if (!active) return
      setScenarios(items)
      if (items.length) {
        setSelected(items[0]); setAssessing(true)
        try { const result = await assessLoanScenario(userId, items[0].id); if (active) setAssessment(result) }
        catch (failure) { if (active) setError(explainApiError(failure)) }
        finally { if (active) setAssessing(false) }
      }
    }).catch((failure) => { if (active) setError(explainApiError(failure)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userId, profile])
  async function select(item) {
    setSelected(item); setAssessment(null); setError(''); setFormError('')
    if (!item) return
    setAssessing(true)
    try { setAssessment(await assessLoanScenario(userId, item.id)) }
    catch (failure) { setError(explainApiError(failure)) }
    finally { setAssessing(false) }
  }
  async function save(values) {
    setSaving(true); setFormError('')
    try {
      const saved = selected ? await updateLoanScenario(userId, selected.id, values) : await createLoanScenario(userId, values)
      setScenarios((old) => [saved, ...old.filter((item) => item.id !== saved.id)])
      setSelected(saved); setAssessment(null); setAssessing(true)
      setAssessment(await assessLoanScenario(userId, saved.id))
    } catch (failure) { setFormError(explainApiError(failure)) }
    finally { setSaving(false); setAssessing(false) }
  }
  async function remove() {
    if (!selected || !window.confirm('Delete this proposed loan and its readiness history?')) return
    setSaving(true); setFormError('')
    try {
      await deleteLoanScenario(userId, selected.id)
      const remaining = scenarios.filter((item) => item.id !== selected.id)
      setScenarios(remaining); await select(remaining[0] ?? null)
    } catch (failure) { setFormError(explainApiError(failure)) }
    finally { setSaving(false) }
  }
  if (!profile) return <div className="rounded-xl bg-teal-50 p-5"><h2 className="text-xl font-semibold">Prepare for a loan</h2>
    <p className="mt-2 text-sm">Save your financial Profile first so the assessment has expenses, debt and reserve amounts.</p>
    <button type="button" className="mt-3 font-semibold text-teal-800 underline" onClick={onOpenProfile}>Open Profile</button></div>
  return <div className="space-y-7">
    <header><h2 className="text-2xl font-semibold">Prepare for a loan</h2>
      <p className="mt-2 text-slate-600">See how a proposed fixed payment fits your current finances and lower-income months. This is preparation, not a lender approval or eligibility decision.</p></header>
    {loading ? <p role="status">Loading your saved loan scenarios…</p> : <>
      {error && <div role="alert" className="rounded-lg bg-rose-50 p-4 text-sm text-rose-900">{error}
        {selected && <button type="button" className="ml-2 underline" onClick={() => select(selected)}>Retry assessment</button>}</div>}
      <div className="flex flex-wrap items-end gap-3"><label className="text-sm font-medium">Proposed loan
        <select className={smallInput} value={selected?.id ?? ''} onChange={(e) => select(scenarios.find((item) => item.id === Number(e.target.value)) ?? null)}>
          <option value="">New loan scenario</option>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button type="button" className="text-sm font-semibold text-teal-800 underline" onClick={() => select(null)}>Create another scenario</button></div>
      <LoanScenarioForm scenario={selected} onSave={save} onDelete={remove} saving={saving} error={formError}
        onOpenProfile={onOpenProfile} onOpenMonths={onOpenMonths} />
      {assessing && <p role="status">Calculating readiness from your latest saved finances…</p>}
      {assessment && selected && <>
        <LoanReadinessResults assessment={assessment} />
        <LoanPreview key={`preview-${selected.id}`} userId={userId} scenarioId={selected.id} assessment={assessment} />
        <LoanChat key={`chat-${selected.id}`} userId={userId} scenarioId={selected.id} />
      </>}
    </>}
  </div>
}
