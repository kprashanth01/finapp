# Research area and experiments

FinApp's everyday planning flow uses deterministic financial checks and a rule-based coordinator. The Research area asks a narrower question: **can a learned policy choose a useful set of financial agents when a situation changes?** It does not measure whether following a recommendation improved anyone's actual finances.

## Keep the product and research paths distinct

| Path | Input | Output | Where it appears |
| --- | --- | --- | --- |
| **Saved rule-based plan** | Your saved profile and goals | Complete coordinated plan and reasons, saved to your account | Dashboard and Advisor |
| **Product comparison on an account** | One current saved profile and its details | Standard and trained selectors side by side; first step only when required checks ran | Advisor → Compare planning approaches |
| **Detailed experimental selection** | Your saved profile or entered monthly record | Agents selected by a rule, seeded random draw, or trained DQN; findings and a plan only if all required checks ran | Advisor's research section and Research |
| **Offline synthetic evaluation** | Generated profiles and month sequences, not account data | Proxy rewards, coverage, traces, model comparisons | Research reports and files under `data/` and `backend/app/rl/` |

The six agents remain the financial checks in each path. Agent selection and financial allocation are different operations: a DQN action selects agents to run; it does not transfer savings or cause the next synthetic month to improve. When an experimental selection misses a required check, the app reports a partial result rather than presenting a complete plan. Advisor's product comparison reads the same current snapshot for both methods and does not update the saved rule-based session.

## Two model generations

The repository contains an earlier **snapshot selector** with a 16-feature observation and a separate **monthly DQN** with a 19-feature observation for generated changing-income episodes. Both use an explicit subset mapping over the six agents. The model artifacts and metadata are committed in `backend/app/rl/`. Research screens and guides identify which model and dataset a result uses. Do not treat the two observations, rewards, or report cohorts as interchangeable.

The reported reward is a **project-defined selection proxy**: it scores coverage of relevant checks and costs of unnecessary selections in synthetic situations. Synthetic next-month finances are generated independently of the agent action. A higher reward is not a claim of improved wealth, goal completion, investment return, or validated personal advice.

## Optional local tools

The [normal setup](setup.md) installs the application without PyTorch. To execute a trained DQN mode or reproduce DQN experiments, install the additional requirements into the same Python environment that starts the API:

**Windows PowerShell, from the repository root**

```powershell
.\.venv\Scripts\python -m pip install -r backend\requirements-rl.txt
```

**macOS/Linux, from the repository root**

```sh
./.venv/bin/python -m pip install -r backend/requirements-rl.txt
```

These requirements include PyTorch and Stable-Baselines3 and are much larger than the base install. Python 3.12 is recommended for this optional environment on Windows. Start the base app first; the training and evaluation scripts are separate work.

Optional explanation features have different dependencies:

- **Generate explanation** can use OpenAI when `OPENAI_API_KEY` is set in the root `.env`. It sends selected financial evidence to the provider only on request. `FINAPP_LLM_MODEL` can override the configured model.
- **Local Advisor chat** uses Ollama if installed and running. The default model is `qwen3.5:4b`; run `ollama pull qwen3.5:4b` after installing Ollama, or configure `FINAPP_CHAT_MODEL`. The app has deterministic fallback behavior when the local model is unavailable.

Neither model is required to create an account or run the saved rule-based plan.

## Find the right experiment guide

| Interest | Read |
| --- | --- |
| The original rule/random/DQN evaluation, cohort, and metric definitions | [Paired monthly experiment](paired-monthly-experiment.md), [Research metrics](research-metrics.md) |
| How a particular synthetic case was handled | [Monthly case analysis](monthly-case-analysis.md), [Recommendation explainability](recommendation-explainability.md) |
| Variable-income shocks and competing priorities | [Variable-income experiments](variable-income-experiments.md), [Conflict scenarios](conflict-scenarios.md) |
| What happens when observations or agents are removed | [Ablation experiments](ablation-experiments.md) |
| Monthly DQN state, training, model storage, and integration | [Dynamic DQN training](dynamic-dqn-training.md), [Model management](rl-model-management.md), [Agent integration](dynamic-dqn-agent-integration.md) |
| Reward, environment, and reasoning contracts | [Dynamic reward](dynamic-reward.md), [Dynamic environment](dynamic-environment.md), [Monthly LLM reasoning](monthly-llm-reasoning.md) |
| Browser demonstrations and entering your own months | [Monthly DQN website demo](monthly-dqn-website-demo.md), [Account month walkthrough](account-monthly-advice.md) |

The [detailed implementation reference](implementation-reference.md#research-comparison-and-rl-foundation) preserves milestone-by-milestone explanations and reproduction commands from the earlier README. It is background detail; start with the current app and the focused guide for the experiment you want to inspect.
