"""A monthly DQN run must select on validation users and preserve test evidence."""

import json

import pytest

pytest.importorskip("stable_baselines3")

from app.rl.dynamic_training import (DynamicTrainingConfig, load_dynamic_dqn,
                                     run_dynamic_training, verified_dynamic_metadata)
from app.rl.dynamic_scenarios import build_dynamic_episode_splits
from app.rl.dynamic_environment import DynamicAgentSelectionEnv


def test_monthly_dqn_checkpoint_and_reloaded_policy(tmp_path):
    config = DynamicTrainingConfig(training_users=8, validation_users=4, test_users=4,
                                   months=2, total_timesteps=64, validation_interval=32,
                                   population_seed=91, split_seed=92, selection_seed=93,
                                   trajectory_seed=94, seed=7)
    metadata = run_dynamic_training(tmp_path, config)
    assert metadata["algorithm"] == "DQN"
    assert metadata["split_counts"] == {"training": 8, "validation": 4, "test": 4}
    assert [row["step"] for row in metadata["validation_history"]] == [32, 64]
    assert metadata["selected_step"] in {32, 64}
    assert metadata["gradient_updates"] > 0
    assert metadata["test"]["episode_count"] == 4
    assert metadata["test"]["decision_count"] == 8
    assert verified_dynamic_metadata(tmp_path) == metadata
    episodes = build_dynamic_episode_splits(training_users=8, validation_users=4, test_users=4,
                                            months=2, population_seed=91, split_seed=92,
                                            selection_seed=93, trajectory_seed=94)
    env = DynamicAgentSelectionEnv(episodes.test)
    observation, _ = env.reset(options={"episode_index": 0})
    action, _ = load_dynamic_dqn(tmp_path).predict(observation, deterministic=True)
    assert env.action_space.contains(int(action))


def test_monthly_dqn_rejects_schema_and_checksum_changes(tmp_path):
    config = DynamicTrainingConfig(training_users=4, validation_users=2, test_users=2,
                                   months=2, total_timesteps=32, validation_interval=32)
    run_dynamic_training(tmp_path, config)
    path = tmp_path / "dynamic_dqn_metadata.json"
    original = path.read_text(encoding="utf-8")
    changed = json.loads(original)
    changed["observation_version"] = "obsolete"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="schema|version"):
        load_dynamic_dqn(tmp_path)
    path.write_text(original, encoding="utf-8")
    model_path = tmp_path / "dynamic_dqn_policy.zip"
    model_path.write_bytes(model_path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_dynamic_dqn(tmp_path)


def test_monthly_training_requires_exact_checkpoint_steps():
    with pytest.raises(ValueError, match="multiples of four"):
        DynamicTrainingConfig(total_timesteps=33, validation_interval=20)
