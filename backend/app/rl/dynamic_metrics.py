"""Descriptive research metrics over a verified paired monthly trace."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median, pvariance

from app.rl.dynamic_experiment import (DEFAULT_OUTPUT as DEFAULT_RAW_PATH,
                                       EXPERIMENT_VERSION, METHODS, _write_atomic)


METRICS_VERSION = "paired-monthly-metrics-v1"
DEFAULT_METRICS_PATH = (DEFAULT_RAW_PATH.parent / "paired-monthly-metrics-v1.summary.json")
RISK_AGENTS = frozenset(("budget", "debt", "emergency", "risk"))


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _priority_provenance_consistent(row: dict) -> bool:
    selected = row["selected_agents"]
    results = row["agent_results"]
    if (len(selected) != len(set(selected)) or len(results) != len(selected) or
            [result["agent_id"] for result in results] != selected or
            row["agent_call_count"] != len(selected)):
        return False
    expected = Counter()
    for result in results:
        for finding in result["findings"]:
            if finding["priority"]:
                expected[json.dumps({
                    "agent_id": result["agent_id"],
                    "code": f"review_{result['agent_id']}",
                    "finding_code": finding["code"],
                    "title": finding["title"],
                    "reason": finding["reason"],
                    "evidence": finding["evidence"],
                    "limitations": finding["limitations"],
                }, sort_keys=True)] += 1
    actual = Counter(json.dumps(action, sort_keys=True) for action in row["priority_actions"])
    return actual == expected


def summarize_metrics(rows: list[dict], manifest: dict) -> dict:
    """Calculate observed policy-selection proxies on complete paired decisions."""
    if (manifest.get("experiment_version") != EXPERIMENT_VERSION or
            manifest.get("methods") != list(METHODS) or
            manifest.get("dataset_split") != "test"):
        raise ValueError("Metrics require the current paired test experiment.")
    groups = defaultdict(dict)
    for row in rows:
        if row.get("experiment_version") != EXPERIMENT_VERSION or row.get("dataset_split") != "test":
            raise ValueError("Rows must come from the current paired test experiment.")
        method = row.get("method")
        key = (row["synthetic_id"], row["month_index"])
        if method not in METHODS or method in groups[key]:
            raise ValueError("Rows must have one decision per method and paired month.")
        groups[key][method] = row
    if (not groups or any(set(group) != set(METHODS) for group in groups.values()) or
            len(groups) != manifest.get("decision_count_per_method") or
            len(rows) != manifest.get("row_count") or
            len({key[0] for key in groups}) != manifest.get("user_count")):
        raise ValueError("Rows do not form the complete paired test cohort.")
    for group in groups.values():
        for field in ("state_fingerprint", "financial_state", "goals", "observation"):
            if len({json.dumps(row[field], sort_keys=True) for row in group.values()}) != 1:
                raise ValueError("Paired methods received different monthly states.")
    for row in rows:
        elapsed = row.get("execution_time_ns")
        if isinstance(elapsed, bool) or not isinstance(elapsed, int) or elapsed < 0:
            raise ValueError("Every row needs a nonnegative execution_time_ns measurement.")

    by_method = {method: [row for row in rows if row["method"] == method]
                 for method in METHODS}
    methods = {}
    for method, method_rows in by_method.items():
        eligible_risks = covered_risks = eligible_goals = addressed_goals = 0
        consistent = 0
        for row in method_rows:
            selected = set(row["selected_agents"])
            risks = set(row["reward_audit"]["critical_agents"]) & RISK_AGENTS
            eligible_risks += len(risks)
            covered_risks += len(risks & selected)
            open_goals = sum(Decimal(goal["target_amount"]) > Decimal(goal["saved_amount"])
                             for goal in row["goals"])
            eligible_goals += open_goals
            addressed_goals += open_goals if "goal" in selected else 0
            consistent += _priority_provenance_consistent(row)
        calls = [row["agent_call_count"] for row in method_rows]
        rewards = [row["reward"] for row in method_rows]
        times_ms = [row["execution_time_ns"] / 1_000_000 for row in method_rows]
        methods[method] = {
            "decision_count": len(method_rows),
            "risk_coverage": {"covered_risks": covered_risks,
                              "eligible_risks": eligible_risks,
                              "rate": _rate(covered_risks, eligible_risks),
                              "status": "measured" if eligible_risks else "unavailable"},
            "goal_alignment": {"addressed_goals": addressed_goals,
                               "eligible_goals": eligible_goals,
                               "rate": _rate(addressed_goals, eligible_goals),
                               "status": "measured" if eligible_goals else "unavailable"},
            "recommendation_consistency": {"status": "unavailable", "rate": None,
                                           "reason": "The paired trace does not contain a coordinated recommendation to check."},
            "priority_action_provenance": {"consistent_decisions": consistent,
                                           "evaluated_decisions": len(method_rows),
                                           "rate": _rate(consistent, len(method_rows))},
            "agent_efficiency": {"total_agent_calls": sum(calls),
                                 "mean_agent_calls": mean(calls)},
            "average_reward": mean(rewards),
            "reward_variance": pvariance(rewards),
            "execution_time": {"mean_ms": mean(times_ms),
                               "median_ms": median(times_ms),
                               "scope": "policy_selection_and_environment_step"},
        }
    limitations = [
        "Financial months are precomputed; no action changes user finances or measures advice uptake.",
        "The trace contains priority actions but no coordinated recommendation, so Recommendation Consistency is unavailable.",
        "Decision rows from one user are correlated; descriptive values are not significance tests.",
    ]
    if all(values["goal_alignment"]["eligible_goals"] == 0 for values in methods.values()):
        limitations.append("This cohort has no unfinished goal snapshots, so Goal Alignment is unavailable.")
    return {
        "metrics_version": METRICS_VERSION,
        "source_experiment_version": EXPERIMENT_VERSION,
        "source_raw_rows_sha256": manifest["raw_rows_sha256"],
        "cohort": {"dataset_split": "test", "user_count": manifest["user_count"],
                   "decisions_per_method": len(groups),
                   "user_id_sha256": manifest["user_id_sha256"],
                   "trajectory_sha256": manifest["trajectory_sha256"]},
        "definitions": {
            "risk_coverage": "Selected critical Budget, Debt, Emergency, and Risk agent categories / all such state-based critical categories; pooled over decisions.",
            "goal_alignment": "Unfinished goal-decision opportunities with Goal agent selected / all unfinished goal-decision opportunities; does not measure funding or advice quality.",
            "recommendation_consistency": "Unavailable until a coordinated recommendation and explicit consistency criteria are recorded for each method.",
            "priority_action_provenance": "Priority actions exactly match priority findings returned by selected agents; a structural trace check, not advice consistency.",
            "agent_efficiency": "Mean and total activated agents per decision; fewer calls alone are not better.",
            "average_reward": "Mean synthetic monthly selection-proxy reward per decision.",
            "reward_variance": "Population variance of synthetic reward across decisions, in squared proxy points.",
            "execution_time": "Observed local elapsed time from policy choice through agent execution and reward, excluding state preparation and serialization; fixed method order and machine load affect it.",
        },
        "methods": methods,
        "limitations": limitations,
    }


def analyze_file(raw_path: Path = DEFAULT_RAW_PATH) -> dict:
    raw_path = Path(raw_path)
    raw_bytes = raw_path.read_bytes()
    manifest = json.loads(raw_path.with_suffix(".summary.json").read_text(encoding="utf-8"))
    if sha256(raw_bytes).hexdigest() != manifest.get("raw_rows_sha256"):
        raise ValueError("Raw experiment rows do not match their manifest checksum.")
    rows = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines()]
    return summarize_metrics(rows, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute measured paired monthly research metrics.")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_METRICS_PATH)
    args = parser.parse_args()
    report = analyze_file(args.raw)
    _write_atomic(args.output, json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"metrics_version": METRICS_VERSION,
                      "user_count": report["cohort"]["user_count"],
                      "decisions_per_method": report["cohort"]["decisions_per_method"],
                      "methods": report["methods"],
                      "output_path": str(args.output.resolve())}, indent=2))


if __name__ == "__main__":
    main()
