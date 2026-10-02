# Make month entry accurate and prevent double-counted spending

## User problem

A new Months record silently starts with current Profile income, expenses, and balances. Entering essential bills on top of the copied “other” amount can count the same spending twice. These records now drive a coordinated plan preview, so inaccurate inputs mislead the user.

## Scope

Start a new month with empty financial amounts and offer an explicit **Use current Profile as a starting point** action. Let the user enter total monthly spending once, then essential bills and the loan payment due; calculate other spending as the remainder. Show balances and actual payments in a visible section and validate their relationships before saving. Preserve saved-month editing, explicit next-month copy, the database schema, and Research entry.

## Acceptance

- No financial amount is silently copied into a new primary Months record.
- Profile import is explicit and still requires the user to identify essential bills.
- Essential bills plus loan due cannot exceed total spending.
- Saved month editing and Research entry continue to work.
- Focused tests verify totals, validation, and the visible entry flow.
