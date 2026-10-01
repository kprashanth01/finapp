"""Monthly model management keeps evidence compatible and avoids repeat loads."""

import json

import pytest

pytest.importorskip("stable_baselines3")

from app.rl.dynamic_model_management import (
    DEFAULT_ARTIFACT_DIR, get_model_metadata, load_model, model_exists, save_model,
)


def test_committed_monthly_model_has_required_provenance():
    metadata = get_model_metadata()
    assert model_exists()
    assert metadata["model_name"] == "monthly-agent-selection-dqn"
    assert metadata["model_version"] == "dynamic-dqn-monthly-v1"
    assert metadata["training_date"]
    assert metadata["training_steps"] == metadata["selected_step"]
    assert metadata["environment_version"] == "dynamic-agent-selection-v1"
    assert metadata["seed"] == metadata["training_seed"]
    assert metadata["dataset_version"] == metadata["dataset"]["scenario_version"]


def test_save_load_and_cache_model_in_new_directory(tmp_path):
    assert not model_exists(tmp_path)
    source = load_model(DEFAULT_ARTIFACT_DIR)
    saved = save_model(source, get_model_metadata(), tmp_path)
    assert saved == get_model_metadata(tmp_path)
    assert model_exists(tmp_path)
    first = load_model(tmp_path)
    assert first is load_model(tmp_path)
    assert first.action_space.n == 63
    assert first.observation_space.shape == (19,)
    save_model(source, get_model_metadata(), tmp_path)
    assert load_model(tmp_path) is not first

    metadata_path = tmp_path / "dynamic_dqn_metadata.json"
    original = metadata_path.read_text(encoding="utf-8")
    changed = json.loads(original)
    changed["dataset_version"] = "incompatible"
    metadata_path.write_text(json.dumps(changed), encoding="utf-8")
    assert not model_exists(tmp_path)
    with pytest.raises(ValueError, match="schema|version"):
        load_model(tmp_path)
    metadata_path.write_text(original, encoding="utf-8")
    assert model_exists(tmp_path)

    model_path = tmp_path / "dynamic_dqn_policy.zip"
    model_path.write_bytes(model_path.read_bytes() + b"tampered")
    assert not model_exists(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        load_model(tmp_path)


def test_save_rejects_bad_metadata_before_writing(tmp_path):
    metadata = get_model_metadata()
    metadata["training_steps"] = 0
    with pytest.raises(ValueError, match="training"):
        save_model(load_model(), metadata, tmp_path)
    assert not model_exists(tmp_path)
