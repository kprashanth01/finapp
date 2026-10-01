"""Controlled scenario inputs must yield comparable, reproducible test decisions."""

import json
from hashlib import sha256

import pytest

from app.rl.dynamic_scenarios import build_dynamic_episode_splits
from app.rl.trajectories import ShockConfig, generate_trajectory
from app.rl.variable_income_experiment import (
    ControlledScenario, build_scenario_episodes, load_scenarios,
    run_controlled_experiment, write_controlled_experiment,
)


class FixedPolicy:
    def predict(self, observation, deterministic):
        assert deterministic is True
        assert observation.shape == (19,)
        return 0, None


@pytest.fixture(scope="module")
def held_out():
    return build_dynamic_episode_splits(
        training_users=1, validation_users=1, test_users=2, months=3,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.1,
    ).test


def test_scheduled_shock_is_reproducible_and_validated(held_out):
    profile = held_out[0].profile
    config = ShockConfig(probability=0, forced_events=((2, "temporary_income_loss"),))
    first = generate_trajectory(profile, months=3, seed=94, shock_config=config)
    second = generate_trajectory(profile, months=3, seed=94, shock_config=config)
    assert first == second
    assert [month.event_type for month in first] == [None, "temporary_income_loss", "temporary_income_loss"]
    assert first[1].income == 0
    with pytest.raises(ValueError, match="distinct"):
        ShockConfig(forced_events=((2, "low_income"), (2, "high_income")))
    with pytest.raises(ValueError, match="outside"):
        generate_trajectory(profile, months=1, shock_config=config)


def test_named_scenarios_change_finances_and_keep_methods_paired(held_out, tmp_path):
    scenarios = load_scenarios()
    assert [scenario.name for scenario in scenarios] == list("ABCDE")
    assert len({scenario.income_volatility for scenario in scenarios}) > 1
    episode_a = build_scenario_episodes(held_out, scenarios[0], months=3, trajectory_seed=94)
    episode_c = build_scenario_episodes(held_out, scenarios[2], months=3, trajectory_seed=94)
    assert [item.profile.synthetic_id for item in episode_a] == [item.profile.synthetic_id for item in episode_c]
    assert episode_c[0].months[1].simulated_event_type == "temporary_income_loss"
    assert episode_c[0].months[1].monthly_income == 0
    assert episode_c[0].months[1].scheduled_emi > episode_a[0].months[1].scheduled_emi
    assert episode_c[0].goals[0].target_amount == 100000

    report = run_controlled_experiment(held_out, (scenarios[0], scenarios[2]),
                                       model=FixedPolicy(), months=3,
                                       trajectory_seed=94, random_seed=17)
    summary = report["summary"]
    assert summary["user_count"] == 2
    assert summary["source_user_id_sha256"] == summary["scenarios"][0]["trace"]["user_id_sha256"]
    assert [item["scenario"]["name"] for item in summary["scenarios"]] == ["A", "C"]
    changed = summary["scenarios"][1]["behavior_vs_first_scenario"]
    assert changed["changed_states"] == 6
    assert changed["changed_observations"] == 6
    assert changed["methods"]["random"]["changed_actions"] == 0
    assert changed["methods"]["trained_rl"]["changed_actions"] == 0
    assert changed["paired_decisions"] == 6
    assert summary["scenarios"][1]["observed_event_months"] == {"temporary_income_loss": 4}
    for item in summary["scenarios"]:
        assert item["trace"]["row_count"] == 18
        assert set(item["metrics"]) == {"random", "rule_based", "trained_rl"}
        assert item["action_distribution"]["trained_rl"] == [
            {"action": 0, "selected_agents": ["budget"], "count": 6}]

    path = write_controlled_experiment(report, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == summary
    for name in ("A", "C"):
        raw_path = tmp_path / f"{name}.jsonl"
        assert len(raw_path.read_text(encoding="utf-8").splitlines()) == 18
        assert sha256(raw_path.read_bytes()).hexdigest() == report["raw_reports"][name]["manifest"]["raw_rows_sha256"]


def test_one_input_can_be_changed_without_replacing_the_test_users(held_out):
    baseline = load_scenarios()[0]
    varied = ControlledScenario.model_validate({
        **baseline.model_dump(mode="json"), "name": "A_volatility",
        "income_volatility": 0.35,
    })
    original = build_scenario_episodes(held_out, baseline, months=3, trajectory_seed=94)
    modified = build_scenario_episodes(held_out, varied, months=3, trajectory_seed=94)
    for left, right in zip(original, modified, strict=True):
        assert left.profile.synthetic_id == right.profile.synthetic_id
        assert left.profile.monthly_expenses == right.profile.monthly_expenses
        assert left.profile.existing_debt == right.profile.existing_debt
        assert left.profile.emergency_fund == right.profile.emergency_fund
        assert left.profile.income_volatility != right.profile.income_volatility
        assert [month.monthly_income for month in left.months] != [month.monthly_income for month in right.months]


def test_invalid_configurations_are_rejected(held_out, tmp_path):
    data = load_scenarios()[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="must include"):
        ControlledScenario.model_validate({**data, "expenses_to_monthly_income": 0.01})
    with pytest.raises(ValueError, match="together"):
        ControlledScenario.model_validate({**data, "goal_amount": "100.00"})
    with pytest.raises(ValueError, match="outside"):
        build_scenario_episodes(held_out, ControlledScenario.model_validate(
            {**data, "forced_events": [[4, "low_income"]]}), months=3, trajectory_seed=94)
    config_path = tmp_path / "scenarios.json"
    config_path.write_text(json.dumps([data, data]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_scenarios(config_path)
