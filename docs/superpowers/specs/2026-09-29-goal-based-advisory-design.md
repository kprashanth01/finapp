# Six-agent advisory baseline and goal planning

Issue: https://github.com/kprashanth01/finapp/issues/11

Branch: `feature/goal-based-advisory`, based on merged main `3c08dc9`.

## Intent and success

The user wants each issue to deliver a substantial, understandable part of the research project. This milestone completes the six-agent rule-based baseline and turns its findings into a useful planning workflow. Ease of viewing, insight, and clear next actions are acceptance criteria alongside correct calculations.

A person should be able to save a measurable goal and answer these questions from the result without reading agent diagnostics:

1. What needs my attention first, and why?
2. How is my recorded monthly savings contribution proposed to be used?
3. How much does each goal need, what does this plan allocate, and what should I adjust?
4. Is investment planning currently supported by my profile, and what limits it?

The current Budget, Debt, and Emergency agents remain. Goal Planning, Risk Assessment, and Investment agents join their common interface and registry. A shared orchestrator interface and structured results prepare the later RL milestone. Login and private account access are the next separate milestone.

## User experience

### Navigation and goals

Keep Dashboard, Profile, and Advisor; add Goals. Use stable navigation and clear selected states. Avoid numbered setup steps after initial profile creation.

Goals starts with one short explanation and an Add goal action. It does not contain example goals. The form asks for name, target amount, target date, amount already saved toward this goal, and priority (High, Medium, Low; default Medium). Required fields and validation appear beside the relevant input. Goal balance help says to enter money earmarked for that goal and exclude emergency savings or money already assigned to another goal.

Each goal shows amount saved versus target, remaining amount, deadline, and an edit action. Archive preserves data and has an accessible undo/restore action. Completed goals remain visible until archived. Archived goals are collapsed separately and excluded from new planning runs.

The existing free-text `financial_goal` is preserved in a collapsed previous-goal note on Goals, without inventing a target or deadline. Remove the duplicate free-text editor from the main Profile form while preserving its value in profile writes. An explicit Add goal action can prefill the name from that note, with the normal 100-character validation; the user can also explicitly clear the old note. Creating a structured goal never happens automatically.

### Dashboard

Retain current saved balances and snapshot metrics. Add a small goal summary and the highest-priority insight from the latest plan, with links to Goals or Advisor. Do not duplicate the entire advisory report. Missing inputs link directly to the appropriate profile fields. Old or out-of-date results have a visible Update analysis action.

### Advisor result, in reading order

1. **Summary:** a short overall status, the leading issue, and the next useful action. Use factual language such as “Your current plan leaves two goals underfunded.”
2. **Monthly plan:** show the recorded monthly contribution, proposed emergency allocation, goal allocations, and any unassigned remainder. Explicitly call these planned amounts; running analysis does not transfer money or change balances.
3. **Goal outcomes:** for each active goal show saved progress, approximate months remaining, monthly amount needed to meet its date, proposed monthly amount, and funding gap. Distinguish completed, overdue, budget covered, underfunded, and missing-budget states. “Budget covered” applies to this month's plan and is not a guaranteed forecast.
4. **Investment readiness:** a simple ready-to-consider / deferred / insufficient-information result, the broad planning category when supported, and the specific factors behind it.
5. **Why this plan:** expandable formulas, assumptions, priority rules, evidence, and contributing agents. A separate expandable research detail section holds agent selection, rule version, and captured inputs.
6. **Saved runs:** preserve the current history and earlier-run viewing flow below the current result.

Do not lead the screen with database IDs, rule versions, six equal agent cards, or repeated disclaimers. Keep one concise educational context note and put rule-specific limitations beside the affected conclusion or in its explanation. Values use consistent amount formatting and the profile's existing currency-neutral convention. Status is conveyed by text as well as color.

Goal and profile saves visibly mark the plan out of date. They do not silently run an analysis or overwrite an earlier result. Preserve entered values on validation/network failures. While a save or analysis is pending, prevent conflicting submissions and avoid pairing updated inputs with old calculations.

## Goal persistence and API

Add a `financial_goals` table with user foreign key, name, target_amount, saved_amount, target_date, priority, archived flag, and created/updated timestamps. Use decimal currency columns and an index supporting user and archive-state queries.

- Name: trimmed, 1–100 characters.
- Target amount: strictly positive, the existing currency precision and maximum size.
- Saved amount: nonnegative; an amount above the target is allowed and is treated as completed.
- Target date: valid date. Existing or newly recorded overdue goals are allowed and explained rather than divided by a zero/negative period.
- Priority: High, Medium, or Low.
- Every query and mutation includes user ownership. These checks do not constitute authentication.

Provide user-scoped list/create/edit operations and an archive/restore operation. A goal belonging to a different user returns 404. Mutating a goal does not update the profile's savings balance automatically.

Goal saved amounts are self-reported earmarks. The app cannot verify whether someone has entered the same existing funds under two goals. It must explain that constraint and must not add goal balances to the profile savings balance or automatically spend the latter. The enforceable conservation rule in this milestone concerns the single monthly planning budget.

## Calculation conventions

Use Decimal for amounts and ratios. Capture an explicit analysis date in each new result, supplied by the backend clock; tests can inject a fixed date. The UI shows that date.

For an incomplete future goal:

- Remaining amount = max(target amount − saved amount, 0).
- Approximate months = ceiling(days until target date / 30), at least one for a future date.
- Required monthly amount = remaining amount / approximate months, rounded upward to cents.

The explanation states the 30-day month approximation and assumes no investment growth or interest. A completed goal requires zero additional funding. An incomplete goal due today or earlier is overdue; it has no invented monthly requirement and receives an action to update the date or progress. It is excluded from automatic monthly goal allocation until its date is future.

The monthly planning budget is the recorded `monthly_savings_contribution`. Null means unknown; zero is a known zero. Do not infer it from gross income minus expenses, or from existing savings. Unknown budgets still allow goal requirement calculations but cannot produce numeric allocations or an affordability verdict.

## Agents and coordination

All six agents independently consume the same immutable state and return structured findings, evidence, limitations, and typed planning values. The recommendation engine must not parse explanatory prose to make decisions. Agents do not call one another or depend on which orchestrator selected them.

| Agent | Responsibility |
| --- | --- |
| Budget | Retain existing ratios and high-expense checks; identify whether a monthly contribution is known. |
| Debt | Retain the debt-payment ratio and recorded balance checks. Indicate elevated burden or missing payment data when debt exists. No APR or payoff schedule is invented. |
| Emergency | Retain reserve coverage and the gap to the configured three-month reserve target. |
| Goal Planning | Produce per-goal remaining balances, deadlines, monthly requirements, and aggregate demand. |
| Risk Assessment | Report stated risk preference and observable capacity constraints from reserve, debt, contribution, and horizon; explain each factor. No unsupported probability or confidence score. |
| Investment | Assess prerequisites and broad planning category using risk preference and horizon. Final use of spare monthly capacity is coordinated after reserve and goal needs are considered. |

The rule-based orchestrator selects Budget, Emergency, Risk, and Investment for every saved financial profile (including an explicit limited result when data is missing). It selects Debt when a positive balance or payment is recorded and Goal Planning when at least one non-archived goal exists. Each selected and skipped agent has a reason. Add an orchestrator protocol whose run signature accepts state and registry, returning the shared result contract; the existing rule-based implementation remains the active implementation.

Keep rule constants together and bump the rule version. Preserve the existing illustrative expense threshold of 80%, debt-payment threshold of 20%, and reserve target of three months. These are transparent project rules, not validated recommendations.

### One shared monthly budget

The recommendation engine consumes agent outputs and the orchestration decision. If the emergency reserve requirement cannot be assessed (for example, monthly expenses are zero), retain the known capacity as unassigned and ask for the missing planning input. Otherwise, with known monthly capacity:

1. Propose up to the remaining emergency reserve gap, capped by this month's capacity.
2. If recorded debt burden meets the configured high threshold, or debt exists but its payment ratio cannot be assessed, hold the remaining capacity unassigned pending debt review. Explain the missing information or burden; do not invent an extra debt payment.
3. Otherwise allocate to incomplete future goals in High/Medium/Low order, then earliest deadline, then stable goal ID. Each allocation is capped by that goal's required monthly amount, remaining goal balance, and remaining capacity.
4. Leave any residual amount explicitly unassigned. If investment prerequisites are satisfied, describe it as available to consider for investment planning; never allocate it to a security or imply a transaction occurred.

Allocations and unassigned capacity must be nonnegative and sum exactly to the known contribution. Goals do not each receive the full contribution independently. Completed and archived goals consume no capacity. If capacity is unknown, allocations and gaps that depend on it are unknown, not zero.

For each future goal, show max(required monthly amount − proposed goal allocation, 0) as its plan funding gap. A reserve-first decision can therefore leave a goal underfunded even if that goal alone fits the budget. Explain that relationship and link to editing goal dates, priorities, or the recorded contribution. Do not claim the goal will automatically catch up in later months.

### Risk and investment interpretation

Missing required data produces an insufficient-information result. Investment consideration requires positive recorded income and monthly contribution, the reserve target met, no elevated/unknown debt-payment burden when debt exists, a positive investment horizon, and no unfunded or overdue active goal under this plan.

For a supported profile, use the stated conservative/moderate/aggressive preference, capped by an illustrative horizon rule: less than three years supports only a conservative short-horizon planning category; three to under seven years supports at most moderate; seven years or longer supports any stated category. Explain that the category is a research heuristic. Do not output securities, returns, percentages, market predictions, or claims of suitability.

The Investment agent supplies prerequisite findings; the coordinator can defer its conclusion when Goal Planning reveals competing needs. Store that conflict and its evidence so the UI can explain it. Recommendation priority follows emergency reserve, debt review, goal funding, then investment consideration; budget and missing-data actions accompany the relevant blockers.

## State, persistence, and historical compatibility

New state captures all inputs used: existing financial amounts and ratios, savings balance, risk preference, horizon, non-archived goal snapshots, and analysis date. Stable goal ordering makes fingerprints reproducible. New results preserve agent evidence, selection reasons, the coordinated monthly plan, goal assessments, readiness, and explanation references in the existing saved session payload.

Goal changes participate in freshness detection. A changed financial input, active goal, analysis date, or active rule version makes a new plan require rerunning. Tell the user whether inputs, the planning date, or the method changed; do not imply that every stale result means an input was edited.

Read existing v1 sessions without modifying their stored JSON or filling missing historical fields from current profile data. Show their original findings and captured inputs with a compact “Earlier analysis format” note and a run-current-analysis action. Do not fabricate historical goals, allocations, or readiness. Preserve existing history pagination and user scoping.

## Architecture and affected files

Flow: saved profile and goals → versioned financial state → orchestrator and registry → independent agent results → recommendation engine and explanations → persisted session → Dashboard/Goals/Advisor.

Expected areas:

- `backend/app/models.py`, goal request/read schemas, and one Alembic migration for persistence.
- A focused goal API module registered by `main.py`; existing analysis endpoints load goals through the service.
- `backend/app/advisory/state.py`, `types.py`, `registry.py`, `orchestrator.py`, `rules.py`, `service.py`, and `recommendations.py`.
- New Goal, Risk, and Investment agent modules alongside the existing three agents.
- `frontend/src/services/api.js`, `App.jsx`, `Dashboard.jsx`, and `AdvisorySession.jsx`; focused Goals and advisory-plan components, with related state extracted only where the growing flow needs it.
- Focused backend tests, existing frontend checks, README usage and current-completion notes.

The user learns domain modeling, reproducible financial state, independent agent contracts, orchestration, shared-budget constraints, conflict resolution, and explanations traceable to evidence.

## Verification and acceptance

- Goal arithmetic: future, due today, overdue, completed, overfunded, small fractional amounts, and 30-day boundary cases.
- Planning: unknown versus zero capacity, reserve consuming all capacity, debt review holding capacity, multiple competing goals, deterministic ordering, exact-cent conservation, and no use of existing balances as extra monthly money.
- Agent decisions: all six registered, explicit selected/skipped reasons, limited inputs, horizon caps, investment deferred by goal conflicts, and every recommendation linked to actual agent evidence.
- API/database: goal creation/edit/archive/restore, user scoping, constraints, stored goal snapshots, stale detection, and existing v1 session reads.
- Browser: enter one temporary profile and two competing goals; run analysis; identify priority and funding gap without expanding diagnostics; edit a goal and rerun; reopen the earlier result; verify archive, validation, retry, and reload behavior. Preserve the user's browser profile pointer and remove only task-created test records.
- Inspect desktop and a genuinely narrow viewport for readable goal cards, amounts, forms, keyboard controls, and error states. Report any environment limitation rather than claiming an unperformed check.
- Run focused deterministic tests, the available regression suite, and the production frontend build. No bulk demo data or synthetic dataset is needed for this milestone.

## Dependencies and boundaries

Use the installed React/FastAPI/SQLAlchemy/PostgreSQL stack and Alembic. No provider account, API key, extra framework, or model download is needed. Apply and verify the schema migration before the live goal flow.

This issue does not implement login, transaction import, actual transfers, investment-return simulation, RL training, or LLM reasoning. These boundaries keep the six-agent baseline understandable and provide a clear next milestone for authenticated user access, followed by RL environment and baseline evaluation work.
