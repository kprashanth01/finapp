import { summarizeMonths } from '../services/monthlyPlanning.js'
import { formatAmount } from '../utils/format.js'

const money = (cents) => formatAmount(cents / 100)
const monthLabel = (period) => new Date(`${period}T12:00:00`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

export default function MonthlyPlanningSummary({ months, profile, onOpenProfile }) {
  const summary = summarizeMonths(months, profile)
  if (!summary) return null
  const { latest, lowest, sampleCount, latestRemainderCents, latestObligationsCents,
    plannedContributionCents, lowIncomeObligationGapCents, lowIncomeAfterObligationsCents } = summary

  return <section className="account-month-summary" aria-labelledby="monthly-planning-heading">
    <h4 id="monthly-planning-heading">What your recorded months mean for your plan</h4>
    <p>Latest entered month: <strong>{monthLabel(latest.period)}</strong>. Income {formatAmount(latest.monthly_income)} less entered spending {formatAmount(latest.monthly_expenses)}: {latestRemainderCents >= 0
      ? <strong>{money(latestRemainderCents)} left after entered spending.</strong>
      : <strong>{money(-latestRemainderCents)} short after entered spending.</strong>}</p>
    {latestRemainderCents < 0 && <p>This recorded month had no income left for a new savings contribution. Review bills and the saved contribution before relying on the Dashboard allocation.</p>}
    {plannedContributionCents == null ? <p>Add a planned monthly savings amount in Profile before relying on a funded allocation.</p>
      : plannedContributionCents > Math.max(0, latestRemainderCents)
        ? <p>Profile plans {money(plannedContributionCents)} in monthly savings, above the {money(Math.max(0, latestRemainderCents))} left after entered spending. If this month reflects your current situation, review the saved contribution and run a new plan.</p>
        : <p>Profile plans {money(plannedContributionCents)} in monthly savings. This is within the latest entered month’s remaining amount, but confirm what you can actually set aside before using the allocation.</p>}
    {sampleCount > 1 && <p>If the lowest recorded income recurred ({formatAmount(lowest.monthly_income)} in {monthLabel(lowest.period)}) while the latest essential bills and loan payment stayed at {money(latestObligationsCents)}, it would be {lowIncomeObligationGapCents > 0
      ? <strong>{money(lowIncomeObligationGapCents)} short of those essential obligations.</strong>
      : <strong>{money(lowIncomeAfterObligationsCents)} above those obligations before other spending.</strong>}</p>}
    {sampleCount > 1 && lowIncomeObligationGapCents > 0 && <p>If you have not already covered that gap, use the worksheet below to see what remains after keeping that amount unallocated.</p>}
    <p className="text-xs">This check uses up to 12 months you entered. The low-income comparison is hypothetical, not a forecast. Recorded figures may omit taxes, timing, and other costs; no money is moved or allocated by this check.</p>
    <button type="button" onClick={onOpenProfile} className="mt-2 text-sm font-semibold text-teal-800 underline">Review planned savings in Profile</button>
  </section>
}
