# Paired monthly selection experiment (Issue 16)

`app.rl.dynamic_experiment` compares the existing seeded Random and Rule-Based baselines with the committed 19-feature monthly DQN. Each method gets its own environment instance, but all three instances reset to the same synthetic test user and advance through the same precomputed monthly states. The runner checks their observations and state fingerprints on every decision. Agent selections pass through the same action catalogue, registered agents, and selection reward. The v2 trace adds recorded goals and elapsed time for policy selection plus agent execution; it does not change the held-out cohort.

The default cohort is rebuilt from the DQN artifact metadata: **64 held-out test users, 12 months each**. The runner rejects any mismatch between the rebuilt dataset summary and the committed metadata. No training or validation user is evaluated. Random uses seed `313`; the Rule-Based policy uses `RuleBaseline`, and the trained DQN predicts deterministically. Each method makes **768 decisions**, giving **2,304 paired raw rows**.

From the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_experiment
Get-Content ..\data\synthetic\paired-monthly-selection-v2.summary.json | ConvertFrom-Json | Select-Object user_count,decision_count_per_method,user_id_sha256,trajectory_sha256,raw_rows_sha256
Get-Content ..\data\synthetic\paired-monthly-selection-v2.jsonl | Select-Object -First 3 | ConvertFrom-Json | Select-Object method,synthetic_id,month_index,action,selected_agents,reward,execution_time_ns
```

Use `--output` for another JSONL location and `--random-seed` to repeat the Random baseline with a different documented seed. The companion `.summary.json` manifest stores model checksum, dataset seeds and counts, action/observation/reward/environment versions, cohort and trajectory digests, and a SHA-256 of the raw JSONL. Raw rows include the synthetic state, observation, goals, action, selected agents and their actual findings, reward components and audit, agent call count, measured elapsed time, and transition. Timings vary by run, so the raw-file checksum also varies. Output files under `data/synthetic/` are ignored by Git.

The three methods share the same exogenous months; selecting agents does not alter the next financial state. Reward is a **synthetic selection proxy**, not a financial outcome or advice quality measure. This framework collects paired evidence. The named research metrics and interpretation are the next issue; no superiority claim follows from row counts or this setup alone.

Run the focused checks with `..\.venv\Scripts\python -m pytest tests\test_dynamic_experiment.py -q` from `backend/`. There is **no new website screen** for this offline experiment. The Research page still displays the earlier snapshot evaluation; it does not present these monthly paired results.
