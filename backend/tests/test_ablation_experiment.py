"""Ablations must preserve paired states and distinguish policy from execution changes."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.rl.ablation_experiment import (_agent_omission, run_ablation_experiment,
                                        write_ablation_experiment)
from app.rl.dynamic_scenarios import build_dynamic_episode_splits
from app.rl.variable_income_experiment import (ControlledScenario,
                                               build_scenario_episodes, load_scenarios)


class FixedPolicy:
    def predict(self, observation, deterministic):
        assert deterministic is True
        return 0, None


@pytest.fixture(scope="module")
def sample():
    episodes = build_dynamic_episode_splits(
        training_users=1, validation_users=1, test_users=2, months=3,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.1,
    ).test
    original = next(item for item in load_scenarios() if item.name == "B")
    baseline = ControlledScenario.model_validate({
        **original.model_dump(mode="json"), "shock_probability": 1,
    })
    report = run_ablation_experiment(
        episodes, baseline, model=FixedPolicy(), months=3,
        trajectory_seed=94, random_seed=17, agent="budget",
    )
    return episodes, baseline, report


def test_input_ablation_pairs_test_users_and_names_only_changed_inputs(sample):
    _, baseline, report = sample
    summary = report["summary"]
    assert summary["user_count"] == 2
    assert summary["baseline_scenario"]["name"] == "B"
    assert [item["ablation"] for item in summary["comparisons"]] == ["no_volatility", "no_shocks"]
    scenarios = summary["paired_scenarios"]
    assert [item["scenario"]["name"] for item in scenarios] == [
        "B", "B_no_volatility", "B_no_shocks"]
    assert len({item["trace"]["user_id_sha256"] for item in scenarios}) == 1
    assert all(item["trace"]["decision_count_per_method"] == 6 for item in scenarios)
    assert scenarios[0]["scenario"]["income_volatility"] == baseline.income_volatility
    assert scenarios[1]["scenario"]["income_volatility"] == 0
    assert scenarios[1]["scenario"]["shock_probability"] == 1
    assert scenarios[2]["scenario"]["income_volatility"] == baseline.income_volatility
    assert scenarios[2]["scenario"]["shock_probability"] == 0
    assert scenarios[0]["observed_event_months"]
    assert scenarios[2]["observed_event_months"] == {}
    for comparison in summary["comparisons"]:
        assert comparison["paired_behavior"]["changed_states"] > 0
        assert comparison["paired_behavior"]["methods"]["random"]["changed_actions"] == 0
        assert comparison["paired_behavior"]["methods"]["trained_rl"]["changed_actions"] == 0
        assert set(comparison["methods"]) == {"random", "rule_based", "trained_rl"}


def test_agent_omission_keeps_policy_action_even_when_no_agent_remains(sample):
    _, _, report = sample
    omission = report["summary"]["agent_omission"]
    assert omission["omitted_agent"] == "budget"
    assert omission["row_count"] == 18
    assert omission["execution_time"] == "not_measured_for_intervention"
    trained = [item for item in report["agent_omission_rows"]
               if item["method"] == "trained_rl"]
    assert len(trained) == 6
    assert all(item["policy_action"] == 0 and item["policy_selected_agents"] == ["budget"]
               and item["effective_agents"] == [] and item["effective_agent_results"] == []
               for item in trained)
    assert omission["methods"]["trained_rl"]["affected_decisions"] == 6
    assert omission["methods"]["trained_rl"]["mean_agent_calls_after"] == 0
    assert omission["methods"]["trained_rl"]["mean_reward_delta"] == pytest.approx(
        omission["methods"]["trained_rl"]["mean_reward_after"] -
        omission["methods"]["trained_rl"]["mean_reward_before"])


def test_written_rows_are_checksummed_and_tampering_is_rejected(sample, tmp_path):
    base_episodes, baseline, report = sample
    summary_path = write_ablation_experiment(report, tmp_path)
    assert json.loads(summary_path.read_text(encoding="utf-8")) == report["summary"]
    raw = tmp_path / "agent-omission.jsonl"
    assert sha256(raw.read_bytes()).hexdigest() == report["summary"]["agent_omission"]["raw_rows_sha256"]
    for name in ("B", "B_no_volatility", "B_no_shocks"):
        assert (tmp_path / f"{name}.jsonl").exists()
    episodes = build_scenario_episodes(base_episodes, baseline, months=3, trajectory_seed=94)
    changed = deepcopy(report["raw_reports"]["B"])
    changed["rows"][0]["reward"] += 1
    with pytest.raises(ValueError, match="baseline reward"):
        _agent_omission(episodes, changed, agent="budget")


def test_optional_ablation_selection_and_validation(sample):
    episodes, baseline, _ = sample
    report = run_ablation_experiment(episodes, baseline, model=FixedPolicy(),
                                     ablations=("omit_agent",), agent="budget",
                                     months=3, trajectory_seed=94, random_seed=17)
    assert report["summary"]["comparisons"] == []
    assert len(report["summary"]["paired_scenarios"]) == 1
    with pytest.raises(ValueError, match="distinct"):
        run_ablation_experiment(episodes, baseline, model=FixedPolicy(),
                                ablations=("no_shocks", "no_shocks"), months=3)
    with pytest.raises(ValueError, match="catalogue"):
        run_ablation_experiment(episodes, baseline, model=FixedPolicy(),
                                ablations=("omit_agent",), agent="nonexistent", months=3)
