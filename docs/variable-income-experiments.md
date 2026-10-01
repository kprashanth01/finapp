# Controlled variable-income experiments (Issue 25)

This offline experiment asks whether agent-selection methods respond when the **underlying synthetic financial state changes**. It reuses the committed monthly DQN, the Random and Rule-Based policies, the 63-action agent catalogue, the monthly simulator, and the paired experiment runner. It reads no saved account or PostgreSQL data.

## Run and inspect

From `backend/` with the existing RL Python environment:

```powershell
..\.venv\Scripts\python -m app.rl.variable_income_experiment
$result = Get-Content ..\data\synthetic\variable-income-experiment-v1\summary.json -Raw | ConvertFrom-Json
$result.scenarios | ForEach-Object {
    [pscustomobject]@{
        Scenario = $_.scenario.name
        ChangedStates = $_.behavior_vs_first_scenario.changed_states
        ChangedRuleActions = $_.behavior_vs_first_scenario.methods.rule_based.changed_actions
        ChangedDQNActions = $_.behavior_vs_first_scenario.methods.trained_rl.changed_actions
        RuleMeanProxyReward = $_.metrics.rule_based.average_reward
        DQNMeanProxyReward = $_.metrics.trained_rl.average_reward
    }
} | Format-Table -AutoSize
```

The default run uses all 64 users from the committed DQN's held-out test split, 12 months per user, and five scenarios. Every method makes 768 decisions in each scenario. It writes one raw JSONL trace and its checksum manifest per scenario, plus `summary.json` with the input settings, measured metrics, event counts, action distributions, and paired action-change counts. The summary gives the source model checksum, user-cohort digest, simulator seed, Random seed, and relevant schema versions. Timings and raw-file digests can vary by run. Generated files are ignored by Git.

The editable scenario matrix is [`experiments/variable-income-scenarios.json`](../experiments/variable-income-scenarios.json). Copy it and pass `--config <path>` to make a custom run. `--users`, `--months`, `--trajectory-seed`, `--random-seed`, and `--output-dir` are also available. Keep scenario names unique. The first listed scenario is the reference for action-change rates. All settings are validated before any output is written.

| Setting | Meaning |
| --- | --- |
| `income_volatility` | Relative standard deviation of monthly income, 0–1. |
| `shock_probability`, `shock_magnitude` | Chance and fractional size of random simulator events. |
| `forced_events` | `[month, event]` pairs for a guaranteed event. A temporary income loss lasts two months by default. |
| `debt_to_annual_income` | Initial debt principal divided by annual base income. |
| `emi_to_monthly_income` | Scheduled monthly debt payment divided by base monthly income. |
| `expenses_to_monthly_income` | Total scheduled expenses, including EMI, divided by base monthly income. |
| `emergency_fund_months` | Initial earmarked reserve divided by scheduled monthly expenses. |
| `risk_tolerance`, `investment_horizon_years` | Policy and agent inputs. |
| `goal_amount`, `goal_horizon_months` | Optional synthetic goal; both fields must be present together. |

The simulator fixes the non-EMI expense split at 65% fixed and 35% variable, uses an illustrative 8% APR for one synthetic debt, and starts total liquid savings equal to the emergency reserve. These assumptions reconcile the generated profiles; they are not household estimates. Scenario A has stable income, low debt and six months of emergency reserve. B has volatile income, moderate debt and little reserve. C schedules temporary income loss in month 2 with high EMI and a three-month goal. D schedules a high-income month with existing debt, strong reserve and a long investment horizon. E schedules a low-income month with high expenses and an upcoming EMI.

All scenarios use the same held-out user identities and underlying trajectory seed. Each method sees the same state within a scenario. The Random policy restarts with the same seed for every scenario, so its unchanged actions are a negative control. `changed_states` and `changed_observations` confirm the scenario actually changed inputs; `changed_actions` counts policy choices that differ from the first scenario on the same user and month. The per-scenario metrics include synthetic mean selection-proxy reward, coverage, call count, timing and reward variance. The experiment does **not** infer that a higher proxy score produces better finances.

For the default settings on this machine, the reference A gave mean proxy rewards of 4.25 for Rule-Based and 3.40 for DQN. Compared with A, DQN changed all 768 actions in each of B–E. Rule-Based changed zero actions in B and E and all 768 in C and D. Random changed zero actions, as expected. The action distributions show that DQN chose one action for every decision in A, C, D, and E; it used three actions in B. The rule policy used one action throughout each scenario. Thus the between-scenario action changes do not establish nuanced within-scenario adaptation. These counts show response to a multi-input scenario change, not which individual input caused it. Re-run the command to inspect the current artifacts and exact scores.

The monthly financial trajectories are precomputed and independent of selections. Scenario settings are synthetic and not calibrated to household data. The saved DQN's 19-feature observation includes investment horizon but omits goal amount and goal deadline, so this run cannot test its response to those two goal inputs. The reward is a project-defined selection proxy, not financial improvement. Decision months from one user are correlated; descriptive values are not a significance test. No website screen was added: the existing Research dashboard still displays the earlier fixed-cohort evaluation. This experiment is inspected through its summary and trace files.
