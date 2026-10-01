# Inspect agent-priority conflicts (Issue 26)

This offline experiment records three **reachable** competitions for one synthetic month's capacity. It uses the committed held-out user 257, the editable settings in [`experiments/conflict-scenarios.json`](../experiments/conflict-scenarios.json), the real six agents, the paired Random/Rule-Based/monthly DQN selector, and the existing deterministic recommendation coordinator. It does not read saved accounts.

From `backend/` with the existing RL Python environment:

```powershell
..\.venv\Scripts\python -m app.rl.conflict_experiment
$report = Get-Content ..\data\synthetic\conflict-scenarios-v1\summary.json -Raw | ConvertFrom-Json
$report.cases | ForEach-Object {
    [pscustomobject]@{
        Case = $_.scenario.name
        Conflict = $_.scenario.expected_conflict
        Rule = $_.methods.rule_based.reference_conflict_outcomes[0].resolution.mechanism
        DQN = $_.methods.trained_rl.reference_conflict_outcomes[0].status
        DQNMissing = $_.methods.trained_rl.reference_conflict_outcomes[0].missing_agents -join ', '
    }
} | Format-Table -AutoSize
```

The command writes `summary.json` and a checksum-verified raw JSONL trace plus manifest for each case. Output files under `data/synthetic/conflict-scenarios-v1/` are ignored by Git. Copy the scenario JSON and pass `--config <path>` to change values; the runner rejects a case if its named conflict is not observed or its rule-policy resolution cannot be verified. You may also pass a test-split `--synthetic-id`, but the default amounts were designed for user 257 and may need adjustment for a different user. `--trajectory-seed`, `--random-seed`, and `--output-dir` are available.

| Case | Agent evidence | Recorded rule-policy outcome |
| --- | --- | --- |
| `reserve_goal` | Emergency reports a reserve gap; Goal requires more funding than remains after that gap. | The coordinator assigns available capacity to the reserve first and records an underfunded goal. |
| `debt_goal` | Debt requests review of a high EMI while Goal records a monthly requirement. | The coordinator holds remaining capacity for debt review and records no goal allocation. |
| `investment_goal` | Investment reports `ready_to_consider`, while Goal's monthly requirement exceeds current capacity. | The coordinator funds the goal up to available capacity and defers investment because the goal remains underfunded. |

For each method, `agent_proposals` contains only findings and structured facts from agents that method **actually selected**. `reference_conflicts` comes from the full Rule-Based selection on the same state and identifies the designed competition. `observed_conflicts` contains only what the method's own selected agents exposed. `reference_conflict_outcomes` says `not_observed` and lists missing agents when a method omitted evidence. The result also records the action ID, selected agents, priority actions, complete or partial recommendation, reward and components. A `resolved_by_coordinator` outcome is backed by the recorded allocation, hold, or investment status; it is not an inference from a score.

In the committed DQN run, Rule-Based selected all six agents and resolved each conflict through the existing coordinator. DQN omitted the Goal Agent in all three cases, so its recommendations were partial and no conflict was marked resolved. The seeded Random control selected Emergency and Risk only. This is a finding about these synthetic cases, not proof that either policy is generally better. The DQN **selects agents**; it does not learn a separate recommendation-conflict solver. The deterministic coordinator builds a full recommendation only after all required agents have run.

The example in which Investment says “ready” while Debt says payments are too high and Emergency says the reserve is inadequate cannot be generated from consistent current inputs: the Investment Agent checks those same debt and reserve conditions and would defer. The `investment_goal` case gives a real alternative: Investment's own readiness check passes, then the coordinator finds an underfunded goal and defers investment. Conflict labels here cover three designed competitions, not all possible disagreements. Financial states are synthetic and exogenous; reward measures agent-selection coverage, not financial improvement or advice quality.

Run `..\.venv\Scripts\python -m pytest tests\test_conflict_experiment.py tests\test_dynamic_cases.py -q` from `backend/` for the focused checks. This issue adds no website screen, migration, package, API key, or service. The Research page continues to show the earlier fixed-cohort evaluation; open the generated JSON report in Codex to inspect the case evidence.
