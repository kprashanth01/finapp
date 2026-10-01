# Structured monthly case reasoning (Issues 19–20)

The six deterministic agents, action catalogue, reward, conflicts, and recommendation run before the optional narrator. The narrator can turn their recorded findings into plain language. It cannot select agents, change an amount, create a plan, or assess a conflict that the case inspector left unassessed.

First generate the paired trace if needed, then inspect the default held-out user and month without a provider call:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_experiment
..\.venv\Scripts\python -m app.rl.dynamic_case_reasoning
```

The result is saved to `data/synthetic/paired-monthly-reasoning-v2.summary.json`. Its `sections` object contains `summary`, `key_findings`, `priority_actions`, `reasoning`, `agent_contributions`, and `limitations`. The existing `narrative` remains available for older readers. The report also retains the unchanged deterministic action, selected agents, agent outputs, reward and components, recommendation, and supported constraints. `source` and `fallback_reason` identify provider wording or deterministic fallback.

For a particular case and method, use `--synthetic-id`, `--month-index`, and `--method random|rule_based|trained_rl`. The provider is contacted **only** with `--llm` and a configured `OPENAI_API_KEY`:

```powershell
..\.venv\Scripts\python -m app.rl.dynamic_case_reasoning --synthetic-id 257 --month-index 1 --method trained_rl --llm
```

The provider receives selected agent findings and recorded priority actions, observed action and reward components, the existing recommendation summary, plan readiness, and assessed constraints. It does not receive the synthetic user's identifier or full profile. The request uses the existing Responses API configuration, `FINAPP_LLM_MODEL` (default `gpt-4o-mini`), `store: false`, a strict JSON schema, and a timeout. A bounded JSON code fence is accepted; arbitrary surrounding prose, malformed JSON, missing or extra fields, and invalid field types trigger deterministic fallback. Numerical claims, investment instructions, unsupported DQN feature causes, and a claim that an unassessed partial plan has no conflicts also trigger fallback. Network failure and missing configuration leave the original case facts intact.

This is an offline research command, with **no new website screen**. Run `..\.venv\Scripts\python -m pytest tests\test_dynamic_case_reasoning.py -q` from `backend/` for the provider and fallback checks. The provider is optional; the command above works without an API key.
