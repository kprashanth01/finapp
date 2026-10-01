"""Reproduce one held-out salaried income-drop case for the website."""

from functools import lru_cache

from app.rl.dynamic_cases import inspect_case
from app.rl.dynamic_experiment import load_committed_test_episodes, run_paired_experiment
from app.rl.dynamic_model_management import load_model
from app.rl.variable_income_experiment import build_scenario_episodes, load_scenarios


DEMO_SYNTHETIC_ID = 1034
DEMO_SCENARIO = "B"
DEMO_TRAJECTORY_SEED = 20261001


@lru_cache(maxsize=1)
def build_monthly_demo() -> dict:
    """Run both real selectors on identical, generated test months.

    This uses no account data. The chosen held-out case illustrates a real
    decision change; it is not a claim about average financial outcomes.
    """
    test_episodes, metadata = load_committed_test_episodes()
    base = next((episode for episode in test_episodes
                 if episode.profile.synthetic_id == DEMO_SYNTHETIC_ID), None)
    if base is None:
        raise ValueError("The monthly demo user is absent from the saved test cohort.")
    scenario = next((item for item in load_scenarios() if item.name == DEMO_SCENARIO), None)
    if scenario is None:
        raise ValueError("The monthly demo scenario is unavailable.")
    episode, = build_scenario_episodes((base,), scenario,
                                       months=metadata["dataset"]["months_per_user"],
                                       trajectory_seed=DEMO_TRAJECTORY_SEED)
    report = run_paired_experiment((episode,), model=load_model(),
                                   model_metadata=metadata)
    months = []
    for month_index in (1, 2):
        case = inspect_case(report["rows"], report["manifest"], (episode,),
                            synthetic_id=DEMO_SYNTHETIC_ID, month_index=month_index)
        methods = {}
        for method in ("trained_rl", "rule_based"):
            result = case["methods"][method]
            methods[method] = {
                "action": result["action"],
                "selected_agents": result["selected_agents"],
                "agent_outputs": result["agent_outputs"],
                "priority_actions": result["priority_actions"],
                "reward": result["reward"],
                "reward_components": result["reward_components"],
                "reward_audit": result["reward_audit"],
                "recommendation": result["recommendation"],
            }
        months.append({"month_index": month_index,
                       "monthly_state": case["monthly_state"],
                       "methods": methods})
    return {
        "demo_version": "monthly-dqn-website-demo-v1",
        "source": {"dataset_split": "test", "scenario": scenario.name,
                   "scenario_description": scenario.description,
                   "synthetic_id": DEMO_SYNTHETIC_ID,
                   "model_version": metadata["model_version"],
                   "artifact_sha256": metadata["artifact_sha256"],
                   "trajectory_seed": DEMO_TRAJECTORY_SEED,
                   "reward_version": report["manifest"]["reward_version"]},
        "persona": episode.profile.persona,
        "months": months,
        "limitations": [
            "This is one synthetic held-out user, not the signed-in account.",
            "The DQN selects agents; the selected specialists produce rule-based findings.",
            "The trained selection is partial when required agents are missing, so it is not a complete coordinated Advisor plan.",
            "Proxy reward measures selected checks and agent-call cost, not advice quality or financial improvement.",
            "Financial months are precomputed; selections do not alter later balances.",
            "The audit explains the proxy score and specialist findings, not the neural network's internal cause.",
        ],
    }
