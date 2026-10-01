"""Run the trained monthly DQN through real registered agents and record its trace."""

import argparse
from datetime import date, timedelta
import json
import logging
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.advisory.dynamic import build_dynamic_planning_state
from app.advisory.planning_types import PlanningAgentResult
from app.advisory.recommendations import RecommendationEngine
from app.advisory.rules import RULE_VERSION
from app.advisory.types import AgentSelection, OrchestratorDecision
from app.rl.dynamic_environment import DynamicAgentSelectionEnv, DynamicEpisode
from app.rl.dynamic_model_management import get_model_metadata, load_model
from app.rl.selection import assess_plan_readiness


INTEGRATION_VERSION = "dynamic-dqn-agent-trace-v1"
DEFAULT_TRACE_PATH = (Path(__file__).resolve().parents[3] / "data" / "synthetic" /
                      "dynamic-dqn-agent-trace-v1.jsonl")
logger = logging.getLogger(__name__)


def _recommendation(episode: DynamicEpisode, position: int, environment: DynamicAgentSelectionEnv,
                    info: dict) -> dict:
    """Use only the agents actually returned by the environment for advice."""
    selected = info["selected_agents"]
    results = info["agent_results"]
    if [result["agent_id"] for result in results] != selected:
        raise ValueError("Selected agents and agent results do not match.")
    state = build_dynamic_planning_state(
        episode.profile, episode.months[position],
        as_of_date=episode.as_of_date + timedelta(days=30 * position), goals=episode.goals,
    )
    if state.fingerprint() != info["state_fingerprint"]:
        raise ValueError("Recommendation state differs from the scored month.")
    readiness = assess_plan_readiness(state, selected)
    suggestions = info["priority_actions"]
    if not readiness["can_build_full_plan"]:
        first = suggestions[0] if suggestions else None
        return {
            "status": "partial", "plan_readiness": readiness,
            "summary": {
                "title": first["title"] if first else "Partial agent review",
                "text": "Only selected agents ran; a coordinated plan needs the missing agents.",
            },
            "priority_actions": suggestions,
            "coordinated_plan": None,
        }
    decision = OrchestratorDecision(
        method="rl", rule_version=RULE_VERSION,
        selections=[AgentSelection(
            agent_id=agent_id, selected=agent_id in selected,
            reason="Selected by the trained monthly DQN." if agent_id in selected else
                   "Not selected by the trained monthly DQN.",
        ) for agent_id in environment.registry.agent_ids],
    )
    advice = RecommendationEngine().build(
        state, decision, [PlanningAgentResult.model_validate(result) for result in results],
    )
    return {
        "status": "complete", "plan_readiness": readiness,
        "summary": advice.summary.model_dump(mode="json"),
        "priority_actions": suggestions,
        "coordinated_plan": advice.model_dump(mode="json"),
    }


def _write_trace(path: Path, steps: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{uuid4().hex}.pending")
    try:
        pending.write_text("".join(json.dumps(step, sort_keys=True, allow_nan=False) + "\n"
                                   for step in steps), encoding="utf-8")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def run_trained_dynamic_episode(episode: DynamicEpisode, *, model=None,
                                trace_path: Path | None = None) -> dict:
    """Run one synthetic user's months; a supplied model is for controlled research checks."""
    metadata = None
    if model is None:
        metadata = get_model_metadata()
        model = load_model()
        if get_model_metadata()["artifact_sha256"] != metadata["artifact_sha256"]:
            raise ValueError("Monthly model artifact changed while preparing the trace.")
        policy = {"source": "versioned_artifact", "model_name": metadata["model_name"],
                  "model_version": metadata["model_version"],
                  "artifact_sha256": metadata["artifact_sha256"],
                  "action_version": metadata["action_version"],
                  "observation_version": metadata["observation_version"]}
    else:
        policy = {"source": "supplied_policy", "model_name": None,
                  "model_version": None, "artifact_sha256": None,
                  "action_version": None, "observation_version": None}
    environment = DynamicAgentSelectionEnv(episode)
    if metadata is not None and environment.catalog.version != metadata["action_version"]:
        raise ValueError("Monthly action catalogue differs from the saved policy.")
    observation, _ = environment.reset(options={"episode_index": 0})
    steps = []
    try:
        for position in range(len(episode.months)):
            current_observation = observation.tolist()
            action, _ = model.predict(observation, deterministic=True)
            raw_action = np.asarray(action)
            if (raw_action.ndim != 0 or not np.issubdtype(raw_action.dtype, np.integer)
                    or isinstance(action, bool)):
                raise ValueError("Action predicted by the monthly policy must be a discrete integer.")
            observation, reward, terminated, truncated, info = environment.step(int(raw_action))
            if truncated or terminated != (position == len(episode.months) - 1):
                raise ValueError("Unexpected termination in the monthly episode.")
            recommendation = _recommendation(episode, position, environment, info)
            row = {
                "trace_version": INTEGRATION_VERSION, "policy": policy,
                "synthetic_id": info["synthetic_id"], "dataset_split": info["dataset_split"],
                "month_index": info["month_index"], "state_fingerprint": info["state_fingerprint"],
                "financial_state": episode.months[position].model_dump(mode="json"),
                "observation_version": info["observation_version"],
                "observation": current_observation,
                "action": info["action"], "action_version": info["action_version"],
                "selected_agents": info["selected_agents"], "agent_results": info["agent_results"],
                "recommendation": recommendation,
                "reward": reward, "reward_version": info["reward_version"],
                "reward_components": info["reward_components"], "reward_audit": info["reward_audit"],
                "transition_source": info["transition_source"],
                "next_month_index": info["next_month_index"], "terminated": terminated,
            }
            steps.append(json.loads(json.dumps(row, allow_nan=False)))
            logger.info("Synthetic user %s month %s selected action %s; reward %.3f",
                        info["synthetic_id"], info["month_index"], info["action"], reward)
    finally:
        environment.close()
    if trace_path is not None:
        _write_trace(trace_path, steps)
    return {
        "trace_version": INTEGRATION_VERSION, "policy": policy,
        "episode": {"synthetic_id": episode.profile.synthetic_id,
                    "dataset_split": episode.profile.dataset_split,
                    "month_count": len(episode.months)},
        "steps": steps, "total_reward": round(sum(step["reward"] for step in steps), 3),
        "trace_path": str(Path(trace_path).resolve()) if trace_path is not None else None,
    }


def main() -> None:
    """Inspect one held-out synthetic user with the committed monthly model."""
    from app.rl.dynamic_state import build_dynamic_financial_state
    from app.rl.population import generate_population
    from app.rl.splits import assign_user_splits
    from app.rl.trajectories import ShockConfig, generate_trajectory

    parser = argparse.ArgumentParser(description="Trace the trained monthly DQN through existing agents.")
    parser.add_argument("--synthetic-id", type=int, help="A user from the synthetic test split")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_TRACE_PATH)
    args = parser.parse_args()
    metadata = get_model_metadata()
    dataset = metadata["dataset"]
    seeds = dataset["seeds"]
    profiles = assign_user_splits(generate_population(seed=seeds["population"]), seed=seeds["split"])
    profile = next((item for item in profiles if item.dataset_split == "test" and
                    (args.synthetic_id is None or item.synthetic_id == args.synthetic_id)), None)
    if profile is None:
        parser.error("synthetic-id must belong to the generated test split")
    months = generate_trajectory(profile, months=args.months, seed=seeds["trajectory"],
                                 shock_config=ShockConfig(probability=dataset["shock_probability"]))
    episode = DynamicEpisode(
        profile, tuple(build_dynamic_financial_state(profile, month) for month in months),
        date(2026, 10, 1),
    )
    report = run_trained_dynamic_episode(episode, trace_path=args.output)
    print(json.dumps({
        "trace_version": report["trace_version"], "policy": report["policy"],
        "synthetic_id": profile.synthetic_id, "dataset_split": profile.dataset_split,
        "actions": [step["action"] for step in report["steps"]],
        "selected_agents": [step["selected_agents"] for step in report["steps"]],
        "recommendation_status": [step["recommendation"]["status"] for step in report["steps"]],
        "rewards": [step["reward"] for step in report["steps"]],
        "total_reward": report["total_reward"], "trace_path": report["trace_path"],
        "note": "Synthetic selection proxy; no account data or simulated advice uptake.",
    }, indent=2))


if __name__ == "__main__":
    main()
