# Issue 3: Deterministic financial analysis

## Boundary

Extend the existing account-owned `financial-analysis` response with a versioned, structured financial picture. Preserve its five existing metrics and the saved Advisor state/result contracts. The new picture is read-only: it uses current Profile values, optional detail, active goals, and recorded Months. It neither changes balances nor chooses a recommendation. Later scenario and conversational work should consume these calculated facts rather than recalculate them.

## Source rules

- The current income estimate and aggregate expenses come from User/Profile. Recorded Months are observations, not forecasts or guarantees. Return the recent observed income, mean, minimum, and population coefficient of variation over at most 12 recorded months. Variability needs two observations. The conservative planning reference needs three consecutive recent months, ending in the current or preceding calendar month; it is the lesser of the current estimate and lowest income in that sequence. Label it a stress reference, not guaranteed income.
- Aggregate monthly expenses already include debt payments. Expense items describe the non-debt portion. Return categorized known amounts and an unclassified remainder. An exact essential/discretionary split is only available when debt payment is known and item totals cover all non-debt expenses. If not, leave exact totals unknown and show known lower bounds.
- Gross cash flow is income estimate minus aggregate expenses; its positive portion is an **upper bound**, not spendable cash. Savings rate uses the entered monthly savings contribution. Debt-to-income uses the aggregate required payment. Never infer either from loan detail when the corresponding Profile amount is unknown.
- The emergency gap uses the existing three-month **total-expense** target so it agrees with the saved Advisor. Report essential-expense coverage only when the exact essential split is known. For active goals, calculate remaining target amount. For planned expenses, calculate unreserved amount only when a reserved amount was supplied; show future and overdue items separately. Loan due dates are calculated from entered payment days; those payments are already in monthly expenses and are not added to one-time obligations.
- Every computed metric carries a source and status (`known`, `partial`, `unknown`, or `estimate`) plus a short limitation. Unknown remains null rather than zero. No currency or tax estimate is inferred.

## UI and compatibility

Show the picture in an expandable Financial snapshot section on Dashboard with income history, cash flow, expense completeness, reserve, goals, and upcoming costs. Keep the saved plan visually separate. Refresh analysis after optional detail, goal, and recorded-month edits. Old saved sessions remain readable and retain their original fingerprints; Issue 5 will decide how to incorporate new facts into recommendations.

## Verification

Pure calculation tests cover complete and partial categories, absent and consecutive income history, signed cash flow, missing debt payment, goal gaps, due dates, and overdue obligations. API tests cover account ownership and use of only the signed-in user's records. Frontend tests cover source/unknown labels and the website rendering. Run the existing backend/frontend suites and build.
