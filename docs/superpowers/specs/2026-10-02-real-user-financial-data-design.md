# Issue 2: Real-user financial data

## Intent and boundary

People can start with the current aggregate profile and add detail only when useful. The saved Advisor remains based on the existing profile, goals, and rule-based plan in this issue. The new records prepare a trustworthy source for Issue 3's deterministic analysis. Recorded `FinancialMonth` rows remain observed history; they are never silently treated as guaranteed income.

## Data contracts

- Add optional `income_pattern` (`stable`, `variable`, or `mixed`) and `guaranteed_monthly_income` to `FinancialProfile`. The existing `User.monthly_income` remains the user's current gross monthly estimate. A missing guarantee stays unknown.
- Add account-owned `RecurringExpense` rows: name, monthly amount, and one of `essential_fixed`, `essential_variable`, `discretionary`. These describe portions of the profile's non-debt monthly expenses; they do not add to its total. Loans are excluded from these rows.
- Add account-owned `Loan` rows: name, optional remaining balance, optional monthly payment, optional type, optional annual interest rate, optional payment day, and optional rate-change date/rate. These describe portions of the profile's aggregate debt and payment; they do not add to those totals. Unreported balances and payments remain unknown.
- Add account-owned `PlannedExpense` rows: name, estimated amount, optional amount reserved, due date, and whether it is essential. These are one-time future commitments, separate from recurring monthly expenses and goals. An unreported reserved amount remains unknown rather than zero.
- The entry flow tells users to keep a cost already tracked as a goal in Goals, avoiding a duplicate commitment. Cross-linking goals and planned expenses is outside this issue.
- All amounts use `Decimal` with two decimal places. Rates are percentages as entered, not fractions. No currency is inferred.

## Persistence and API

Migration `0009` adds the two optional profile fields and three tables with foreign keys, nonnegative money checks, relevant date/rate checks, and account indexes. Migrations `0010` and `0011` permit unknown loan payments and balances without storing false zeroes. `GET /users/{user_id}/financial-details` returns the optional fields, arrays, and breakdown subtotals. `PUT` to the same path replaces the optional detail snapshot atomically, preserving row IDs that the caller owns. Removed rows are deleted. Cross-account or duplicate IDs are rejected. Existing profile endpoints keep their contract.

On every detail save, validate that expense rows fit within monthly expenses after known debt payments (using the aggregate payment when present, otherwise the sum of entered loan payments), loan balances fit within aggregate debt, and known loan payments fit within a known aggregate payment. A profile edit must preserve these invariants. A missing aggregate debt payment does not turn an entered loan payment into zero; the detail is stored but the plan remains limited by its existing missing-input behavior. The API returns a clear 422 when entered detail exceeds a saved aggregate.

## User flow

Profile retains the quick aggregate form. A separate expandable section offers income context, recurring expense breakdown, loan details, and upcoming one-time costs. It shows subtotals against the current profile and states that those details are descriptive until analysis incorporates them in Issue 3. Months remains the income-history entry point. Every new field is optional; the page does not block a basic profile or plan when no detail exists.

## Verification

Focused API tests cover persistence, update/removal, account ownership, cross-total constraints, and preservation of existing saved plans. Frontend tests cover the optional section and submission contract. Run the full backend and frontend suites and production build. A live PostgreSQL migration requires the configured local database and is reported separately if unavailable.
