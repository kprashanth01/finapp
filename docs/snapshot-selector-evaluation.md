# Snapshot selector evaluation

The Research screen's **How the three selectors performed** report evaluates the product's 16-feature snapshot DQN. It is separate from the 19-feature monthly DQN experiment. The question is whether a selector chooses useful financial checks for one generated planning state. It does not evaluate the advice itself or a household's later financial outcome.

## Compared methods and cases

`backend/app/rl/evaluation.py` creates 256 distinct generated states with seed `20261002`, separate from the snapshot model's training, validation, and test cases. Each method receives the same state and the same six-agent action catalogue. The rule and DQN each make one selection per case. Seeded random repeats the cohort five times, so its aggregate metrics use 1,280 selections. DQN inference is deterministic. Fingerprints identify the ordered cohort; the paired calculation refuses mismatched cases or scenario-group membership.

The **rule selector** always runs Budget, Emergency fund, Risk, and Investment readiness. It adds Debt if there is a debt balance or monthly debt payment, and Goal if there is a saved goal. This also defines which checks are needed before the app can build a complete rule-based plan.

The **DQN** receives 16 bounded features covering income/expenses, savings, debt, emergency reserve, goals, horizon, risk tolerance, and missing-input flags. During offline training it learned a choice among nonempty subsets of the six agents from the `selection-proxy-v1` reward. Each episode contains one selection. The DQN does not generate advice, move money, learn from an individual user's account, or model the effect of an action on future finances.

## Reward and measures

The reward gives **+1** for each selected relevant agent, **+2** for each selected critical agent, **−3** for each missed critical agent, **−0.75** for each selected agent that is not relevant, and **−0.15** for each selected agent call. Budget, Emergency fund, Risk, and Investment readiness are always relevant under this score; Debt becomes relevant when debt or a payment exists, and Goal when a saved goal exists. Emergency fund is critical when coverage is below three months with positive expenses; Debt is critical when debt exists and the payment-to-income ratio is at least 20% or unavailable; Goal is critical when a goal is unfinished. The cutoffs are part of this research reward, not universal financial advice.

| Report measure | Meaning |
| --- | --- |
| Average proxy score | Mean reward points per selection; random pools its five seeded runs. |
| Score variance | Population variance of selection scores; it is not a confidence interval. |
| Missed critical check | Fraction of selections missing at least one reward-defined critical agent. |
| Relevant checks covered | Selected relevant checks divided by all reward-defined relevant checks. |
| Risk check selected | Fraction selecting Risk. Risk is always relevant in this reward. |
| Goal check on unfinished goals | Fraction selecting Goal among cases with an unfinished goal. |
| Avg. agents | Mean number of agents selected, not a monetary cost. |
| Full plan possible | Fraction selecting every check required by the rule-based plan. |
| Mean execution | Local wall-clock selection and agent execution time, excluding model load; diagnostic only. |
| Average paired score difference | Mean of **DQN reward minus rule reward** on each matching case, in proxy points. Positive means DQN scored higher under this reward. |
| Average paired agent-call difference | Mean of **DQN selected-agent count minus rule count** on each matching case. Negative means DQN selected fewer agents. |
| DQN − rule score by scenario group | The same paired difference restricted to that group. Groups overlap. |

The report also counts cases where DQN and rule select the same agents, where DQN scores higher/equal/lower, and where DQN cannot build a full plan. A difference in score measures this rule-defined proxy only. The rule selector and reward share criteria, so the evaluation favors its design. The generated cohort comes from one hand-designed generator, contains no observed household outcomes or independent expert labels, and cannot establish advice quality, financial improvement, or generalization to real users. Recommendation consistency and conflicts are explicitly unmeasured.

## Reproduce

Install the optional RL dependencies described in [Research](research.md#optional-local-tools). From `backend/`, run `python -m app.rl.evaluation` with that Python environment. The command verifies the installed model, checks that the cohort is disjoint from its training/validation/test splits, and rewrites `app/rl/evaluation_report.json`. The API serves the report only when its versions, model checksum, cohort fingerprints, and metric structure match the installed artifacts. The Research screen reads that verified report and does not use account data for the evaluation.
