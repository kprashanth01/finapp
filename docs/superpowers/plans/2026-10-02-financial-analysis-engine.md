# Issue 3 implementation plan

1. Build a pure, versioned financial picture from current Profile, optional detail, active Goals, and recorded Months. Keep every missing value explicit and attach source/status/limitation to each metric.
2. Extend `GET /users/{user_id}/financial-analysis` without removing its existing five fields. Query only account-owned rows. Keep saved Advisor snapshots and research contracts unchanged.
3. Show a concise summary on Dashboard, with expandable facts and their sources. Refresh the picture after optional detail, goal, and recorded-month edits.
4. Verify complete and incomplete financial cases, account scoping, legacy analysis values, frontend rendering, and the production build. Describe limitations in the user guide.
