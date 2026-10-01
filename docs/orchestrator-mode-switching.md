# Configured Advisor selector (Issue 14)

Set `ORCHESTRATOR_MODE` in the repository root `.env` and restart the backend to choose the server default for **Advisor → Choose how agents are selected → Server default**:

```env
ORCHESTRATOR_MODE=rule_based
```

Allowed values are `rule_based`, `random`, and `trained_rl`. If unset, the default is `rule_based`. Server-default random uses seed 42; choose **Seeded random** explicitly to change its seed. `trained_rl` uses the committed **snapshot** DQN for saved-profile observations, with its existing process-level model cache. A missing or incompatible model returns an unavailable error; it does not silently fall back to another selector. An invalid setting also returns a clear configuration error for server-default runs.

The selector appears on **Advisor**, though its read-only API route is under `/research/orchestration-run`. That route accepts a request without `mode` to use this setting. A request with an explicit mode still runs that method, which keeps comparisons reproducible regardless of server configuration. The earlier explicit API value `rl` remains accepted for existing clients; new configuration and the website use `trained_rl`. Responses name the actual selected mode, action, agent results, readiness, score components, and explanation. All three modes use the same registered agents and action catalogue after selecting an action.

The saved **Advisor** session remains a complete, rule-based plan and continues to be stored in history. Experimental selector runs on the same page remain read-only and may show partial findings when fewer agents run. The separate **Research → Try your own agent selection** panel is for manually ticking agents; it does not use this setting. The newly trained **monthly** DQN is still offline; its 19-feature input is not substituted for the saved profile's 16-feature snapshot. Later dynamic integration work will address that separate inference path.

## Check it on the website

1. Restart the backend after editing `.env`, then open the running FinApp and sign in.
2. Open **Advisor**, scroll below the saved plan to **Choose how agents are selected**, and leave **Server default** selected.
3. Click **Run selected method**. The result header shows the mode actually used. Choose **Rule based**, **Seeded random**, or **Trained RL** explicitly to compare them without editing configuration.

The configured mode does not modify a saved profile or create an Advisor session. To check the backend directly, run from `backend/`:

```powershell
..\.venv\Scripts\python -m pytest tests\test_orchestration.py tests\test_advisory_api.py -q
```
