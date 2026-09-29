# Private Accounts and Saved Data — Design

## Intent and scope

FinApp should reopen a person's saved profile, goals, and advisory history after sign-in, and one account must never see another account's records. Signup asks for name, email, and password; financial inputs remain in the Profile flow. No practice records are created automatically. Issue #13 builds on issue #11, which is still awaiting merge when this branch starts.

The current browser-stored user ID is a locator, not proof of identity. It must stop selecting the signed-in account. Existing users, profiles, goals, and analysis sessions must survive the additive migration. A legacy record with no password remains inaccessible through ordinary signup or login until a local administrator issues a one-time claim code for its email. The user enters that code and a new password in the app; the record keeps its ID and all linked data.

## API and data model

- Add nullable `users.password_hash`, `users.legacy_claim_digest`, and `users.legacy_claim_expires_at`. A null password hash identifies an unclaimed legacy account. Canonicalize new account email to lowercase and enforce case-insensitive uniqueness. Preserve existing email spelling in old rows until claimed or edited.
- Add `auth_sessions` with user ID, SHA-256 digest of a random 256-bit opaque token, issued time, fixed seven-day expiry, and optional revocation time. Only the cookie contains the raw token. Logout revokes the row. Expired or revoked tokens fail every protected request.
- `POST /users` creates an account with Argon2id password hash, zero gross income, and no profile, then signs in. It no longer creates passwordless users. `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, and `POST /auth/claim` manage identity. Wrong credentials use one generic response. Passwords are 12–128 characters, never returned or logged. `POST /auth/claim` accepts email, one-time code, and password; it consumes the code atomically and signs in as the existing user.
- A local CLI command `python -m app.legacy_claim --email ADDRESS` generates a cryptographically random, single-use claim code, stores only its digest and a 30-minute expiry, and prints it once. It refuses missing or already claimed users. Running it again invalidates an earlier unconsumed code. No browser user ID or email alone can claim a record.
- All `/users/{user_id}` endpoints, including goals and advisory history, require a valid session for that exact ID. Missing session returns 401; another account's ID returns 404. Existing response shapes for financial records remain the same. `/health`, account creation, login, and claim are the only unauthenticated routes.
- Failed login attempts are limited per normalized email and client IP over a short database-backed window. The response does not reveal whether the email exists. This is basic local protection; a public deployment still needs edge rate limits, email verification, and password recovery.

## Browser session protection

- Session cookie is HttpOnly, SameSite=Strict, host-only, Path=/, and Secure except on an exact loopback HTTP host for local development. HTTPS uses the `__Host-` prefix. Browser code never stores credentials, tokens, or user IDs in localStorage.
- The API permits credentialed CORS only from explicit frontend origins. In local development these are `http://127.0.0.1:5173`, `http://localhost:5173`, and the feature preview on port 5174. Other origins are configured explicitly for deployment; no wildcard with credentials.
- Every mutating browser request includes a fixed custom `X-FinApp-Request` header. The API requires it and rejects a supplied Origin outside the allowlist. SameSite and Origin checks provide additional CSRF barriers. JSON bodies are required where payloads exist.
- Account routes return `Cache-Control: no-store`; financial endpoints should also avoid browser/shared-cache storage. Never put raw session or claim tokens in URLs.

## User experience

- On startup, the app asks `/auth/me` who is signed in. It shows a concise sign-in/signup screen if no valid session exists, and a retry state if the API is unavailable. Signing in opens that account's dashboard and loads its saved profile/goals/history. New accounts are guided to complete Profile.
- A separate “Claim an earlier local profile” form accepts email, code, and new password. It explains that the one-time code comes from a local administrator. It does not expose existing account details before a valid code is submitted.
- The signed-in header shows account name/email and Sign out. Signing out revokes the server session, clears account data from React state, and returns to sign-in. Expiry or 401 during a protected request does the same without retaining a prior account's view. Navigation and old requests cannot repopulate a different account's screen.
- Existing profile, goal, analysis, dashboard, and advisory flows stay usable after sign-in. No fake user or financial data is introduced.

## Verification and limits

- Test signup, password hashing, session persistence/revocation/expiry, legacy claim single-use/expiry, case-insensitive email collision, login throttling, CSRF/CORS, and ownership of every user/profile/goal/advisory route.
- Test startup, sign-in/signup/claim, sign-out, account switching, expired session, and a saved record reopening in the browser. Verify desktop and narrow viewport.
- Apply migration to local PostgreSQL without deleting existing data; test the claim flow against disposable records and leave the real Demo User unclaimed until its owner chooses a password.
- This issue does not add email delivery, password reset, email verification, MFA, or production hosting. The app remains a research prototype until those operational controls and HTTPS deployment are addressed.
