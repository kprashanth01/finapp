# Measured research metrics (Issue 17)

The offline metric report reads the paired monthly JSONL and checks its manifest SHA-256, paired user-month keys, and matching states before calculating results. Rebuild the same 64-user, 12-month cohort and then analyze it:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_experiment
..\.venv\Scripts\python -m app.rl.dynamic_metrics
Get-Content ..\data\synthetic\paired-monthly-metrics-v1.summary.json | ConvertFrom-Json | Select-Object -ExpandProperty methods
```

The metric report is saved at `data/synthetic/paired-monthly-metrics-v1.summary.json`; the paired raw input is `data/synthetic/paired-monthly-selection-v2.jsonl`. Both are ignored by Git. The report cites the raw file checksum and cohort/trajectory digests. It contains descriptive values for Random, Rule-Based, and trained RL, each on 768 decisions.

| Requested metric | Operational definition | Availability in this cohort |
| --- | --- | --- |
| Risk Coverage | Selected critical Budget, Debt, Emergency, or Risk agent categories divided by all such state-based critical categories, pooled across user-month decisions. | Measured. These are proxy flags from the environment, not independently verified risk outcomes. |
| Goal Alignment | Unfinished goal-decision opportunities for which Goal was selected divided by all unfinished goal-decision opportunities. | Unavailable: the committed test cohort has no goal snapshots. The calculation is tested with a separate goal-bearing fixture, which is not part of the reported cohort. |
| Recommendation Consistency | Whether a coordinated recommendation is internally consistent. | Unavailable: the paired trace contains agent findings and priority actions, not a coordinated recommendation for each method. |
| Agent Efficiency | Total and mean number of agents activated per decision. | Measured. Fewer calls alone do not imply better advice. |
| Average Reward | Mean synthetic selection-proxy reward per decision. | Measured. This is the training proxy, not a financial gain. |
| Reward Variance | Population variance of reward over decisions, in squared proxy points. | Measured; decisions from a user are correlated. |
| Execution Time | Mean and median local milliseconds from policy choice through agent execution and reward. | Measured for this run. State preparation, serialization, machine load, and fixed method order limit timing comparisons. |

The report separately checks **priority-action provenance**: every priority action must match a priority finding returned by a selected agent. This checks trace structure; it is not a recommendation-consistency score. No statistical significance, policy superiority, advice quality, financial improvement, or causal effect is established by these metrics.

Run focused verification from `backend/` with `..\.venv\Scripts\python -m pytest tests\test_dynamic_metrics.py tests\test_dynamic_experiment.py -q`.

There is **no new website screen** for this offline metric report. The Research page still shows the earlier snapshot evaluation, not these monthly metrics.
