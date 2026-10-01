"""Paired financial-input and selected-agent ablations for monthly policies."""

import argparse
from collections import defaultdict
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from app.advisory.dynamic import build_dynamic_planning_state
from app.rl.dynamic_experiment import (_json, _write_atomic, load_committed_test_episodes,
                                       write_experiment)
from app.rl.dynamic_model_management import load_model
from app.rl.dynamic_reward import audit_dynamic_reward
from app.rl.selection import AGENT_IDS
from app.rl.variable_income_experiment import (DEFAULT_CONFIG as DEFAULT_SCENARIOS,
                                               ControlledScenario, build_scenario_episodes,
                                               load_scenarios, run_controlled_experiment)


ABLATION_VERSION = "monthly-ablations-v1"
ABLATIONS = ("no_volatility", "no_shocks", "omit_agent")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / ABLATION_VERSION


def _variant(baseline: ControlledScenario, kind: str) -> ControlledScenario:
    values = baseline.model_dump(mode="json")
    values["name"] = f"{baseline.name}_{kind}"
    if kind == "no_volatility":
        values["income_volatility"] = 0
        values["description"] = baseline.description + "; income volatility set to zero"
    elif kind == "no_shocks":
        values["shock_probability"] = 0
        values["forced_events"] = []
        values["description"] = baseline.description + "; simulator shocks removed"
    else:
        raise ValueError("Unknown financial-input ablation.")
    return ControlledScenario.model_validate(values)


def _agent_omission(episodes, baseline_report: dict, *, agent: str) -> dict:
    """Hold each policy action fixed and recompute the proxy after suppressing one agent."""
    if agent not in AGENT_IDS:
        raise ValueError("agent must be in the committed action catalogue.")
    states = {}
    financial_states = {}
    for episode in episodes:
        for position, month in enumerate(episode.months):
            key = (episode.profile.synthetic_id, month.month_index)
            states[key] = build_dynamic_planning_state(
                episode.profile, month,
                as_of_date=episode.as_of_date + timedelta(days=30 * position),
                goals=episode.goals,
            )
            financial_states[key] = month.model_dump(mode="json")
    source = baseline_report["manifest"]
    if len(states) != source["decision_count_per_method"]:
        raise ValueError("The ablation episodes differ from the paired baseline.")
    rows = []
    for row in baseline_report["rows"]:
        key = (row["synthetic_id"], row["month_index"])
        state = states[key]
        if (state.fingerprint() != row["state_fingerprint"] or
                financial_states[key] != row["financial_state"]):
            raise ValueError("The ablation state differs from the paired baseline.")
        selected = tuple(row["selected_agents"])
        if [item["agent_id"] for item in row["agent_results"]] != list(selected):
            raise ValueError("The baseline agent outputs differ from the recorded selection.")
        original = audit_dynamic_reward(state, selected)
        if (abs(original.total - row["reward"]) > 1e-9 or
                original.components != row["reward_components"] or
                json.loads(_json(original.to_dict())) != row["reward_audit"]):
            raise ValueError("The baseline reward does not match its recorded state and selection.")
        effective = tuple(item for item in selected if item != agent)
        audit = audit_dynamic_reward(state, effective)
        transformed = {
            "ablation_version": ABLATION_VERSION,
            "method": row["method"], "synthetic_id": row["synthetic_id"],
            "month_index": row["month_index"],
            "state_fingerprint": row["state_fingerprint"],
            "policy_action": row["action"],
            "policy_selected_agents": row["selected_agents"],
            "effective_agents": list(effective), "omitted_agent": agent,
            "effective_agent_results": [item for item in row["agent_results"]
                                        if item["agent_id"] != agent],
            "agent_was_selected": agent in selected,
            "source_reward": row["reward"], "ablated_reward": audit.total,
            "reward_delta": audit.total - row["reward"],
            "source_critical_misses": row["reward_audit"]["missed_critical_agents"],
            "ablated_critical_misses": list(audit.missed_critical_agents),
            "critical_agents": list(audit.critical_agents),
            "ablated_reward_components": audit.components,
            "effective_priority_actions": [item for item in row["priority_actions"]
                                           if item["agent_id"] != agent],
        }
        rows.append(json.loads(_json(transformed)))
    by_method = defaultdict(list)
    for row in rows:
        by_method[row["method"]].append(row)
    methods = {}
    for method, items in by_method.items():
        opportunities = sum(len(item["critical_agents"]) for item in items)
        before_missed = sum(len(item["source_critical_misses"]) for item in items)
        after_missed = sum(len(item["ablated_critical_misses"]) for item in items)
        methods[method] = {
            "decision_count": len(items),
            "affected_decisions": sum(item["agent_was_selected"] for item in items),
            "mean_reward_before": mean(item["source_reward"] for item in items),
            "mean_reward_after": mean(item["ablated_reward"] for item in items),
            "mean_reward_delta": mean(item["reward_delta"] for item in items),
            "mean_agent_calls_before": mean(len(item["policy_selected_agents"]) for item in items),
            "mean_agent_calls_after": mean(len(item["effective_agents"]) for item in items),
            "critical_opportunities": opportunities,
            "critical_misses_before": before_missed,
            "critical_misses_after": after_missed,
            "critical_miss_rate_before": (before_missed / opportunities if opportunities else None),
            "critical_miss_rate_after": (after_missed / opportunities if opportunities else None),
        }
    raw_text = "".join(_json(row) + "\n" for row in rows)
    return {
        "summary": {
            "omitted_agent": agent,
            "source_raw_rows_sha256": source["raw_rows_sha256"],
            "source_trajectory_sha256": source["trajectory_sha256"],
            "raw_rows_sha256": sha256(raw_text.encode("utf-8")).hexdigest(),
            "row_count": len(rows),
            "methods": methods,
            "method": "Post-selection execution intervention. Policy actions are unchanged; selected agent findings and priority actions are filtered, and the selection proxy is recomputed on the same state.",
            "execution_time": "not_measured_for_intervention",
        },
        "rows": rows,
    }


def run_ablation_experiment(base_episodes, baseline: ControlledScenario, *, model,
                            ablations: tuple[str, ...] = ABLATIONS,
                            agent: str = "emergency", months: int = 12,
                            trajectory_seed: int = 20261001, random_seed: int = 313,
                            model_metadata: dict | None = None) -> dict:
    """Compare explicit single-parameter changes and an execution-stage agent omission."""
    base_episodes = tuple(base_episodes)
    ablations = tuple(ablations)
    if not ablations or len(set(ablations)) != len(ablations) or any(
            item not in ABLATIONS for item in ablations):
        raise ValueError("Select distinct supported ablations.")
    if "omit_agent" in ablations and agent not in AGENT_IDS:
        raise ValueError("agent must be in the committed action catalogue.")
    financial = [item for item in ablations if item != "omit_agent"]
    scenarios = (baseline, *(_variant(baseline, kind) for kind in financial))
    controlled = run_controlled_experiment(
        base_episodes, scenarios, model=model, months=months,
        trajectory_seed=trajectory_seed, random_seed=random_seed,
        model_metadata=model_metadata,
    )
    baseline_report = controlled["raw_reports"][baseline.name]
    baseline_metrics = controlled["summary"]["scenarios"][0]["metrics"]
    comparisons = []
    for kind, item in zip(financial, controlled["summary"]["scenarios"][1:], strict=True):
        comparisons.append({
            "ablation": kind,
            "scenario": item["scenario"]["name"],
            "changed_input": (
                {"income_volatility": {"before": baseline.income_volatility, "after": 0}}
                if kind == "no_volatility" else
                {"shock_probability": {"before": baseline.shock_probability, "after": 0},
                 "forced_events": {"before": baseline.model_dump(mode="json")["forced_events"],
                                   "after": []}}
            ),
            "paired_behavior": item["behavior_vs_first_scenario"],
            "methods": {method: {
                "mean_reward_before": baseline_metrics[method]["average_reward"],
                "mean_reward_after": item["metrics"][method]["average_reward"],
                "mean_reward_delta": (item["metrics"][method]["average_reward"] -
                                      baseline_metrics[method]["average_reward"]),
                "mean_agent_calls_before": baseline_metrics[method]["agent_efficiency"]["mean_agent_calls"],
                "mean_agent_calls_after": item["metrics"][method]["agent_efficiency"]["mean_agent_calls"],
            } for method in baseline_metrics},
        })
    omission = None
    if "omit_agent" in ablations:
        episodes = build_scenario_episodes(base_episodes, baseline, months=months,
                                           trajectory_seed=trajectory_seed)
        omission = _agent_omission(episodes, baseline_report, agent=agent)
    summary = {
        "ablation_version": ABLATION_VERSION,
        "dataset_split": "test", "user_count": len(base_episodes),
        "months_per_user": months, "trajectory_seed": trajectory_seed,
        "random_seed": random_seed,
        "source_model": controlled["summary"]["source_model"],
        "baseline_scenario": baseline.model_dump(mode="json"),
        "paired_scenarios": controlled["summary"]["scenarios"],
        "comparisons": comparisons,
        "agent_omission": omission["summary"] if omission is not None else None,
        "existing_controls": {
            "without_rl": "Rule-Based and seeded Random are already independent arms on these exact states; omitting the trained RL arm does not change their recorded decisions or rewards.",
            "without_llm": "The offline selector and deterministic agents do not call the optional LLM, so there is no LLM invocation to ablate in this outcome measure.",
        },
        "limitations": [
            "Income changes can also change downstream cash balances and event eligibility; comparison deltas are effects within this simulator, not isolated real-world causal effects.",
            "Agent omission preserves the policy's proposed action and does not retrain or rerun it. It measures a post-selection execution intervention, not how that policy would adapt to a smaller catalogue.",
            "The agent-omission trace does not measure execution time or construct a new coordinated recommendation.",
            "Reward is a synthetic selection proxy; none of these ablations measure financial improvement or advice quality.",
        ],
    }
    return {"summary": summary, "raw_reports": controlled["raw_reports"],
            "agent_omission_rows": omission["rows"] if omission is not None else None}


def write_ablation_experiment(report: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in report["summary"]["paired_scenarios"]:
        name = item["scenario"]["name"]
        write_experiment(report["raw_reports"][name], output_dir / f"{name}.jsonl")
    if report["agent_omission_rows"] is not None:
        _write_atomic(output_dir / "agent-omission.jsonl",
                      "".join(_json(row) + "\n" for row in report["agent_omission_rows"]))
    path = output_dir / "summary.json"
    _write_atomic(path, json.dumps(report["summary"], indent=2, allow_nan=False) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired monthly policy ablations.")
    parser.add_argument("--scenario-config", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--base-scenario", default="B")
    parser.add_argument("--ablations", nargs="+", choices=ABLATIONS, default=ABLATIONS)
    parser.add_argument("--agent", choices=AGENT_IDS, default="emergency")
    parser.add_argument("--users", type=int, default=64)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--trajectory-seed", type=int, default=20261001)
    parser.add_argument("--random-seed", type=int, default=313)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not 1 <= args.users <= 64:
        parser.error("--users must be between 1 and 64 held-out users")
    baseline = next((item for item in load_scenarios(args.scenario_config)
                     if item.name == args.base_scenario), None)
    if baseline is None:
        parser.error("--base-scenario must name a scenario in the configuration")
    episodes, metadata = load_committed_test_episodes()
    report = run_ablation_experiment(
        episodes[:args.users], baseline, model=load_model(),
        ablations=tuple(args.ablations), agent=args.agent, months=args.months,
        trajectory_seed=args.trajectory_seed, random_seed=args.random_seed,
        model_metadata=metadata,
    )
    path = write_ablation_experiment(report, args.output_dir)
    print(json.dumps({
        "summary_path": str(path.resolve()),
        "users": report["summary"]["user_count"],
        "comparisons": report["summary"]["comparisons"],
        "agent_omission": report["summary"]["agent_omission"],
    }, indent=2))


if __name__ == "__main__":
    main()
