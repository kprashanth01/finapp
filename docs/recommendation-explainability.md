# Recommendation explainability (Issue 21)

Every new Advisor explanation recommendation, including the coordinated plan summary, exposes six parts: **What**, **Why**, **Evidence**, **Agents**, **Orchestration**, and **Limitations**. These are derived from the saved trace. What is the deterministic recommendation text; Why is the recorded agent finding reason; Evidence contains the finding's metrics and relevant captured state metrics; Agents names the actual contributors; Orchestration describes the observed selection and its recorded basis; Limitations includes unavailable values, partial-plan gaps, and the project's validation boundary. A DQN explanation does not claim feature-level causes.

To see this on the website, open **Advisor**, run a selection using your saved practice profile, then open **How this result was reached**. The first recommendation appears in the four-step trail. Expand **Explore every selection, finding, and limit** to inspect the six parts for every recommendation. Previously saved sessions without a trace remain readable. This display needs no API key or new service; the local backend and frontend must be running.

The offline monthly research command also saves `recommendation_explanations` for the deterministic summary and each recorded priority action:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_case_reasoning
```

Open `data/synthetic/paired-monthly-reasoning-v3.summary.json`. Each explanation has a stable `key` (`summary` or its agent and finding code) and the same six parts. The summary lists metrics from selected agents' recorded findings. Priority-action evidence is copied from its linked finding; the command rejects a mismatched action/finding reference. Partial recommendations state which required agents did not run and that planning conflicts were not assessed. The optional LLM can reword the separate `sections` object only; it cannot change these deterministic explanations or core facts.

No database migration, package installation, provider configuration, or LLM call is needed for this issue.
