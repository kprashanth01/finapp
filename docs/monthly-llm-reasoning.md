# Optional monthly case narration (Issue 19)

The six deterministic agents, action catalogue, reward, conflicts, and recommendation run before the optional narrator. The narrator can turn their recorded findings into plain language. It cannot select agents, change an amount, create a plan, or assess a conflict that the case inspector left unassessed.

First generate the paired trace if needed, then inspect the default held-out user and month without a provider call:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_experiment
..\.venv\Scripts\python -m app.rl.dynamic_case_reasoning
```

The result is saved to `data/synthetic/paired-monthly-reasoning-v1.summary.json`. It contains the narrative alongside the unchanged deterministic action, selected agents, agent outputs, reward and components, recommendation, and supported constraints. The result records `source` and `fallback_reason` so you can tell whether the wording came from the optional provider or the deterministic case.

For a particular case and method, use `--synthetic-id`, `--month-index`, and `--method random|rule_based|trained_rl`. The provider is contacted **only** with `--llm` and a configured `OPENAI_API_KEY`:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_case_reasoning --synthetic-id 257 --month-index 1 --method trained_rl --llm
```

The provider receives selected agent findings, observed action and reward components, the existing recommendation summary, plan readiness, and assessed constraints. It does not receive the synthetic user's identifier or full profile. The request uses the existing Responses API configuration, `FINAPP_LLM_MODEL` (default `gpt-4o-mini`), `store: false`, and a timeout. The narrator is asked for qualitative text only. Numerical claims, investment instructions, unsupported DQN feature causes, and a claim that an unassessed partial plan has no conflicts trigger deterministic fallback. Network failure, missing configuration, or invalid output also leaves the original case facts intact.

This is an offline research command, with **no new website screen**. Run `..\.venv\Scripts\python -m pytest tests\test_dynamic_case_reasoning.py -q` from `backend/` for the provider and fallback checks. Issue 20 will define a dedicated structured, validated LLM output contract.
