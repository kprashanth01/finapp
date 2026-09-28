# Dashboard and advisory history design

## Intent

Make the financial profile and rule-based analysis understandable from the app itself. A user who has saved a profile can see their current values and latest finding at a glance, then reopen older advisory sessions. All displayed data comes from that user's existing PostgreSQL records. The feature adds no seeded users, generated financial data, login, or new financial rules.

## Approach

Use three lightweight views in the existing React app: **Dashboard**, **Profile**, and **Advisor**. This keeps the current forms and advisory components, while giving the saved data a clear entry point. A single long page with history appended would be quicker, but would make the already long flow harder to scan. Adding React Router is unnecessary for three local views; view selection can remain client-side state until real account navigation is designed.

The browser still remembers one user ID in local storage. This is a local convenience, not account access. The dashboard must not present it as a login or offer a way to browse other user IDs. Authentication and migration of existing users with no credentials belong in a separate issue.

## Current data and dashboard

The Dashboard view shows the saved user's name, the saved monthly income, expenses, savings balance, outstanding debt, emergency fund, risk tolerance, and optional financial goal. It shows the existing calculated snapshot values with their current unavailable states; it does not calculate new ratios in React. A latest-analysis card shows its date, whether it is stale, and its priority titles (or that the rules produced none), with a way to open Advisor. Empty states direct a new user to create a profile or run an analysis. A dashboard reload uses the existing user/profile/analysis/latest-session API calls.

The Profile view retains the existing user and financial-profile editing forms. The Advisor view retains the latest-run panel and adds session history below it. After a save or run, the views refresh from the saved API result, so a historical finding is never silently presented as current.

## History API and UI

- `GET /users/{user_id}/advisory-sessions?limit=10&before_id=<optional>` returns a page of summaries in descending session-ID order, plus a `next_before_id` cursor when another page exists. Limit is bounded to 1–50. Each summary includes the database session ID, creation time, method/version, stale status against today's saved financial inputs, and priority finding titles/count. The list filters by the path user ID.
- `GET /users/{user_id}/advisory-sessions/{session_id}` returns the same structured session shape as the existing latest endpoint. A session owned by another user returns 404.
- The existing latest endpoint remains unchanged. No migration is needed because analysis sessions already store an immutable structured result and input fingerprint; the existing `(user_id, id)` index supports descending pages.
- The Advisor view initially shows the latest run. The history list loads saved runs, with a **Load more** control if there is another page. Selecting a run shows its stored findings and the financial inputs captured in `result.state`: gross monthly income, monthly expenses, monthly savings contribution, monthly debt payments, outstanding debt, and emergency fund. The panel labels the numeric key as **session ID**, never as the user's run count. Reopening a past run cannot alter it.
- Savings balance, risk tolerance, goal, and investment horizon are included in the fingerprint but not stored in historical `result.state`; the UI will not reconstruct or imply historical values for them. The current dashboard can show their current saved values. A full profile audit trail is outside this issue.

## Failure behavior

The current profile remains usable if history cannot load; Advisor shows a retryable history error. A missing or other-user session shows an error without replacing the currently displayed run. Empty history states plainly say no runs have been saved. Stale status refers to differences from current saved financial inputs, not time elapsed. An analysis run or saved profile edit refreshes the latest session and history summaries. No unsaved form values appear in dashboard or historical views.

## Files and verification

Likely edits: `backend/app/api.py`, `backend/app/advisory/types.py`, and focused API tests; `frontend/src/App.jsx`, `frontend/src/components/AdvisorySession.jsx`, `frontend/src/services/api.js`; a small dashboard/history component if it keeps `App.jsx` readable; `README.md`. No database migration or new package is expected.

Verify the API's descending order, cursor boundary, user ownership, empty list, and stale summaries with focused tests. Verify the browser flow against PostgreSQL: load an existing profile, see dashboard values, run analysis, reopen it from history, edit a financial input, observe stale status, then rerun. Check narrow-screen layout and browser errors. Do not populate the user's database with demo records for verification; temporary QA records must be removed.
