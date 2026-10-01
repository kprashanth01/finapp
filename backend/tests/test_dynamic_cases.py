"""A monthly case must expose paired evidence without inventing agent findings."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json

import pytest

from app.advisory.state import GoalSnapshot
from app.rl.dynamic_cases import inspect_case, inspect_case_file
from app.rl.dynamic_experiment import run_paired_experiment, write_experiment
from app.rl.dynamic_scenarios import build_dynamic_episode_splits


class FixedPolicy:
    def __init__(self, action):
        self.action = action

    def predict(self, observation, deterministic):
        return self.action, None


@pytest.fixture(scope="module")
def small_experiment():
    episodes = build_dynamic_episode_splits(
        training_users=2, validation_users=2, test_users=2, months=2,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.2,
    ).test
    report = run_paired_experiment(episodes, model=FixedPolicy(0), random_seed=17)
    return episodes, report


def test_case_shows_same_state_each_method_and_real_outputs(small_experiment):
    episodes, report = small_experiment
    episode = episodes[0]
    case = inspect_case(report["rows"], report["manifest"], episodes,
                        synthetic_id=episode.profile.synthetic_id, month_index=1)
    assert case["user_state"]["synthetic_id"] == episode.profile.synthetic_id
    assert case["monthly_state"] == episode.months[0].model_dump(mode="json")
    assert case["source"]["raw_rows_sha256"] == report["manifest"]["raw_rows_sha256"]
    assert set(case["methods"]) == {"random", "rule_based", "trained_rl"}
    assert case["methods"]["trained_rl"]["action"] == 0
    for method, result in case["methods"].items():
        original = next(row for row in report["rows"] if row["method"] == method and
                        row["synthetic_id"] == episode.profile.synthetic_id and
                        row["month_index"] == 1)
        assert result["selected_agents"] == original["selected_agents"]
        assert result["agent_outputs"] == original["agent_results"]
        assert result["reward_components"] == original["reward_components"]
        assert result["reward"] == original["reward"]
        assert result["explanation"]
        if result["recommendation"]["status"] == "partial":
            assert result["recommendation"]["coordinated_plan"] is None
            assert result["conflicts_status"] == "not_assessed"
        else:
            assert result["recommendation"]["coordinated_plan"] is not None
            assert result["conflicts_status"] == "assessed"
    assert case["methods"]["trained_rl"]["recommendation"]["status"] == "partial"
    assert case["methods"]["rule_based"]["recommendation"]["status"] == "complete"


def test_full_plan_exposes_funding_conflict_from_computed_allocation(small_experiment):
    episodes, _ = small_experiment
    goal = GoalSnapshot(id=7, name="Course", target_amount=Decimal("999999999"),
                        saved_amount=Decimal("0"), target_date=date(2026, 11, 1),
                        priority="high")
    episode = replace(episodes[0], goals=(goal,))
    report = run_paired_experiment((episode,), model=FixedPolicy(62), random_seed=17)
    case = inspect_case(report["rows"], report["manifest"], (episode,),
                        synthetic_id=episode.profile.synthetic_id, month_index=1)
    trained = case["methods"]["trained_rl"]
    assert trained["recommendation"]["status"] == "complete"
    assert trained["conflicts_status"] == "assessed"
    assert any(item["code"] == "goal_funding_gap" for item in trained["conflicts"])
    assert trained["recommendation"]["coordinated_plan"]["monthly_plan"]["goal_allocations"]


def test_unknown_case_and_modified_trace_are_rejected(small_experiment, tmp_path):
    episodes, report = small_experiment
    with pytest.raises(ValueError, match="not in the paired test cohort"):
        inspect_case(report["rows"], report["manifest"], episodes,
                     synthetic_id=999999, month_index=1)
    raw = tmp_path / "paired.jsonl"
    write_experiment(report, raw)
    case = inspect_case_file(raw, synthetic_id=episodes[0].profile.synthetic_id,
                             month_index=1, episodes=episodes)
    assert case["user_state"]["synthetic_id"] == episodes[0].profile.synthetic_id
    raw.write_text(raw.read_text(encoding="utf-8") + json.dumps({"tampered": True}) + "\n",
                   encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        inspect_case_file(raw, synthetic_id=episodes[0].profile.synthetic_id,
                          month_index=1, episodes=episodes)
