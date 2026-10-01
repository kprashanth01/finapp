"""Evidence-grounded conflicts in paired synthetic advisory selections."""

import argparse
from decimal import Decimal
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.rl.dynamic_cases import inspect_case
from app.rl.dynamic_experiment import (METHODS, _write_atomic,
                                       load_committed_test_episodes,
                                       run_paired_experiment, write_experiment)
from app.rl.dynamic_model_management import load_model
from app.rl.variable_income_experiment import ControlledScenario, build_scenario_episodes


CONFLICT_VERSION = "conflict-scenarios-v1"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "experiments" / "conflict-scenarios.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / CONFLICT_VERSION
ConflictCode = Literal["reserve_vs_goal", "debt_vs_goal", "investment_vs_goal"]


class ConflictScenario(ControlledScenario):
    """One controlled month expected to expose a named competition for capacity."""

    expected_conflict: ConflictCode
    explanation: str = Field(min_length=1)


def load_conflict_scenarios(path: Path = DEFAULT_CONFIG) -> tuple[ConflictScenario, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Conflict scenarios must be a nonempty JSON array.")
    scenarios = tuple(ConflictScenario.model_validate(item) for item in payload)
    if len({item.name for item in scenarios}) != len(scenarios):
        raise ValueError("Conflict scenario names must be unique.")
    return scenarios


def _sources(outputs: dict, agents: tuple[str, ...], goal_code: str) -> list[dict]:
    return [
        {"agent_id": agent_id,
         "finding_code": (goal_code if agent_id == "goal" else outputs[agent_id]["findings"][0]["code"])}
        for agent_id in agents
    ]


def detect_conflicts(agent_outputs: list[dict]) -> list[dict]:
    """Label only competitions supported by these actually executed agents."""
    outputs = {result["agent_id"]: result for result in agent_outputs}
    if len(outputs) != len(agent_outputs):
        raise ValueError("Agent outputs contain a duplicate agent.")
    if "budget" not in outputs or "goal" not in outputs:
        return []
    capacity_value = outputs["budget"]["facts"]["capacity"]
    if capacity_value is None:
        return []
    capacity = Decimal(capacity_value)
    conflicts = []
    for requirement in outputs["goal"]["facts"]["requirements"]:
        if requirement["status"] != "future" or requirement["required_monthly"] is None:
            continue
        required = Decimal(requirement["required_monthly"])
        if required <= 0:
            continue
        goal_id = requirement["goal"]["id"]
        goal_code = f"goal_{goal_id}"
        common = {"goal_id": goal_id, "capacity": str(capacity),
                  "goal_required_monthly": str(required)}
        emergency = outputs.get("emergency")
        if emergency is not None and emergency["facts"]["gap"] is not None:
            gap = Decimal(emergency["facts"]["gap"])
            if gap > 0 and gap + required > capacity:
                agents = ("budget", "emergency", "goal")
                conflicts.append({"code": "reserve_vs_goal", "goal_id": goal_id,
                                  "agent_ids": list(agents),
                                  "source_refs": _sources(outputs, agents, goal_code),
                                  "evidence": {**common, "reserve_gap": str(gap)}})
        debt = outputs.get("debt")
        if debt is not None and debt["facts"]["review_required"] and capacity > 0:
            agents = ("budget", "debt", "goal")
            conflicts.append({"code": "debt_vs_goal", "goal_id": goal_id,
                              "agent_ids": list(agents),
                              "source_refs": _sources(outputs, agents, goal_code),
                              "evidence": {**common,
                                           "debt_reason_code": debt["facts"]["reason_code"]}})
        investment = outputs.get("investment")
        if (investment is not None and
                investment["facts"]["status"] == "ready_to_consider" and
                required > capacity):
            agents = ("budget", "goal", "investment")
            conflicts.append({"code": "investment_vs_goal", "goal_id": goal_id,
                              "agent_ids": list(agents),
                              "source_refs": _sources(outputs, agents, goal_code),
                              "evidence": {**common,
                                           "investment_agent_status": "ready_to_consider"}})
    return conflicts


def _resolution(conflict: dict, recommendation: dict) -> dict:
    """Read the existing coordinator's actual plan; never invent a plan for partial runs."""
    if recommendation["status"] != "complete":
        return {"status": "withheld_partial", "mechanism": None,
                "evidence": {"missing_agents": recommendation["plan_readiness"]["missing_agents"]}}
    plan = recommendation["coordinated_plan"]
    monthly = plan["monthly_plan"]
    allocation = next((item for item in monthly["goal_allocations"]
                       if item["requirement"]["goal"]["id"] == conflict["goal_id"]), None)
    if allocation is None:
        return {"status": "unsupported", "mechanism": None,
                "evidence": {"reason": "No matching goal allocation was recorded."}}
    code = conflict["code"]
    if code == "reserve_vs_goal":
        resolved = (Decimal(monthly["emergency_allocation"] or "0") > 0 and
                    allocation["status"] == "underfunded" and
                    Decimal(allocation["funding_gap"] or "0") > 0)
        mechanism = "reserve_first"
        evidence = {"emergency_allocation": monthly["emergency_allocation"],
                    "goal_allocation": allocation["allocated_monthly"],
                    "goal_funding_gap": allocation["funding_gap"]}
    elif code == "debt_vs_goal":
        resolved = ("debt payments" in (monthly["hold_reason"] or "").lower() and
                    Decimal(allocation["allocated_monthly"] or "0") == 0 and
                    Decimal(allocation["funding_gap"] or "0") > 0)
        mechanism = "debt_review_hold"
        evidence = {"hold_reason": monthly["hold_reason"],
                    "goal_allocation": allocation["allocated_monthly"],
                    "goal_funding_gap": allocation["funding_gap"]}
    else:
        resolved = (plan["investment"]["status"] == "deferred" and
                    any("underfunded goals" in reason for reason in plan["investment"]["reasons"]) and
                    allocation["status"] == "underfunded" and
                    Decimal(allocation["funding_gap"] or "0") > 0)
        mechanism = "goal_before_investment"
        evidence = {"investment_status": plan["investment"]["status"],
                    "investment_reasons": plan["investment"]["reasons"],
                    "goal_allocation": allocation["allocated_monthly"],
                    "goal_funding_gap": allocation["funding_gap"]}
    return {"status": "resolved_by_coordinator" if resolved else "unsupported",
            "mechanism": mechanism if resolved else None, "evidence": evidence}


def _method_record(detail: dict, reference_conflicts: list[dict]) -> dict:
    observed = detect_conflicts(detail["agent_outputs"])
    selected = set(detail["selected_agents"])
    outcomes = []
    for reference in reference_conflicts:
        match = next((item for item in observed if item["code"] == reference["code"] and
                      item["goal_id"] == reference["goal_id"]), None)
        if match is None:
            missing = [agent for agent in reference["agent_ids"] if agent not in selected]
            if not missing:
                raise ValueError("Selected agents did not reproduce the reference conflict.")
            outcomes.append({"code": reference["code"], "status": "not_observed",
                             "missing_agents": missing,
                             "resolution": None})
        else:
            outcomes.append({"code": match["code"], "status": "observed",
                             "missing_agents": [],
                             "resolution": _resolution(match, detail["recommendation"])})
    return {
        "action": detail["action"], "selected_agents": detail["selected_agents"],
        "agent_proposals": detail["agent_outputs"],
        "priority_actions": detail["priority_actions"],
        "observed_conflicts": observed, "reference_conflict_outcomes": outcomes,
        "recommendation": detail["recommendation"],
        "reward": detail["reward"], "reward_components": detail["reward_components"],
        "reward_audit": detail["reward_audit"],
        "decision_scope": (
            "The method selected agents; the existing deterministic coordinator produced the plan."
            if detail["recommendation"]["status"] == "complete" else
            "The method selected agents, but required facts were missing and no coordinated plan was produced."
        ),
    }


def run_conflict_experiment(base_episode, scenarios: tuple[ConflictScenario, ...], *, model,
                            trajectory_seed: int = 20261001, random_seed: int = 313,
                            model_metadata: dict | None = None) -> dict:
    """Verify each intended conflict against full rule-policy evidence, then compare policies."""
    scenarios = tuple(scenarios)
    if not scenarios or len({item.name for item in scenarios}) != len(scenarios):
        raise ValueError("Supply distinct conflict scenarios.")
    if base_episode.profile.dataset_split != "test":
        raise ValueError("Conflict experiments require a held-out test user.")
    reports = {}
    cases = []
    for scenario in scenarios:
        episode = build_scenario_episodes((base_episode,), scenario, months=1,
                                          trajectory_seed=trajectory_seed)
        report = run_paired_experiment(episode, model=model, random_seed=random_seed,
                                       model_metadata=model_metadata)
        case = inspect_case(report["rows"], report["manifest"], episode,
                            synthetic_id=base_episode.profile.synthetic_id, month_index=1)
        reference = detect_conflicts(case["methods"]["rule_based"]["agent_outputs"])
        if not any(item["code"] == scenario.expected_conflict for item in reference):
            raise ValueError(f"Scenario {scenario.name} did not produce {scenario.expected_conflict}.")
        rule_record = _method_record(case["methods"]["rule_based"], reference)
        if any(item["resolution"]["status"] != "resolved_by_coordinator"
               for item in rule_record["reference_conflict_outcomes"]):
            raise ValueError(f"Scenario {scenario.name} has no supported rule-policy resolution.")
        methods = {method: (rule_record if method == "rule_based" else
                            _method_record(case["methods"][method], reference))
                   for method in METHODS}
        reports[scenario.name] = report
        cases.append({
            "scenario": scenario.model_dump(mode="json"),
            "source": case["source"],
            "synthetic_id": case["synthetic_id"],
            "month_index": case["month_index"],
            "as_of_date": case["as_of_date"],
            "monthly_state": case["monthly_state"], "goals": case["goals"],
            "reference_conflicts": reference, "methods": methods,
        })
    summary = {
        "experiment_version": CONFLICT_VERSION,
        "dataset_split": "test", "synthetic_id": base_episode.profile.synthetic_id,
        "trajectory_seed": trajectory_seed, "random_seed": random_seed,
        "model": reports[scenarios[0].name]["manifest"]["model"],
        "cases": cases,
        "limitations": [
            "The rule policy selects all required agents, so its outputs identify the designed reference conflict. Unselected agents are not attributed to other methods.",
            "The trained DQN and Random methods choose agent subsets; only the deterministic coordinator resolves a complete recommendation.",
            "These labels cover three designed competitions for capacity, not every possible disagreement between agents.",
            "Investment readiness cannot coexist with the current Investment Agent's own high-debt or low-reserve blockers under consistent inputs.",
            "Rewards are synthetic selection proxies; no financial outcomes, transactions, or advice uptake are measured.",
        ],
    }
    return {"summary": summary, "raw_reports": reports}


def write_conflict_experiment(report: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for case in report["summary"]["cases"]:
        name = case["scenario"]["name"]
        write_experiment(report["raw_reports"][name], output_dir / f"{name}.jsonl")
    path = output_dir / "summary.json"
    _write_atomic(path, json.dumps(report["summary"], indent=2, allow_nan=False) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect competing agent priorities on paired held-out cases.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--synthetic-id", type=int, default=257)
    parser.add_argument("--trajectory-seed", type=int, default=20261001)
    parser.add_argument("--random-seed", type=int, default=313)
    args = parser.parse_args()
    episodes, metadata = load_committed_test_episodes()
    episode = next((item for item in episodes
                    if item.profile.synthetic_id == args.synthetic_id), None)
    if episode is None:
        parser.error("--synthetic-id must belong to the committed held-out test cohort")
    report = run_conflict_experiment(episode, load_conflict_scenarios(args.config),
                                     model=load_model(), trajectory_seed=args.trajectory_seed,
                                     random_seed=args.random_seed, model_metadata=metadata)
    path = write_conflict_experiment(report, args.output_dir)
    print(json.dumps({"summary_path": str(path.resolve()),
                      "cases": [{"name": case["scenario"]["name"],
                                 "conflict": case["scenario"]["expected_conflict"],
                                 "methods": {method: {
                                     "action": detail["action"],
                                     "selected_agents": detail["selected_agents"],
                                     "recommendation_status": detail["recommendation"]["status"],
                                     "conflict_outcome": detail["reference_conflict_outcomes"][0]["status"],
                                     "resolution": detail["reference_conflict_outcomes"][0]["resolution"],
                                     "reward": detail["reward"],
                                 } for method, detail in case["methods"].items()}}
                                for case in report["summary"]["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
