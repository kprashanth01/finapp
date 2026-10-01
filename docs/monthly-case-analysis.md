# Inspect a paired monthly case (Issue 18)

The case inspector reads the checksum-verified Issue 17 paired trace and rebuilds the committed held-out synthetic cohort. It checks that the requested user's monthly state and goals match the trace, then shows **Random, Rule-Based, and trained RL for the same user-month**. It reuses the actual selected agents' recorded outputs to build a deterministic recommendation. It does not rerun or invent omitted agents.

Generate the paired trace if this is a fresh checkout, then inspect the first test user, month 1:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_experiment
..\.venv\Scripts\python -m app.rl.dynamic_cases
Get-Content ..\data\synthetic\paired-monthly-case-v1.summary.json | ConvertFrom-Json | Select-Object synthetic_id,month_index,methods
```

To inspect another case, pass a test-split ID and a month from 1 to 12, for example:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_cases --synthetic-id 257 --month-index 2
```

The full JSON case file at `data/synthetic/paired-monthly-case-v1.summary.json` contains:

- synthetic user profile, monthly financial state, and saved research goals;
- each method's action ID, selected agents, actual agent outputs and priority findings;
- reward, every reward component and its audit;
- a partial or coordinated recommendation built only from selected agents' results;
- explicit funding or allocation constraints when a coordinated plan exists; and
- deterministic explanations tied to action mapping, critical coverage, reward, and plan readiness.

When required agents did not run, the recommendation is **partial**, its coordinated plan is `null`, and conflicts are `not_assessed`. An empty assessed conflict list means the deterministic plan exposed no supported funding or allocation constraint; it does not prove the advice is conflict-free. The case remains synthetic and does not demonstrate financial improvement or advice quality.

The default user is **257**, month **1** in the committed cohort. In that case, Random selected Emergency and Risk, Rule-Based selected Budget, Emergency, Risk, and Investment, and trained RL selected Budget, Emergency, and Risk. Only Rule-Based had the agent coverage required to build a coordinated plan. These are one case's recorded choices, not an aggregate comparison.

From `backend/`, run `..\.venv\Scripts\python -m pytest tests\test_dynamic_cases.py -q` to verify case selection, evidence provenance, partial and complete plans, funding constraints, and checksum rejection.

There is **no new website screen** for this offline research inspector. Open the generated JSON case file in Codex to review all three methods side by side by key.
