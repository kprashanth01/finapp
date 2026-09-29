"""Run all three selection policies through the same registered agents and score."""

from functools import lru_cache
from typing import Literal

from app.advisory.planning_types import PlanningAgentResult
from app.advisory.explain import build_explanation
from app.advisory.recommendations import RecommendationEngine, priority_actions
from app.advisory.registry import AgentRegistry
from app.advisory.rules import RULE_VERSION
from app.advisory.state import PlanningState
from app.advisory.types import AgentSelection, OrchestratorDecision
from app.rl.baselines import BaselinePolicy, RandomBaseline, RuleBaseline
from app.rl.dqn_artifact import MODEL_VERSION, load_dqn_artifact
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import encode_observation


Mode = Literal["rule_based", "random", "rl"]


class ModelUnavailableError(Exception):
    """The trained selector cannot safely run in this server process."""


@lru_cache(maxsize=1)
def cached_dqn_model():
    try:
        return load_dqn_artifact()
    except Exception as error:
        raise ModelUnavailableError("The trained RL selector is unavailable. Install the RL runtime and check the model artifact.") from error


class DQNPolicy:
    def choose_action(self, state: PlanningState, catalog) -> int:
        try:
            action, _ = cached_dqn_model().predict(encode_observation(state), deterministic=True)
            selected = int(action)
            catalog.agents_for(selected)
            return selected
        except ModelUnavailableError:
            raise
        except (TypeError, ValueError, IndexError) as error:
            raise ModelUnavailableError("The trained RL selector returned an invalid agent action.") from error


def get_policy(mode: Mode, seed: int) -> BaselinePolicy:
    if mode == "rule_based":
        return RuleBaseline()
    if mode == "random":
        return RandomBaseline(seed=seed)
    if mode == "rl":
        return DQNPolicy()
    raise ValueError("Choose rule_based, random, or rl.")


def run_orchestration(state: PlanningState, *, mode: Mode, seed: int) -> dict:
    registry = AgentRegistry.default()
    environment = AgentSelectionEnv(state, registry=registry)
    environment.reset(seed=seed)
    action = get_policy(mode, seed).choose_action(state, environment.catalog)
    _, reward, _, _, info = environment.step(action)
    results = [PlanningAgentResult.model_validate(item) for item in info["agent_results"]]
    readiness = info["plan_readiness"]
    advice = None
    advice_model = None
    selected = set(info["selected_agents"])
    decision = OrchestratorDecision(
        method=mode, rule_version=RULE_VERSION,
        selections=[AgentSelection(
            agent_id=agent_id, selected=agent_id in selected,
            reason=("Selected" if agent_id in selected else "Not selected") + f" by {mode} policy.",
        ) for agent_id in registry.agent_ids],
    )
    if readiness["can_build_full_plan"]:
        advice_model = RecommendationEngine().build(state, decision, results)
        advice = advice_model.model_dump(mode="json")
        summary = advice["summary"]
    else:
        findings = priority_actions(results)
        first = findings[0] if findings else None
        summary = {
            "title": "Partial analysis",
            "text": ((f"Selected checks found: {first.title}. " if first else "No priority finding in the selected checks. ")
                     + "A complete monthly plan needs the missing agents listed below."),
        }
    return {
        "mode": mode,
        "policy_version": MODEL_VERSION if mode == "rl" else RULE_VERSION if mode == "rule_based" else "seeded-random-v1",
        "seed": seed if mode == "random" else None,
        "source": "saved_profile",
        "as_of_date": state.as_of_date.isoformat(),
        "state_fingerprint": state.fingerprint(),
        "state": state.model_dump(mode="json"),
        "action": int(action),
        "action_version": environment.catalog.version,
        "selected_agents": info["selected_agents"],
        "agent_results": info["agent_results"],
        "total_reward": reward,
        "reward_components": info["reward_components"],
        "reward_audit": info["reward_audit"],
        "plan_readiness": readiness,
        "summary": summary,
        "advice": advice,
        "explanation": build_explanation(state, decision, int(action), results, advice_model,
                                          seed=seed).model_dump(mode="json"),
    }
