"""The research DQN must learn from environment steps and reload safely."""

import json

import pytest

pytest.importorskip("stable_baselines3")

from app.rl.dqn_artifact import load_dqn_artifact, read_training_evidence
from app.rl.dqn_training import TrainingConfig, run_training
from app.rl.observation import encode_observation
from app.rl.scenarios import generate_scenarios
from app.rl.selection import ACTION_COUNT


def test_bounded_dqn_training_saves_a_predictable_policy(tmp_path):
    config = TrainingConfig(training_cases=24, validation_cases=8, test_cases=8,
                            total_timesteps=64, validation_interval=32, seed=7)
    metadata = run_training(tmp_path, config)
    assert metadata["algorithm"] == "DQN"
    assert metadata["scenario_source"] == "generated coverage cases; no saved profiles"
    assert metadata["split_counts"] == {"training": 24, "validation": 8, "test": 8}
    assert [row["step"] for row in metadata["validation_history"]] == [32, 64]
    assert metadata["selected_step"] in {32, 64}
    assert metadata["gradient_updates"] > 0
    assert metadata["test"]["case_count"] == 8
    assert -5 <= metadata["test"]["mean_reward"] <= 10
    assert read_training_evidence(tmp_path)["status"] == "available"

    model = load_dqn_artifact(tmp_path)
    observation = encode_observation(generate_scenarios(1, seed=91)[0])
    action, _ = model.predict(observation, deterministic=True)
    assert 0 <= int(action) < ACTION_COUNT


def test_dqn_artifact_rejects_tampering_and_schema_mismatch(tmp_path):
    config = TrainingConfig(training_cases=16, validation_cases=4, test_cases=4,
                            total_timesteps=32, validation_interval=32, seed=11)
    run_training(tmp_path, config)
    metadata_path = tmp_path / "dqn_metadata.json"
    original = metadata_path.read_text(encoding="utf-8")
    payload = json.loads(original)
    payload["observation_version"] = "unknown"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema|version"):
        load_dqn_artifact(tmp_path)

    payload = json.loads(original)
    payload.pop("test")
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")
    assert read_training_evidence(tmp_path)["status"] == "unavailable"

    metadata_path.write_text(original, encoding="utf-8")
    model_path = tmp_path / "dqn_policy.zip"
    model_path.write_bytes(model_path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_dqn_artifact(tmp_path)
    assert read_training_evidence(tmp_path)["status"] == "unavailable"


def test_missing_training_artifact_has_a_clear_unavailable_state(tmp_path):
    evidence = read_training_evidence(tmp_path)
    assert evidence["status"] == "unavailable"
    assert "not installed" in evidence["reason"].lower()


def test_training_rejects_step_counts_that_would_misreport_checkpoint_positions():
    with pytest.raises(ValueError, match="multiples of four"):
        TrainingConfig(total_timesteps=33, validation_interval=20)
