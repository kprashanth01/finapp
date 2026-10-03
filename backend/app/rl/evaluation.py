"""Offline, paired evaluation of agent selection on generated financial states."""

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from pathlib import Path

from app.rl.baselines import RandomBaseline, RuleBaseline
from app.rl.dqn_artifact import DEFAULT_ARTIFACT_DIR, load_dqn_artifact, verified_metadata
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import OBSERVATION_VERSION
from app.rl.reward import REWARD_VERSION
from app.rl.scenarios import SCENARIO_VERSION, generate_scenarios
from app.rl.selection import ACTION_VERSION

EVALUATION_VERSION = "paired-selection-evaluation-v2"
REPORT_FILENAME = "evaluation_report.json"
DEFAULT_SEED = 20261002
DEFAULT_CASE_COUNT = 256
DEFAULT_RANDOM_SEEDS = (17, 29, 43, 71, 97)


def _segments(state):
    names = []
    if state.emergency_fund_months is not None and state.emergency_fund_months < 3:
        names.append("low_reserve")
    if state.existing_debt > 0 and (state.debt_to_income_percent is None or
                                    state.debt_to_income_percent >= 20):
        names.append("high_or_unknown_debt_payment")
    if any(goal.target_amount > goal.saved_amount for goal in state.goals):
        names.append("unfinished_goal")
    if state.monthly_income > 0 and state.monthly_expenses >= state.monthly_income:
        names.append("expenses_at_or_above_income")
    return names


def _metrics(rows):
    rewards = [row["reward"] for row in rows]
    goal_rows = [row for row in rows if row["unfinished_goal"]]
    relevant = sum(row["relevant_count"] for row in rows)
    return {
        "mean_reward": round(statistics.mean(rewards), 4),
        "reward_variance": round(statistics.pvariance(rewards), 4),
        "critical_miss_rate": round(statistics.mean(row["missed_critical"] for row in rows), 4),
        "relevant_coverage_rate": round(sum(row["covered_relevant"] for row in rows) / relevant, 4),
        "risk_coverage_rate": round(statistics.mean(row["risk_selected"] for row in rows), 4),
        "goal_alignment_rate": (round(statistics.mean(row["goal_selected"] for row in goal_rows), 4)
                                if goal_rows else None),
        "goal_case_count": len(goal_rows),
        "mean_agent_calls": round(statistics.mean(row["agent_calls"] for row in rows), 4),
        "full_plan_rate": round(statistics.mean(row["full_plan"] for row in rows), 4),
        "mean_execution_ms": round(statistics.mean(row["execution_ms"] for row in rows), 4),
    }


def _paired_summary(rule_rows, rl_rows):
    """Compare DQN minus rule only when each row describes the same case."""
    if (not rule_rows or len(rule_rows) != len(rl_rows) or
            len({row["fingerprint"] for row in rule_rows}) != len(rule_rows) or
            any(rule["fingerprint"] != rl["fingerprint"] or
                set(rule["segments"]) != set(rl["segments"])
                for rule, rl in zip(rule_rows, rl_rows))):
        raise ValueError("Paired evaluation needs matching, distinct cases and segments.")

    def summarize(pairs):
        return {
            "case_count": len(pairs),
            "mean_reward_delta": round(statistics.mean(rl["reward"] - rule["reward"]
                                                       for rule, rl in pairs), 4),
            "rl_higher_score_count": sum(rl["reward"] > rule["reward"] for rule, rl in pairs),
            "equal_score_count": sum(rl["reward"] == rule["reward"] for rule, rl in pairs),
            "rl_lower_score_count": sum(rl["reward"] < rule["reward"] for rule, rl in pairs),
        }

    pairs = list(zip(rule_rows, rl_rows))
    summary = summarize(pairs)
    summary.update({
        "mean_agent_call_delta": round(statistics.mean(rl["agent_calls"] - rule["agent_calls"]
                                                       for rule, rl in pairs), 4),
        "same_selection_count": sum(rule["action"] == rl["action"] for rule, rl in pairs),
        "rl_partial_plan_count": sum(not rl["full_plan"] for _, rl in pairs),
        "segments": {name: summarize([pair for pair in pairs if name in pair[0]["segments"]])
                     for name in ("low_reserve", "high_or_unknown_debt_payment",
                                  "unfinished_goal", "expenses_at_or_above_income")
                     if any(name in rule["segments"] for rule, _ in pairs)},
    })
    return summary


def evaluate_cohort(states, model, *, scenario_seed: int,
                    random_seeds=DEFAULT_RANDOM_SEEDS):
    """Execute the same cases for each method; random is repeated across seeds."""
    states = tuple(states)
    random_seeds = tuple(random_seeds)
    if not states:
        raise ValueError("Evaluation needs at least one scenario.")
    if not random_seeds or len(set(random_seeds)) != len(random_seeds):
        raise ValueError("Random evaluation needs distinct seeds.")
    fingerprints = [state.fingerprint() for state in states]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("Evaluation scenarios must be distinct.")
    cohort_digest = hashlib.sha256("\n".join(fingerprints).encode()).hexdigest()
    methods = {}
    paired_rows = {}
    for method in ("random", "rule_based", "rl"):
        seeds = random_seeds if method == "random" else (None,)
        pooled = []
        runs = []
        for seed in seeds:
            policy = (RandomBaseline(seed=seed) if method == "random" else
                      RuleBaseline() if method == "rule_based" else None)
            rows = []
            for state in states:
                environment = AgentSelectionEnv(state)
                observation, _ = environment.reset()
                started = time.perf_counter()
                action = (int(model.predict(observation, deterministic=True)[0])
                          if method == "rl" else policy.choose_action(state, environment.catalog))
                _, reward, terminated, truncated, info = environment.step(action)
                elapsed = (time.perf_counter() - started) * 1000
                if not terminated or truncated or not math.isfinite(reward):
                    raise ValueError("Selection produced an invalid outcome.")
                selected = set(info["selected_agents"])
                audit = info["reward_audit"]
                relevant = set(audit["relevant_agents"])
                rows.append({
                    "fingerprint": state.fingerprint(), "action": action, "reward": reward,
                    "missed_critical": bool(audit["missed_critical_agents"]),
                    "relevant_count": len(relevant),
                    "covered_relevant": len(selected & relevant),
                    "risk_selected": "risk" in selected,
                    "unfinished_goal": any(g.target_amount > g.saved_amount for g in state.goals),
                    "goal_selected": "goal" in selected,
                    "agent_calls": len(selected),
                    "full_plan": info["plan_readiness"]["can_build_full_plan"],
                    "execution_ms": elapsed,
                    "segments": _segments(state),
                })
            pooled.extend(rows)
            if seed is None:
                paired_rows[method] = rows
            runs.append({"seed": seed, "case_count": len(rows), "metrics": _metrics(rows)})
        segment_names = ("low_reserve", "high_or_unknown_debt_payment", "unfinished_goal",
                         "expenses_at_or_above_income")
        methods[method] = {
            "run_count": len(runs), "evaluations": len(pooled), "metrics": _metrics(pooled),
            "runs": runs,
            "segments": {name: {
                "case_count": sum(name in _segments(state) for state in states),
                "mean_reward": round(statistics.mean(row["reward"] for row in pooled
                                                     if name in row["segments"]), 4),
                "critical_miss_rate": round(statistics.mean(row["missed_critical"] for row in pooled
                                                           if name in row["segments"]), 4),
            } for name in segment_names if any(name in row["segments"] for row in pooled)},
        }
    return {
        "evaluation_version": EVALUATION_VERSION,
        "scenario_version": SCENARIO_VERSION,
        "observation_version": OBSERVATION_VERSION,
        "action_version": ACTION_VERSION,
        "reward_version": REWARD_VERSION,
        "cohort": {"seed": scenario_seed, "case_count": len(states),
                   "sha256": cohort_digest, "fingerprints": fingerprints,
                   "source": "generated scenarios; no saved profiles or observed outcomes"},
        "random_seeds": list(random_seeds), "methods": methods,
        "paired_rl_vs_rule": _paired_summary(paired_rows["rule_based"], paired_rows["rl"]),
        "metric_definitions": {
            "mean_reward": "Mean selection-proxy-v1 points per selection; random pools all seeded runs.",
            "reward_variance": "Population variance of per-case proxy rewards; random pools all seeded runs.",
            "critical_miss_rate": "Share of selections missing at least one reward-defined critical agent.",
            "relevant_coverage_rate": "Selected relevant agents divided by all reward-defined relevant agents.",
            "risk_coverage_rate": "Share selecting the risk agent; risk is relevant in every generated case.",
            "goal_alignment_rate": "Share selecting goal agent among cases with an unfinished goal.",
            "mean_agent_calls": "Mean number of selected agents per selection; this is a call count, not a monetary cost.",
            "full_plan_rate": "Share selecting every agent required by the current rule-based plan.",
            "mean_execution_ms": "Mean wall-clock policy selection plus agent execution on this machine; model load excluded.",
            "mean_reward_delta": "Mean of paired DQN reward minus rule reward on the same cases, in proxy points; positive favors DQN under this reward only.",
            "mean_agent_call_delta": "Mean of paired DQN selected-agent count minus rule count on the same cases.",
        },
        "limitations": {
            "recommendation_consistency": "not measured",
            "recommendation_conflicts": "not measured",
            "reason": "The experiment scores selection and agent execution; no validated recommendation comparison or conflict ontology exists.",
            "reward_bias": "The proxy reward shares criteria with the rule-based selector and is not a financial outcome.",
            "scenario_bias": "Generated cases come from one hand-designed generator, not real household data.",
        },
    }


def read_evaluation_report(path: Path = DEFAULT_ARTIFACT_DIR / REPORT_FILENAME) -> dict:
    """Serve only a report matching the installed model and evaluation schema."""
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        metadata = verified_metadata(DEFAULT_ARTIFACT_DIR)
        expected = {"evaluation_version": EVALUATION_VERSION,
                    "scenario_version": SCENARIO_VERSION,
                    "observation_version": OBSERVATION_VERSION,
                    "action_version": ACTION_VERSION,
                    "reward_version": REWARD_VERSION,
                    "model_sha256": metadata["artifact_sha256"]}
        if any(report.get(key) != value for key, value in expected.items()):
            raise ValueError("Evaluation artifact is stale.")
        cohort = report["cohort"]
        if (cohort["case_count"] != len(cohort["fingerprints"]) or
                len(set(cohort["fingerprints"])) != cohort["case_count"] or
                hashlib.sha256("\n".join(cohort["fingerprints"]).encode()).hexdigest() != cohort["sha256"] or
                cohort["fingerprints"] != [state.fingerprint() for state in
                                          generate_scenarios(cohort["case_count"], seed=cohort["seed"])] or
                cohort["seed"] in metadata["split_seeds"].values()):
            raise ValueError("Evaluation cohort is invalid.")
        if set(report["methods"]) != {"random", "rule_based", "rl"}:
            raise ValueError("Evaluation methods are incomplete.")
        for method, item in report["methods"].items():
            if (item["run_count"] != len(item["runs"]) or
                    item["evaluations"] != cohort["case_count"] * item["run_count"] or
                    item["run_count"] != (len(report["random_seeds"]) if method == "random" else 1)):
                raise ValueError("Evaluation run counts are invalid.")
            metrics = item["metrics"]
            for key in ("mean_reward", "reward_variance", "critical_miss_rate",
                        "relevant_coverage_rate", "risk_coverage_rate", "mean_agent_calls",
                        "full_plan_rate", "mean_execution_ms"):
                if isinstance(metrics.get(key), bool) or not isinstance(metrics.get(key), (int, float)) or not math.isfinite(metrics[key]):
                    raise ValueError("Evaluation metrics are invalid.")
            for key in ("critical_miss_rate", "relevant_coverage_rate", "risk_coverage_rate",
                        "full_plan_rate"):
                if not 0 <= metrics[key] <= 1:
                    raise ValueError("Evaluation rates are invalid.")
        paired = report["paired_rl_vs_rule"]
        def validate_pair_counts(item, case_count):
            if (type(item.get("case_count")) is not int or item["case_count"] != case_count or
                    any(type(item.get(key)) is not int or not 0 <= item[key] <= case_count
                        for key in ("rl_higher_score_count", "equal_score_count",
                                    "rl_lower_score_count")) or
                    sum(item[key] for key in ("rl_higher_score_count", "equal_score_count",
                                              "rl_lower_score_count")) != case_count or
                    type(item.get("mean_reward_delta")) not in (int, float) or
                    not math.isfinite(item["mean_reward_delta"])):
                raise ValueError("Paired comparison is invalid.")

        validate_pair_counts(paired, cohort["case_count"])
        for key in ("same_selection_count", "rl_partial_plan_count"):
            if type(paired.get(key)) is not int or not 0 <= paired[key] <= cohort["case_count"]:
                raise ValueError("Paired comparison is invalid.")
        if (type(paired.get("mean_agent_call_delta")) not in (int, float) or
                not math.isfinite(paired["mean_agent_call_delta"]) or
                abs(paired["mean_reward_delta"] - (
                    report["methods"]["rl"]["metrics"]["mean_reward"] -
                    report["methods"]["rule_based"]["metrics"]["mean_reward"])) > 0.0002 or
                abs(paired["mean_agent_call_delta"] - (
                    report["methods"]["rl"]["metrics"]["mean_agent_calls"] -
                    report["methods"]["rule_based"]["metrics"]["mean_agent_calls"])) > 0.0002):
            raise ValueError("Paired comparison is invalid.")
        if set(paired["segments"]) != set(report["methods"]["rule_based"]["segments"]):
            raise ValueError("Paired segments are invalid.")
        for name, item in paired["segments"].items():
            count = report["methods"]["rule_based"]["segments"][name]["case_count"]
            validate_pair_counts(item, count)
            if abs(item["mean_reward_delta"] - (
                    report["methods"]["rl"]["segments"][name]["mean_reward"] -
                    report["methods"]["rule_based"]["segments"][name]["mean_reward"])) > 0.0002:
                raise ValueError("Paired segments are invalid.")
        return {"status": "available", "report": report}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "reason": "Evaluation report is missing or does not match the installed model."}


def main():
    parser = argparse.ArgumentParser(description="Evaluate Random, Rule-Based, and DQN on one fixed generated cohort.")
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_DIR / REPORT_FILENAME)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--random-seeds", type=int, nargs="+", default=DEFAULT_RANDOM_SEEDS)
    args = parser.parse_args()
    metadata = verified_metadata(DEFAULT_ARTIFACT_DIR)
    if args.seed in metadata["split_seeds"].values():
        parser.error("The evaluation seed must differ from training, validation, and test seeds.")
    model = load_dqn_artifact(DEFAULT_ARTIFACT_DIR)
    states = generate_scenarios(args.cases, seed=args.seed)
    evaluation_fingerprints = {state.fingerprint() for state in states}
    for split in ("training", "validation", "test"):
        earlier = generate_scenarios(metadata["split_counts"][split],
                                     seed=metadata["split_seeds"][split])
        if evaluation_fingerprints.intersection(state.fingerprint() for state in earlier):
            parser.error(f"Evaluation scenarios overlap the {split} split.")
    report = evaluate_cohort(states, model,
                             scenario_seed=args.seed, random_seeds=args.random_seeds)
    report["cohort"]["disjoint_from_training_validation_test"] = True
    report["model_sha256"] = metadata["artifact_sha256"]
    report["runtime"] = {"python": platform.python_version(), "platform": platform.platform()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "case_count": args.cases,
                      "methods": {name: item["metrics"] for name, item in report["methods"].items()}}, indent=2))


if __name__ == "__main__":
    main()
