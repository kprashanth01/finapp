# Monthly DQN training (Issue 12)

The new offline DQN selects one nonempty subset of six research agents at each synthetic month. It uses the 19-feature dynamic observation and the inspectable selection proxy from Issues 10–11. The earlier 16-feature one-step DQN and its saved artifact remain separate.

## Reproduce the run

From the repository root, after installing `backend/requirements-rl.txt` into `.venv`:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_training --steps 12000 --validation-every 3000 --training-users 256 --validation-users 64 --test-users 64 --months 12 --seed 313
```

The command writes `app/rl/dynamic_model/dynamic_dqn_policy.zip` and `dynamic_dqn_metadata.json`. CLI flags also control the population, split, selected-user, trajectory, and model seeds, as well as shock probability and output directory. Inputs are generated locally; training does not read accounts or connect to the website/database.

The 12,000 synthetic users are assigned at the **user** level, 80% train and 20% test within each persona. Validation users are held out of the train cohort before sampling training users. No month from a validation or test user is used in fitting. The metadata records all seeds, counts, persona counts, and a SHA-256 digest of each selected user-ID list so the cohorts can be reconstructed and checked without embedding their full lists in the artifact.

The run fits DQN on training episodes, evaluates every checkpoint on all validation episodes, chooses the highest mean proxy reward (earliest in a tie), and evaluates that saved checkpoint once on test episodes. The validation history, chosen step, held-out test metrics, version identifiers, dependency versions, and model ZIP checksum are stored alongside the policy. The loader rejects version or checksum mismatches.

The committed run used 256 training users, 64 validation users, 64 test users, and 12 months each. Validation mean proxy reward was 5.068 at 3,000 steps, 5.140 at 6,000, 5.262 at 9,000, and 5.493 at 12,000. The selected 12,000-step checkpoint scored **5.572 mean proxy points** on 768 held-out test decisions, with a **0.000 critical-miss rate** and **3.836 mean agent calls**. These are selection-rule diagnostics on synthetic data, not financial outcomes or a comparison with baselines.

The discount is `gamma=0`: future monthly states are precomputed independently of selections. This is a monthly **contextual selection** experiment, not a learned financial transition model. Its reward is a project-defined proxy for agent coverage and call cost; a higher reward does not establish better advice, financial improvement, or superiority to another selector. Baseline comparison and broader evaluation follow in later issues.

## Inspect the result

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests\test_dynamic_scenarios.py tests\test_dynamic_training.py -q
..\.venv\Scripts\python -c "from app.rl.dynamic_training import verified_dynamic_metadata; from pprint import pprint; pprint(verified_dynamic_metadata('app/rl/dynamic_model')['test'])"
```

There is no new website screen for this offline training milestone. The existing signed-in Research page still uses the earlier one-step policy, and the monthly policy is not served to account data.
