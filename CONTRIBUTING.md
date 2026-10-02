# Contributing to FinApp

Thanks for helping make FinApp easier to use and understand. Start with the [project overview](README.md), [local setup](docs/setup.md), and [codebase tour](docs/codebase-tour.md). The everyday financial planning experience is the first priority; research features should have a clear purpose and remain identifiable as experiments.

## Choose a focused change

Use a GitHub issue for a meaningful, reviewable change. Describe the user problem, expected behavior, and how someone can demonstrate it. Preserve the existing account data model, agents, rule-based plan, and research infrastructure unless a change actually requires modifying them. Make calculations and recommendation limits visible to users.

## Work locally

1. Start from the latest `main` and make a feature branch.
2. Change the smallest coherent set of code and documentation.
3. Add focused tests for financial calculations, API behavior, or important user decisions. Keep hypothetical values and experimental proxy scores clearly labelled.
4. Run the relevant checks below, inspect `git diff --check`, then open a pull request linked to the issue. Explain what changed, why it helps a user, and how to try it.

**Frontend, from `frontend/`:** `npm test` and `npm run build`.

**Backend, from `backend/`:** `../.venv/bin/python -m pytest -q` on macOS/Linux or `..\.venv\Scripts\python -m pytest -q` on Windows after installing `backend/requirements-dev.txt`.

For documentation-only changes, verify commands against the repository, check local Markdown links and headings, and run `git diff --check`. A documentation edit does not need to rerun financial or RL test suites unless it also changes executable behavior.

## Financial and research boundaries

- A savings **balance** is not a monthly savings **contribution**. Debt payments should be included in total expenses, then identified separately for ratios.
- Treat calculations, project rules, hypothetical previews, optional generated wording, and experimental scores as distinct outputs.
- Do not describe synthetic reward or DQN selection scores as proven financial benefits.
- Do not commit `.env`, account data, credentials, or generated private financial records. Use synthetic or practice values in examples and tests.
- Keep the saved Advisor plan complete and auditable. An experimental policy that omits required agents should be shown as partial.

The repository does not currently contain a separate public deployment guide or automated production hardening. Discuss changes to authentication, hosting, or use of real financial data explicitly in an issue before deployment.
