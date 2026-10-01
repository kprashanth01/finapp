# Trained monthly DQN through existing agents (Issue 15)

`app.rl.dynamic_integration` loads the version-checked 19-feature monthly DQN and runs it on **synthetic test-split months**. For each month it records the financial state and encoded observation, predicts an action, maps that action through the existing 63-subset catalogue, then calls only those selected agents in `DynamicAgentSelectionEnv`. The recommendation uses their returned facts and findings; the dynamic selection reward is recorded separately. No agent output is invented from the DQN prediction.

The recommendation is **partial** when required checks are missing: it contains only priority findings from agents that actually ran and withholds a coordinated plan. When the selected agents cover the plan requirements, the existing `RecommendationEngine` builds a structured plan from those agents' returned results. “Complete” means the required agent facts were present; it does not mean the advice is validated, funded, or effective.

Each JSONL trace row records the synthetic state, observation, model name/version/checksum, action ID and mapping, selected agents' actual results, recommendation/readiness, reward components and audit, and next-month transition. The trace contains synthetic values only and is ignored by Git. The next month was generated in advance and does not change because of any selected agent or recommendation.

## Run and inspect

From the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_integration --months 3
Get-Content ..\data\synthetic\dynamic-dqn-agent-trace-v1.jsonl | Select-Object -First 1 | ConvertFrom-Json | Select-Object month_index,action,selected_agents,reward,recommendation
```

The committed model currently selects actions **22, 22, 20** for the default three-month, held-out synthetic user. These map to Budget + Debt + Emergency + Risk for the first two months, then Budget + Emergency + Risk. Their selection-proxy rewards are **3.65, 3.65, and 8.55 points**. Each month remains a partial recommendation because Investment was not selected; the trace records the actual missing checks. These numbers are one deterministic example, not an evaluation against baselines.

Use `--synthetic-id` to choose another user assigned to the test split, `--months` to change the episode length, or `--output` to choose a trace file. A train-split ID is rejected. The CLI uses the saved model's population, split, trajectory, and shock seeds. It never reads an account, profile database, or API key.

To verify the integration:

```powershell
..\.venv\Scripts\python -m pytest tests\test_dynamic_integration.py -q
```

There is **no new website screen** for this offline integration. The signed-in Advisor selector still uses the earlier 16-feature snapshot DQN. The monthly 19-feature policy must not be applied to that saved-profile input without a compatible monthly state and a separately reviewed product flow.
