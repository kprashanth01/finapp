"""Research metrics are computed from paired evidence with explicit denominators."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import statistics

import pytest

from app.advisory.state import GoalSnapshot
from app.rl.dynamic_experiment import run_paired_experiment, write_experiment
from app.rl.dynamic_metrics import analyze_file, summarize_metrics
from app.rl.dynamic_scenarios import build_dynamic_episode_splits


class BudgetOnlyPolicy:
    def predict(self, observation, deterministic):
        return 0, None


@pytest.fixture(scope="module")
def test_episodes():
    return build_dynamic_episode_splits(
        training_users=2, validation_users=2, test_users=2, months=2,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.2,
    ).test


def test_measured_values_have_explicit_denominators_and_no_invented_goals(test_episodes):
    report = run_paired_experiment(test_episodes, model=BudgetOnlyPolicy(), random_seed=17)
    metrics = summarize_metrics(report["rows"], report["manifest"])
    assert metrics["cohort"]["user_count"] == 2
    assert metrics["cohort"]["decisions_per_method"] == 4
    assert metrics["cohort"]["trajectory_sha256"] == report["manifest"]["trajectory_sha256"]
    for method in ("random", "rule_based", "trained_rl"):
        rows = [row for row in report["rows"] if row["method"] == method]
        values = metrics["methods"][method]
        assert values["goal_alignment"]["status"] == "unavailable"
        assert values["goal_alignment"]["rate"] is None
        assert values["goal_alignment"]["eligible_goals"] == 0
        assert values["recommendation_consistency"]["status"] == "unavailable"
        assert values["recommendation_consistency"]["rate"] is None
        assert values["priority_action_provenance"]["rate"] == 1.0
        assert values["agent_efficiency"]["mean_agent_calls"] == pytest.approx(
            statistics.mean(row["agent_call_count"] for row in rows))
        assert values["average_reward"] == pytest.approx(statistics.mean(row["reward"] for row in rows))
        assert values["reward_variance"] == pytest.approx(
            statistics.pvariance(row["reward"] for row in rows))
        assert values["execution_time"]["mean_ms"] > 0
        risk_count = sum(len(set(row["reward_audit"]["critical_agents"]) &
                             {"budget", "debt", "emergency", "risk"}) for row in rows)
        covered = sum(len(set(row["reward_audit"]["critical_agents"]) &
                          set(row["selected_agents"]) &
                          {"budget", "debt", "emergency", "risk"}) for row in rows)
        assert values["risk_coverage"]["eligible_risks"] == risk_count
        assert values["risk_coverage"]["covered_risks"] == covered
        assert values["risk_coverage"]["rate"] == pytest.approx(covered / risk_count)


def test_goal_alignment_only_counts_unfinished_goals(test_episodes):
    goal = GoalSnapshot(id=1, name="Course", target_amount=Decimal("1200"),
                        saved_amount=Decimal("100"), target_date=date(2027, 1, 1),
                        priority="high")
    episode = replace(test_episodes[0], goals=(goal,))
    report = run_paired_experiment((episode,), model=BudgetOnlyPolicy(), random_seed=17)
    metrics = summarize_metrics(report["rows"], report["manifest"])
    assert metrics["methods"]["rule_based"]["goal_alignment"]["rate"] == 1.0
    assert metrics["methods"]["trained_rl"]["goal_alignment"]["rate"] == 0.0
    assert metrics["methods"]["trained_rl"]["goal_alignment"]["eligible_goals"] == 2


def test_priority_provenance_inconsistency_is_counted(test_episodes):
    report = run_paired_experiment(test_episodes[:1], model=BudgetOnlyPolicy(), random_seed=17)
    rows = [dict(row) for row in report["rows"]]
    target = next(row for row in rows if row["method"] == "trained_rl")
    target["priority_actions"] = [{"agent_id": "debt", "finding_code": "invented"}]
    metrics = summarize_metrics(rows, report["manifest"])
    assert metrics["methods"]["trained_rl"]["priority_action_provenance"]["consistent_decisions"] == 1
    assert metrics["methods"]["trained_rl"]["priority_action_provenance"]["rate"] == 0.5


def test_unpaired_or_unmeasured_inputs_are_rejected(test_episodes):
    report = run_paired_experiment(test_episodes[:1], model=BudgetOnlyPolicy(), random_seed=17)
    with pytest.raises(ValueError, match="paired"):
        summarize_metrics(report["rows"][:-1], report["manifest"])
    rows = [dict(row) for row in report["rows"]]
    rows[0].pop("execution_time_ns")
    with pytest.raises(ValueError, match="execution_time_ns"):
        summarize_metrics(rows, report["manifest"])


def test_file_analysis_checks_raw_checksum(test_episodes, tmp_path):
    report = run_paired_experiment(test_episodes[:1], model=BudgetOnlyPolicy(), random_seed=17)
    raw = tmp_path / "paired.jsonl"
    write_experiment(report, raw)
    assert analyze_file(raw)["cohort"]["decisions_per_method"] == 2
    raw.write_bytes(raw.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        analyze_file(raw)
