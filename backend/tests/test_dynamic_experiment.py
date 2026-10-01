"""A paired monthly experiment must never vary its held-out states by policy."""

from collections import defaultdict
from hashlib import sha256
import json

import pytest

from app.rl.dynamic_experiment import run_paired_experiment, write_experiment
from app.rl.dynamic_scenarios import build_dynamic_episode_splits
from app.rl.selection import DEFAULT_CATALOG


class FixedPolicy:
    def predict(self, observation, deterministic):
        assert deterministic is True
        assert observation.shape == (19,)
        return 0, None


@pytest.fixture(scope="module")
def episodes():
    splits = build_dynamic_episode_splits(
        training_users=2, validation_users=2, test_users=2, months=2,
        population_seed=91, split_seed=92, selection_seed=93,
        trajectory_seed=94, shock_probability=0.2,
    )
    return splits


def test_every_method_uses_each_identical_test_month_and_real_agent_results(episodes):
    report = run_paired_experiment(episodes.test, model=FixedPolicy(), random_seed=17)
    assert len(report["rows"]) == 2 * 2 * 3
    assert report["manifest"]["decision_count_per_method"] == 4
    assert report["manifest"]["methods"] == ["random", "rule_based", "trained_rl"]
    grouped = defaultdict(dict)
    for row in report["rows"]:
        assert row["dataset_split"] == "test"
        assert row["selected_agents"] == list(DEFAULT_CATALOG.agents_for(row["action"]))
        assert [result["agent_id"] for result in row["agent_results"]] == row["selected_agents"]
        assert row["reward"] == pytest.approx(sum(row["reward_components"].values()))
        assert row["transition_source"] == "precomputed_exogenous_trajectory"
        assert row["agent_call_count"] == len(row["selected_agents"])
        grouped[row["synthetic_id"], row["month_index"]][row["method"]] = row
    assert len(grouped) == 4
    for methods in grouped.values():
        assert set(methods) == {"random", "rule_based", "trained_rl"}
        assert len({row["state_fingerprint"] for row in methods.values()}) == 1
        assert len({tuple(row["observation"]) for row in methods.values()}) == 1
        assert len({json.dumps(row["financial_state"], sort_keys=True) for row in methods.values()}) == 1
        assert methods["trained_rl"]["action"] == 0


def test_random_is_reproducible_and_training_users_are_rejected(episodes):
    first = run_paired_experiment(episodes.test, model=FixedPolicy(), random_seed=17)
    second = run_paired_experiment(episodes.test, model=FixedPolicy(), random_seed=17)
    assert [{key: value for key, value in row.items() if key != "execution_time_ns"}
            for row in first["rows"]] == [
                {key: value for key, value in row.items() if key != "execution_time_ns"}
                for row in second["rows"]]
    assert {key: value for key, value in first["manifest"].items() if key != "raw_rows_sha256"} == {
        key: value for key, value in second["manifest"].items() if key != "raw_rows_sha256"}
    with pytest.raises(ValueError, match="test"):
        run_paired_experiment(episodes.training, model=FixedPolicy())
    with pytest.raises(ValueError, match="duplicate"):
        run_paired_experiment((episodes.test[0], episodes.test[0]), model=FixedPolicy())


def test_raw_rows_and_manifest_are_written_only_after_complete_run(episodes, tmp_path):
    report = run_paired_experiment(episodes.test, model=FixedPolicy(), random_seed=17)
    output = tmp_path / "paired.jsonl"
    manifest = tmp_path / "paired.summary.json"
    write_experiment(report, output, manifest)
    assert [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] == report["rows"]
    assert json.loads(manifest.read_text(encoding="utf-8")) == report["manifest"]
    assert sha256(output.read_bytes()).hexdigest() == report["manifest"]["raw_rows_sha256"]
