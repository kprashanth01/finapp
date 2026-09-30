# Multi-month Gymnasium environment (Issue 11)

`DynamicAgentSelectionEnv` is a separate research environment for repeated selections along **one synthetic user's ordered months**. The existing one-step `AgentSelectionEnv`, saved Advisor API, and committed DQN remain unchanged.

## Episode contract

`DynamicEpisode` holds one `SyntheticProfile`, consecutive `DynamicFinancialState` months, a start date, and optional fixed example goals. It rejects mismatched user identity or dataset split and skipped or reversed months. An environment can sample multiple episodes with a seeded `reset()`, but it rejects a mixture of train and test users. Keep users' whole trajectories in their assigned split when constructing training and evaluation environments.

| Gymnasium part | Meaning |
| --- | --- |
| `observation_space` | 19 `float32` features in `[-1, 1]`, encoded by `dynamic-observation-v1`; split, persona, and hidden event label are excluded |
| `action_space` | Discrete IDs from the existing versioned catalogue; the default has 63 nonempty subsets of six agents |
| `reset(seed, options)` | Select an episode reproducibly and return its first month; `options={"episode_index": i}` inspects a particular episode |
| `step(action)` | Analyze the current month with **only** the selected registered agents; return their structured results and actual priority findings, `dynamic-selection-proxy-v1` reward components and checks, then move to the next generated month |
| Termination | One step per month. The last step returns `terminated=True`, `truncated=False`, and the last month's observation as the terminal observation; another step requires `reset()` |

The `info` dictionary reports synthetic user/month identity, selected action and agents, action/observation/reward versions, agent results, priority actions, reward components and audit, the current state's fingerprint, and the next month index. `priority_actions` contains only priority findings actually returned by selected agents; it is **not** a complete coordinated financial plan. An empty list is a legitimate result.

Every next month comes from the **precomputed exogenous trajectory**, independently of the selected agents or their findings. The `transition_source` field names this rule. The environment therefore supports temporal selection experiments and comparisons across volatile months, but it does not simulate advice uptake, alter balances, measure resulting financial health, or prove a causal benefit from sequencing. Those would require a separately specified behavior/transition model and outcome validation.

## Run the episode

From the repository root in PowerShell:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_environment --synthetic-id 1 --months 3 --seed 4 --shocks --shock-probability 0.5 --selected budget investment
```

This seed currently produces the following trace. These are **project reward points**, not money or observed financial improvement.

| Month | Income | Scheduled cash flow | Reward | Next month | Priority findings from selected agents |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 90778.08 | 32515.60 | −3.05 | 2 | None |
| 2 | 83643.31 | 18447.35 | −6.05 | 3 | None |
| 3 | 44470.22 | −15063.68 | −7.05 | End | Budget review |

The CLI prints each step's actual `reward_components`, selection, priority actions, and termination. Running the same command again produces identical JSON. `--income-volatility` overrides configured volatility and `--shock-probability` changes event frequency. No PostgreSQL connection, account, API key, migration, external model, or new package is required beyond the existing backend environment.

There is no new website screen in Issue 11. The [dynamic reward notes](dynamic-reward.md) explain the proxy's weights. Issue 12 can use this environment to train and evaluate a **new**, version-compatible DQN; the old 16-feature model cannot be applied to this 19-feature environment.
