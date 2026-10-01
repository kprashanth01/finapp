# Paired ablation experiments (Issue 27)

This offline runner asks which inputs and agent executions affect the project's **synthetic agent-selection behavior**. It reuses the held-out monthly cohort, the committed DQN, the Random and Rule-Based baselines, the variable-income scenario generator, and the existing reward audit. It reads no saved account or PostgreSQL data.

From `backend/` with the existing RL Python environment:

```powershell
..\.venv\Scripts\python -m app.rl.ablation_experiment
$report = Get-Content ..\data\synthetic\monthly-ablations-v1\summary.json -Raw | ConvertFrom-Json
$report.comparisons | ForEach-Object {
    [pscustomobject]@{
        Ablation = $_.ablation
        ChangedStates = $_.paired_behavior.changed_states
        ChangedDQNActions = $_.paired_behavior.methods.trained_rl.changed_actions
        DQNMeanProxyRewardChange = $_.methods.trained_rl.mean_reward_delta
    }
} | Format-Table -AutoSize
```

The default is Scenario B from [`experiments/variable-income-scenarios.json`](../experiments/variable-income-scenarios.json): 64 held-out users, 12 months each, and 768 decisions per method. One variant sets `income_volatility` to zero. Another sets `shock_probability` to zero and removes forced events. User identities, months, trajectory seed, Random seed, and all other scenario settings remain paired. Income changes can still change downstream savings, debt balances, and event eligibility. The report records changed states, observations, actions, mean proxy rewards, and agent calls.

The third ablation suppresses **Emergency** after each policy has chosen its action. It keeps that original action in `policy_action` and records the remaining `effective_agents`; an empty effective set is allowed for this offline intervention. It filters recorded findings and priority actions from the omitted agent, then recomputes the existing state-based selection proxy and critical misses. The policy is not retrained or rerun with a smaller catalogue. The intervention does not measure execution time or produce a new coordinated recommendation. The raw `agent-omission.jsonl` trace is checksum-linked to the baseline rows, with source and ablated rewards on every decision.

The default run on this machine yielded:

| Ablation | State changes / 768 | DQN action changes / 768 | DQN mean proxy reward change |
| --- | ---: | ---: | ---: |
| No income volatility | 768 | 300 | −1.976 |
| No income shocks | 548 | 61 | −0.271 |

Random reused the same seeded actions in both variants; Rule-Based kept the same selected agent set. Removing Emergency affected all 768 Rule-Based and DQN selections and 392 Random selections. The mean proxy reward changed by −5.85 for Rule-Based and DQN. Rule-Based critical misses rose from 0 to 39.9% of critical opportunities; DQN misses rose from 0.3% to 40.2%. This is expected sensitivity of a reward that explicitly values coverage of critical agents. It does **not** show that removing Emergency worsens real finances or that the DQN learned its importance. The income ablations change both policy observations and state-based reward criteria, so their score differences are not isolated effects of selection alone.

Run a subset or choose another agent:

```powershell
..\.venv\Scripts\python -m app.rl.ablation_experiment --ablations no_shocks
..\.venv\Scripts\python -m app.rl.ablation_experiment --ablations omit_agent --agent debt
```

`--scenario-config`, `--base-scenario`, `--users`, `--months`, `--trajectory-seed`, `--random-seed`, and `--output-dir` are available. Only the requested ablations are run. Generated JSONL traces, checksum manifests, and `summary.json` under `data/synthetic/monthly-ablations-v1/` are ignored by Git. Use a different `--output-dir` when retaining multiple runs.

**Without RL:** Rule-Based and seeded Random already run as independent methods on the same states. Reading those arms is the no-RL comparison; dropping the DQN arm does not alter their selections or rewards. **Without LLM:** this offline path never calls the optional LLM, so there is no LLM effect on its actions or proxy reward to measure. A future user-facing text-quality study would need a different outcome measure.

The synthetic trajectories are exogenous and no method changes a user's finances. The report measures responses under this simulator and proxy, not advice quality, household outcomes, causal effects in a population, or model retraining. Run `..\.venv\Scripts\python -m pytest tests\test_ablation_experiment.py -q` from `backend/` for focused checks. There is no new website screen, migration, package, API key, or service in this issue; inspect the generated JSON report in Codex.
