# Issue 2 implementation plan

## Files and interfaces

1. `backend/app/models.py` and migrations `0009_real_user_details.py`, `0010_optional_loan_payment.py`, and `0011_optional_loan_balance.py`: optional profile income fields plus `RecurringExpense`, `Loan`, and `PlannedExpense` account-owned tables. Keep existing aggregate columns and saved result payloads intact. Missing balances, payments, and reserved amounts remain null.
2. `backend/app/financial_detail_schemas.py`: strict Pydantic write/read models. `FinancialDetailsWrite` is an atomic snapshot with optional income fields and arrays of records carrying optional IDs. `FinancialDetailsRead` adds subtotals.
3. `backend/app/services/financial_details.py`: validate cross-total invariants and make the account's detail snapshot. `backend/app/financial_details_api.py` exposes GET/PUT; register it in `main.py`. `api.py` calls the same validator before a profile edit commits.
4. `frontend/src/services/api.js` and `frontend/src/components/FinancialDetails.jsx`: load, edit, and save optional detail. Mount below the core profile form in `Workspace.jsx`. Reuse the existing Months link for observed income history.
5. Update user documentation to distinguish profile totals, descriptive details, and observed months.

## Red/green steps

1. Add API tests for an empty snapshot and a complete snapshot; run them to see the missing endpoint, then add schemas, models, migration, and GET/PUT.
2. Add API tests for ID ownership, replacement/removal, invalid amounts, and detail totals exceeding profile totals; see failure, then implement atomic validation.
3. Add a profile-edit regression test showing an edit cannot make existing detail exceed its aggregate; see failure, then call the shared validator from profile save.
4. Add a frontend test for optional data entry and the API request; see failure, then implement the component and mount it.
5. Run focused tests, full backend and frontend suites, frontend build, migration check when a local PostgreSQL server is available, and inspect the diff.

## Review focus

- A foreign record ID must never be reassigned to the current account.
- Repeated IDs in one PUT must fail instead of creating ambiguous updates.
- Loan payments must not be added to recurring expenses a second time.
- A missing aggregate debt payment must remain unknown, not zero.
- Old saved analysis JSON must remain readable after migration.
