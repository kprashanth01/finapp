"""Paired, held-out monthly selection experiment for three policies."""

import argparse
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.advisory.dynamic import build_dynamic_planning_state
from app.rl.baselines import RandomBaseline, RuleBaseline
from app.rl.dynamic_environment import (DYNAMIC_ENVIRONMENT_VERSION,
                                        DynamicAgentSelectionEnv, DynamicEpisode)
from app.rl.dynamic_model_management import get_model_metadata, load_model
from app.rl.dynamic_scenarios import build_dynamic_episode_splits
from app.rl.dynamic_reward import DYNAMIC_REWARD_VERSION
from app.rl.dynamic_state import DYNAMIC_OBSERVATION_VERSION
from app.rl.selection import ACTION_VERSION


EXPERIMENT_VERSION = "paired-monthly-selection-v1"
METHODS = ("random", "rule_based", "trained_rl")
DEFAULT_OUTPUT = (Path(__file__).resolve().parents[3] / "data" / "synthetic" /
                  "paired-monthly-selection-v1.jsonl")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _action(value, count: int) -> int:
    raw = np.asarray(value)
    if (isinstance(value, bool) or raw.ndim != 0 or
            not np.issubdtype(raw.dtype, np.integer) or not 0 <= int(raw) < count):
        raise ValueError("Policy action must be a discrete integer in the action catalogue.")
    return int(raw)


def run_paired_experiment(episodes: tuple[DynamicEpisode, ...], *, model,
                          random_seed: int = 313, model_metadata: dict | None = None) -> dict:
    """Evaluate every policy on each identical test month through the same environment.

    Months are generated before this call. Actions cannot alter their financial
    states; the reward measures selection coverage and cost, not improvement.
    """
    episodes = tuple(episodes)
    if not episodes or any(not isinstance(item, DynamicEpisode) or
                           item.profile.dataset_split != "test" for item in episodes):
        raise ValueError("The paired experiment requires test-split episodes only.")
    ids = [item.profile.synthetic_id for item in episodes]
    if len(set(ids)) != len(ids):
        raise ValueError("The experiment contains a duplicate synthetic user.")
    if isinstance(random_seed, bool) or not isinstance(random_seed, int) or random_seed < 0:
        raise ValueError("random_seed must be a nonnegative integer.")
    random_policy = RandomBaseline(seed=random_seed)
    rule_policy = RuleBaseline()
    rows = []
    trajectory = []
    environments = {method: DynamicAgentSelectionEnv(episodes) for method in METHODS}
    try:
        if any(env.catalog.version != ACTION_VERSION for env in environments.values()):
            raise ValueError("The experiment must use the committed monthly action catalogue.")
        for episode_index, episode in enumerate(episodes):
            observations = {method: env.reset(options={"episode_index": episode_index})[0]
                            for method, env in environments.items()}
            for position, month in enumerate(episode.months):
                values = [value.tolist() for value in observations.values()]
                if any(value != values[0] for value in values[1:]):
                    raise ValueError("Methods received different monthly observations.")
                state = build_dynamic_planning_state(
                    episode.profile, month,
                    as_of_date=episode.as_of_date + timedelta(days=30 * position),
                    goals=episode.goals,
                )
                financial_state = month.model_dump(mode="json")
                trajectory.append({"synthetic_id": episode.profile.synthetic_id,
                                   "month_index": month.month_index,
                                   "financial_state": financial_state,
                                   "state_fingerprint": state.fingerprint(),
                                   "observation": values[0]})
                for method, env in environments.items():
                    observation = observations[method]
                    if method == "random":
                        proposed = random_policy.choose_action(state, env.catalog)
                    elif method == "rule_based":
                        proposed = rule_policy.choose_action(state, env.catalog)
                    else:
                        proposed, _ = model.predict(observation, deterministic=True)
                    action = _action(proposed, env.catalog.action_count)
                    next_observation, reward, terminated, truncated, info = env.step(action)
                    if (info["synthetic_id"] != episode.profile.synthetic_id or
                            info["month_index"] != month.month_index or
                            info["state_fingerprint"] != state.fingerprint() or
                            truncated or terminated != (position == len(episode.months) - 1)):
                        raise ValueError("Methods did not run the same test user and month.")
                    row = {
                        "experiment_version": EXPERIMENT_VERSION,
                        "method": method, "synthetic_id": info["synthetic_id"],
                        "dataset_split": info["dataset_split"],
                        "persona": episode.profile.persona,
                        "month_index": info["month_index"],
                        "state_fingerprint": info["state_fingerprint"],
                        "financial_state": financial_state,
                        "observation_version": info["observation_version"],
                        "observation": values[0],
                        "action_version": info["action_version"],
                        "action": action, "selected_agents": info["selected_agents"],
                        "agent_results": info["agent_results"],
                        "priority_actions": info["priority_actions"],
                        "agent_call_count": len(info["selected_agents"]),
                        "reward_version": info["reward_version"],
                        "reward": reward, "reward_components": info["reward_components"],
                        "reward_audit": info["reward_audit"],
                        "transition_source": info["transition_source"],
                        "next_month_index": info["next_month_index"],
                        "terminated": terminated,
                    }
                    rows.append(json.loads(_json(row)))
                    observations[method] = next_observation
    finally:
        for env in environments.values():
            env.close()
    user_ids = ",".join(str(value) for value in ids)
    manifest = {
        "experiment_version": EXPERIMENT_VERSION,
        "methods": list(METHODS), "dataset_split": "test",
        "user_count": len(episodes), "decision_count_per_method": len(trajectory),
        "row_count": len(rows), "random_seed": random_seed,
        "user_id_sha256": sha256(user_ids.encode("ascii")).hexdigest(),
        "trajectory_sha256": sha256(_json(trajectory).encode("utf-8")).hexdigest(),
        "action_version": ACTION_VERSION,
        "observation_version": DYNAMIC_OBSERVATION_VERSION,
        "reward_version": DYNAMIC_REWARD_VERSION,
        "environment_version": DYNAMIC_ENVIRONMENT_VERSION,
        "raw_rows_sha256": sha256("".join(_json(row) + "\n" for row in rows).encode("utf-8")).hexdigest(),
        "model": ({"source": "versioned_artifact", "model_name": model_metadata["model_name"],
                   "model_version": model_metadata["model_version"],
                   "artifact_sha256": model_metadata["artifact_sha256"]}
                  if model_metadata is not None else {"source": "supplied_policy"}),
        "dataset": model_metadata["dataset"] if model_metadata is not None else None,
        "note": "Synthetic monthly selection proxy; trajectories are exogenous and no advice uptake is simulated.",
    }
    return {"manifest": manifest, "rows": rows}


def _write_atomic(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{uuid4().hex}.pending")
    try:
        pending.write_text(content, encoding="utf-8", newline="\n")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def write_experiment(report: dict, output: Path,
                     manifest_path: Path | None = None) -> None:
    """Write raw JSONL and a small provenance manifest after a complete run."""
    output = Path(output)
    manifest_path = Path(manifest_path or output.with_suffix(".summary.json"))
    if output.resolve() == manifest_path.resolve():
        raise ValueError("Raw rows and manifest need distinct paths.")
    _write_atomic(output, "".join(_json(row) + "\n" for row in report["rows"]))
    _write_atomic(manifest_path, json.dumps(report["manifest"], indent=2, allow_nan=False) + "\n")


def run_committed_experiment(*, random_seed: int = 313) -> dict:
    """Rebuild and verify the exact test cohort recorded with the saved DQN."""
    metadata = get_model_metadata()
    dataset = metadata["dataset"]
    seeds = dataset["seeds"]
    counts = metadata["split_counts"]
    splits = build_dynamic_episode_splits(
        training_users=counts["training"], validation_users=counts["validation"],
        test_users=counts["test"], months=dataset["months_per_user"],
        population_seed=seeds["population"], split_seed=seeds["split"],
        selection_seed=seeds["selection"], trajectory_seed=seeds["trajectory"],
        shock_probability=dataset["shock_probability"],
    )
    if splits.summary != dataset:
        raise ValueError("Rebuilt test cohort or trajectory parameters differ from model metadata.")
    model = load_model()
    if get_model_metadata()["artifact_sha256"] != metadata["artifact_sha256"]:
        raise ValueError("Monthly model changed while preparing the experiment.")
    return run_paired_experiment(splits.test, model=model,
                                 random_seed=random_seed, model_metadata=metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired monthly selections on the saved test cohort.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--random-seed", type=int, default=313)
    args = parser.parse_args()
    report = run_committed_experiment(random_seed=args.random_seed)
    write_experiment(report, args.output)
    print(json.dumps({**report["manifest"], "raw_path": str(args.output.resolve()),
                      "manifest_path": str(args.output.with_suffix(".summary.json").resolve())}, indent=2))


if __name__ == "__main__":
    main()
