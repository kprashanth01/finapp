"""Conflict labels and resolutions must come from real selected-agent evidence."""

import json
from hashlib import sha256

import pytest

from app.rl.conflict_experiment import (
    ConflictScenario, detect_conflicts, load_conflict_scenarios,
    run_conflict_experiment, write_conflict_experiment,
)
from app.rl.dynamic_experiment import load_committed_test_episodes


class FixedPolicy:
    def predict(self, observation, deterministic):
        assert deterministic is True
        return 0, None


@pytest.fixture(scope="module")
def completed_cases():
    episodes, _ = load_committed_test_episodes()
    return run_conflict_experiment(episodes[0], load_conflict_scenarios(),
                                   model=FixedPolicy())


def test_three_conflicts_use_actual_proposals_and_verified_rule_resolutions(completed_cases):
    summary = completed_cases["summary"]
    assert summary["synthetic_id"] == 257
    assert [case["scenario"]["expected_conflict"] for case in summary["cases"]] == [
        "reserve_vs_goal", "debt_vs_goal", "investment_vs_goal"]
    expected = ("reserve_first", "debt_review_hold", "goal_before_investment")
    for case, mechanism in zip(summary["cases"], expected, strict=True):
        reference = case["reference_conflicts"][0]
        assert reference["code"] == case["scenario"]["expected_conflict"]
        assert {ref["agent_id"] for ref in reference["source_refs"]} == set(reference["agent_ids"])
        rule = case["methods"]["rule_based"]
        assert rule["recommendation"]["status"] == "complete"
        assert rule["reference_conflict_outcomes"][0]["resolution"]["status"] == "resolved_by_coordinator"
        assert rule["reference_conflict_outcomes"][0]["resolution"]["mechanism"] == mechanism
        assert rule["observed_conflicts"] == case["reference_conflicts"]
        for method, result in case["methods"].items():
            assert [proposal["agent_id"] for proposal in result["agent_proposals"]] == result["selected_agents"]
            row = next(row for row in completed_cases["raw_reports"][case["scenario"]["name"]]["rows"]
                       if row["method"] == method)
            assert result["action"] == row["action"]
            assert result["reward"] == row["reward"]
            assert result["reward_components"] == row["reward_components"]
        fixed = case["methods"]["trained_rl"]
        assert fixed["selected_agents"] == ["budget"]
        assert fixed["observed_conflicts"] == []
        assert fixed["reference_conflict_outcomes"][0]["status"] == "not_observed"
        assert fixed["reference_conflict_outcomes"][0]["resolution"] is None
        assert fixed["recommendation"]["coordinated_plan"] is None


def test_detector_requires_the_agents_that_supply_each_claim(completed_cases):
    reserve = completed_cases["summary"]["cases"][0]
    proposals = reserve["methods"]["rule_based"]["agent_proposals"]
    assert [item["code"] for item in detect_conflicts(proposals)] == ["reserve_vs_goal"]
    assert detect_conflicts([item for item in proposals if item["agent_id"] != "goal"]) == []
    assert detect_conflicts([item for item in proposals if item["agent_id"] != "budget"]) == []
    with pytest.raises(ValueError, match="duplicate"):
        detect_conflicts([proposals[0], proposals[0]])


def test_output_is_checksummed_and_bad_scenario_labels_fail(completed_cases, tmp_path):
    path = write_conflict_experiment(completed_cases, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == completed_cases["summary"]
    for case in completed_cases["summary"]["cases"]:
        name = case["scenario"]["name"]
        raw = tmp_path / f"{name}.jsonl"
        assert sha256(raw.read_bytes()).hexdigest() == case["source"]["raw_rows_sha256"]
        assert len(raw.read_text(encoding="utf-8").splitlines()) == 3
    episodes, _ = load_committed_test_episodes()
    wrong = ConflictScenario.model_validate({
        **completed_cases["summary"]["cases"][0]["scenario"],
        "expected_conflict": "debt_vs_goal",
    })
    with pytest.raises(ValueError, match="did not produce"):
        run_conflict_experiment(episodes[0], (wrong,), model=FixedPolicy())
    config_path = tmp_path / "duplicate.json"
    config_path.write_text(json.dumps([wrong.model_dump(mode="json")] * 2), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_conflict_scenarios(config_path)
