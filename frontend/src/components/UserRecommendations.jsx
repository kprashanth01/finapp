import { useEffect, useState } from 'react'
import { explainApiError, getUserRecommendations } from '../services/api.js'
import { formatAmount } from '../utils/format.js'

function calculationText(item) {
  if (item.value == null) return 'Unknown'
  if (item.unit === 'currency') return formatAmount(item.value)
  if (item.unit === 'percent') return item.value + '%'
  if (item.unit === 'months') return item.value + ' months'
  if (item.unit === 'days') return item.value + ' days'
  return String(item.value)
}

function sourceText(source) {
  if (source.startsWith('saved_goal') || source.startsWith('remaining_goal')) return 'Goals'
  if (source.startsWith('saved_planned')) return 'Profile upcoming costs'
  if (source.startsWith('saved_loan')) return 'Profile loan detail'
  if (source.startsWith('recorded_months') || source.includes('recent_recorded_months')) return 'Recorded Months'
  if (source.includes('expense_details')) return 'Profile expense detail'
  if (source.includes('profile') || source.includes('gross_cash_flow')) return 'Profile'
  return 'Saved financial picture'
}

function RecommendationCard({ item, onOpenProfile, onOpenGoal, onOpenMonths, primary = false }) {
  function openTarget() {
    if (item.target_view === 'goals') onOpenGoal?.(item.target_id)
    else if (item.target_view === 'months') onOpenMonths?.()
    else onOpenProfile?.()
  }
  return <article className={primary ? 'rounded-xl border border-teal-200 bg-white p-5 shadow-sm' : 'rounded-lg border border-slate-200 bg-white p-4'}>
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Priority {item.priority} · {item.urgency} · {item.area.replace('_', ' ')}</p>
    <h4 className="mt-2 text-lg font-semibold text-slate-900">{item.action}</h4>
    <p className="mt-2 text-sm text-slate-700">{item.reason}</p>
    {item.supporting_calculations.length > 0 && <dl className="mt-3 grid gap-2 sm:grid-cols-2">
      {item.supporting_calculations.map((calc) => <div key={calc.label} className="rounded-lg bg-slate-50 p-3">
        <dt className="text-xs text-slate-600">{calc.label}</dt>
        <dd className="mt-1 text-sm font-semibold">{calculationText(calc)}</dd>
        <p className="mt-1 text-xs text-slate-500">Source: {sourceText(calc.source)}</p>
      </div>)}
    </dl>}
    <details className="mt-3 text-xs text-slate-600">
      <summary className="cursor-pointer font-medium">Why this priority and what it assumes</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {item.priority_factors.map((factor) => <li key={factor}>{factor}</li>)}
        {item.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}
      </ul>
    </details>
    <button type="button" onClick={openTarget} className="mt-3 text-sm font-semibold text-teal-900 underline underline-offset-4">
      {item.target_view === 'goals' ? 'Review this goal' : item.target_view === 'months' ? 'Open recorded months' : 'Review saved details'}
    </button>
  </article>
}

export function RecommendationContent({ data, onOpenProfile, onOpenGoal, onOpenMonths }) {
  const [first, ...others] = data.recommendations
  return <div className="mt-4 space-y-4">
    <p className="text-sm text-slate-600">Calculated from saved information as of {data.as_of_date}. The order responds to due dates, shortfalls, income uncertainty, and your goal priorities.</p>
    {first && <RecommendationCard item={first} primary onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} onOpenMonths={onOpenMonths} />}
    {others.length > 0 && <details className="rounded-xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer font-semibold">{others.length} more {others.length === 1 ? 'action' : 'actions'} to review</summary>
      <div className="mt-4 space-y-3">{others.map((item) => <RecommendationCard key={item.code} item={item}
        onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} onOpenMonths={onOpenMonths} />)}</div>
    </details>}
    <p className="text-xs text-slate-600">{data.limitations.join(' ')}</p>
  </div>
}

export default function UserRecommendations({ userId, onOpenProfile, onOpenGoal, onOpenMonths }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let alive = true
    getUserRecommendations(userId).then((result) => {
      if (alive) { setData(result); setLoading(false); setError('') }
    }).catch((failure) => {
      if (alive) { setData(null); setLoading(false); setError(explainApiError(failure)) }
    })
    return () => { alive = false }
  }, [userId, retry])
  return <section aria-labelledby="user-recommendations-heading" className="rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:p-6">
    <h3 id="user-recommendations-heading" className="text-xl font-semibold text-teal-950">What should I do this month?</h3>
    {loading && <p role="status" className="mt-3 text-sm text-slate-600">Checking current saved information…</p>}
    {error && <div className="mt-3 text-sm"><p role="alert" className="text-rose-800">Recommendations could not load: {error}</p>
      <button type="button" onClick={() => { setLoading(true); setRetry((value) => value + 1) }} className="mt-2 font-medium underline">Retry recommendations</button></div>}
    {data && <RecommendationContent data={data} onOpenProfile={onOpenProfile} onOpenGoal={onOpenGoal} onOpenMonths={onOpenMonths} />}
  </section>
}
