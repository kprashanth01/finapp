# Monthly DQN website demo (Issue 29)

Open the signed-in website at `http://127.0.0.1:5174/`, choose **Research**, and press **Run monthly DQN demo**. The first run loads the verified model and may take several seconds. The case is read-only and does not use or change the signed-in account. It replays held-out synthetic user 1034, persona `salaried_with_loan`, under controlled variable-income scenario B. Use the month buttons to show the state change and the two methods' outputs.

| | Month 1 | Month 2 |
| --- | ---: | ---: |
| Income, profile currency | 168,744.03 | 62,867.67 |
| Scheduled expenses | 90,235.14 | 94,111.36 |
| DQN action | 20: Budget, Emergency, Risk | 22: Budget, Debt, Emergency, Risk |
| Rule action | 54: Budget, Debt, Emergency, Risk, Investment | 54: same agents |
| DQN selection proxy | 6.55 | 11.40 |
| Rule selection proxy | 6.50 | 10.50 |

In month 2 the DQN includes Debt, and its selected agents return recorded priorities to review the emergency reserve, current debt obligations, and monthly budget. Expand **See recorded evidence** for the actual amounts and rules used by those specialists. The rule baseline returns the same three priorities while also running Investment. Both methods select all agents that the project's month-2 proxy marks critical. The DQN receives 0.90 more proxy points because it avoids one unneeded agent and one agent call.

The DQN output is **partial specialist findings**, not a complete coordinated Advisor plan: it omits Investment, which the current plan builder requires. The score measures selection coverage and call cost, not financial improvement or advice quality. This is one illustrative held-out case; it does not establish an overall advantage. The model chooses agents, while the agents' own project rules produce the displayed findings. The synthetic months are precomputed, so neither method changes later balances. The current monthly DQN is not run on the signed-in user's profile and does not record their income history. Its observation omits goal amount and deadline; the forced income-loss scenario with a goal remains a documented weakness in [the controlled experiment](variable-income-experiments.md).

This demo uses the existing RL Python dependencies and local backend. No API key, model service, or database migration is needed. The profile-linked and goal-aware monthly model belong to later issues.
