"""Inspect one synthetic user-month across all paired selection policies."""

import argparse
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from app.rl.dynamic_environment import DynamicAgentSelectionEnv, DynamicEpisode
from app.rl.dynamic_experiment import (DEFAULT_OUTPUT as DEFAULT_RAW_PATH,
                                       METHODS, _write_atomic, load_committed_test_episodes)
from app.rl.dynamic_integration import _recommendation
from app.rl.dynamic_metrics import summarize_metrics


CASE_VERSION = "paired-monthly-case-v1"
DEFAULT_CASE_PATH = DEFAULT_RAW_PATH.parent / "paired-monthly-case-v1.summary.json"


def _conflicts(recommendation: dict) -> tuple[str, list[dict]]:
    """Describe only constraints established by a built coordinated plan."""
    if recommendation["status"] != "complete":
        return "not_assessed", []
    plan = recommendation["coordinated_plan"]["monthly_plan"]
    conflicts = []
    if plan["hold_reason"]:
        conflicts.append({"code": "allocation_hold", "type": "planning_constraint",
                          "description": plan["hold_reason"]})
    for allocation in plan["goal_allocations"]:
        if allocation["status"] == "underfunded" and allocation["funding_gap"] is not None:
            gap = Decimal(allocation["funding_gap"])
            if gap > 0:
                conflicts.append({
                    "code": "goal_funding_gap", "type": "funding_constraint",
                    "description": f"The monthly allocation for {allocation['requirement']['goal']['name']} is short of its calculated requirement.",
                    "goal_id": allocation["requirement"]["goal"]["id"],
                    "funding_gap": str(gap),
                    "source_agent_ids": ["budget", "emergency", "goal"],
                })
    return "assessed", conflicts


def _explanation(method: str, row: dict, recommendation: dict,
                 conflicts_status: str, conflicts: list[dict]) -> list[str]:
    selected = ", ".join(row["selected_agents"])
    critical = row["reward_audit"]["critical_agents"]
    missed = row["reward_audit"]["missed_critical_agents"]
    readiness = recommendation["plan_readiness"]
    explanation = [
        f"{method} chose action {row['action']}, selecting {selected}.",
        f"The selection-proxy reward is {row['reward']} points from the recorded reward components; it is not a financial outcome.",
    ]
    if critical:
        explanation.insert(1, f"The synthetic reward audit marked {', '.join(critical)} as critical; " +
                           (f"{', '.join(missed)} were not selected." if missed else
                            "all were selected."))
    else:
        explanation.insert(1, "The synthetic reward audit marked no agent as critical for this month.")
    if recommendation["status"] == "partial":
        explanation.append(
            f"A coordinated plan was withheld because {', '.join(readiness['missing_agents'])} did not run.")
        explanation.append("Conflicts in a coordinated plan could not be assessed from this partial selection.")
    else:
        explanation.append("The coordinated plan uses only the selected agents' recorded outputs.")
        if conflicts_status == "assessed":
            explanation.append(f"The deterministic plan records {len(conflicts)} funding or allocation constraints.")
    return explanation


def inspect_case(rows: list[dict], manifest: dict, episodes: tuple[DynamicEpisode, ...], *,
                 synthetic_id: int, month_index: int) -> dict:
    """Build an evidence-grounded case from one complete paired experiment."""
    summarize_metrics(rows, manifest)  # Checks the full paired keys and identical monthly states.
    episodes = tuple(episodes)
    ids = ",".join(str(item.profile.synthetic_id) for item in episodes)
    if (len(episodes) != manifest["user_count"] or
            sha256(ids.encode("ascii")).hexdigest() != manifest["user_id_sha256"]):
        raise ValueError("Episodes differ from the paired test cohort.")
    episode = next((item for item in episodes if item.profile.synthetic_id == synthetic_id), None)
    if episode is None:
        raise ValueError("Synthetic user is not in the paired test cohort.")
    position = next((index for index, month in enumerate(episode.months)
                     if month.month_index == month_index), None)
    if position is None:
        raise ValueError("Month is not in the paired test cohort.")
    selected_rows = {row["method"]: row for row in rows
                     if row["synthetic_id"] == synthetic_id and row["month_index"] == month_index}
    if set(selected_rows) != set(METHODS):
        raise ValueError("Case is missing a paired method.")
    expected_month = episode.months[position].model_dump(mode="json")
    expected_goals = [goal.model_dump(mode="json") for goal in episode.goals]
    if any(row["financial_state"] != expected_month or row["goals"] != expected_goals
           for row in selected_rows.values()):
        raise ValueError("Case state differs from the rebuilt test episode.")
    environment = DynamicAgentSelectionEnv(episode)
    methods = {}
    try:
        for method in METHODS:
            row = selected_rows[method]
            recommendation = _recommendation(episode, position, environment, row, method=method)
            conflicts_status, conflicts = _conflicts(recommendation)
            methods[method] = {
                "action": row["action"], "action_version": row["action_version"],
                "selected_agents": row["selected_agents"],
                "agent_outputs": row["agent_results"],
                "priority_actions": row["priority_actions"],
                "reward": row["reward"], "reward_components": row["reward_components"],
                "reward_audit": row["reward_audit"],
                "recommendation": recommendation,
                "conflicts_status": conflicts_status, "conflicts": conflicts,
                "explanation": _explanation(method, row, recommendation,
                                            conflicts_status, conflicts),
            }
    finally:
        environment.close()
    return {
        "case_version": CASE_VERSION,
        "source": {"experiment_version": manifest["experiment_version"],
                   "raw_rows_sha256": manifest["raw_rows_sha256"],
                   "user_id_sha256": manifest["user_id_sha256"],
                   "trajectory_sha256": manifest["trajectory_sha256"]},
        "synthetic_id": synthetic_id, "month_index": month_index,
        "as_of_date": (episode.as_of_date + timedelta(days=30 * position)).isoformat(),
        "user_state": json.loads(json.dumps(asdict(episode.profile), default=str)),
        "monthly_state": expected_month, "goals": expected_goals,
        "methods": methods,
        "limitations": [
            "This is a synthetic case; the next financial month was precomputed and is unaffected by agent selection.",
            "A complete coordinated plan means required agent facts were present, not that the advice is validated or effective.",
            "Conflicts are only the explicit funding or allocation constraints in a built plan; partial plans remain unassessed.",
        ],
    }


def inspect_case_file(raw_path: Path = DEFAULT_RAW_PATH, *, synthetic_id: int | None = None,
                      month_index: int = 1,
                      episodes: tuple[DynamicEpisode, ...] | None = None) -> dict:
    """Verify a saved trace and inspect one case without rerunning policies."""
    raw_path = Path(raw_path)
    raw_bytes = raw_path.read_bytes()
    manifest = json.loads(raw_path.with_suffix(".summary.json").read_text(encoding="utf-8"))
    if sha256(raw_bytes).hexdigest() != manifest.get("raw_rows_sha256"):
        raise ValueError("Raw experiment rows do not match their manifest checksum.")
    if episodes is None:
        episodes, metadata = load_committed_test_episodes()
        if (manifest.get("dataset") != metadata["dataset"] or
                manifest.get("model", {}).get("artifact_sha256") != metadata["artifact_sha256"]):
            raise ValueError("Saved trace differs from the committed test cohort or model.")
    episodes = tuple(episodes)
    if not episodes:
        raise ValueError("No test episodes were supplied.")
    chosen_id = episodes[0].profile.synthetic_id if synthetic_id is None else synthetic_id
    rows = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines()]
    return inspect_case(rows, manifest, episodes,
                        synthetic_id=chosen_id, month_index=month_index)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect one held-out monthly case across all policies.")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--synthetic-id", type=int)
    parser.add_argument("--month-index", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_CASE_PATH)
    args = parser.parse_args()
    case = inspect_case_file(args.raw, synthetic_id=args.synthetic_id,
                             month_index=args.month_index)
    _write_atomic(args.output, json.dumps(case, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "case_version": CASE_VERSION, "synthetic_id": case["synthetic_id"],
        "month_index": case["month_index"],
        "methods": {method: {"action": detail["action"],
                             "selected_agents": detail["selected_agents"],
                             "reward": detail["reward"],
                             "recommendation_status": detail["recommendation"]["status"],
                             "conflicts_status": detail["conflicts_status"]}
                    for method, detail in case["methods"].items()},
        "output_path": str(args.output.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
