"""Versioned, checksum-verified storage for the offline monthly DQN policy.

Metadata operations do not import PyTorch or deserialize a policy. Loading is
cached per artifact digest, so repeated inference requests reuse one DQN.
"""

import argparse
from datetime import date
from functools import lru_cache
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.rl.dynamic_environment import DYNAMIC_ENVIRONMENT_VERSION
from app.rl.dynamic_reward import DYNAMIC_REWARD_VERSION
from app.rl.dynamic_scenarios import DYNAMIC_SCENARIO_VERSION
from app.rl.dynamic_state import DYNAMIC_FEATURE_NAMES, DYNAMIC_OBSERVATION_VERSION
from app.rl.selection import ACTION_COUNT, ACTION_VERSION


MODEL_NAME = "monthly-agent-selection-dqn"
MODEL_VERSION = "dynamic-dqn-monthly-v1"
MODEL_FILENAME = "dynamic_dqn_policy.zip"
METADATA_FILENAME = "dynamic_dqn_metadata.json"
DEFAULT_ARTIFACT_DIR = Path(__file__).parent / "dynamic_model"
_model_lock = RLock()


def _positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_metadata(metadata: dict) -> None:
    expected = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "environment_version": DYNAMIC_ENVIRONMENT_VERSION,
        "observation_version": DYNAMIC_OBSERVATION_VERSION,
        "action_version": ACTION_VERSION,
        "reward_version": DYNAMIC_REWARD_VERSION,
        "scenario_version": DYNAMIC_SCENARIO_VERSION,
        "dataset_version": DYNAMIC_SCENARIO_VERSION,
        "feature_names": list(DYNAMIC_FEATURE_NAMES),
        "action_count": ACTION_COUNT,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("Dynamic DQN artifact schema or version is incompatible.")
    try:
        training_date = metadata["training_date"]
        if not isinstance(training_date, str) or date.fromisoformat(training_date).isoformat() != training_date:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Dynamic DQN training date is missing or invalid.") from error
    counts = metadata.get("split_counts")
    dataset = metadata.get("dataset")
    history = metadata.get("validation_history")
    final = metadata.get("test")
    if (metadata.get("algorithm") != "DQN" or not isinstance(counts, dict) or
            any(not _positive_int(counts.get(role)) for role in ("training", "validation", "test")) or
            not isinstance(dataset, dict) or dataset.get("scenario_version") != DYNAMIC_SCENARIO_VERSION or
            dataset.get("user_counts") != counts or not _positive_int(dataset.get("months_per_user")) or
            not isinstance(history, list) or not history or not isinstance(final, dict) or
            not _positive_int(metadata.get("training_steps")) or
            not _positive_int(metadata.get("total_timesteps")) or
            not isinstance(metadata.get("seed"), int) or isinstance(metadata.get("seed"), bool) or
            metadata.get("seed") != metadata.get("training_seed") or
            metadata.get("selected_step") != metadata["training_steps"] or
            metadata["training_steps"] > metadata["total_timesteps"]):
        raise ValueError("Dynamic DQN training evidence is incomplete.")
    for row in [*history, final]:
        if (not isinstance(row, dict) or
                any(not isinstance(row.get(key), (int, float)) or isinstance(row.get(key), bool) or
                    not math.isfinite(row[key]) for key in
                    ("mean_reward", "critical_miss_rate", "mean_agent_calls")) or
                not 0 <= row["critical_miss_rate"] <= 1):
            raise ValueError("Dynamic DQN evaluation metrics are invalid.")
    if (metadata["training_steps"] not in [row.get("step") for row in history] or
            final.get("episode_count") != counts["test"] or
            final.get("decision_count") != counts["test"] * dataset.get("months_per_user", 0)):
        raise ValueError("Dynamic DQN checkpoint or test split is invalid.")


def get_model_metadata(directory: Path = DEFAULT_ARTIFACT_DIR) -> dict:
    """Return validated provenance after checking the local ZIP digest."""
    directory = Path(directory)
    metadata = json.loads((directory / METADATA_FILENAME).read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Dynamic DQN metadata must be a JSON object.")
    _validate_metadata(metadata)
    if sha256((directory / MODEL_FILENAME).read_bytes()).hexdigest() != metadata.get("artifact_sha256"):
        raise ValueError("Dynamic DQN model checksum mismatch.")
    return metadata


def model_exists(directory: Path = DEFAULT_ARTIFACT_DIR) -> bool:
    """Check presence and compatibility without importing the RL training stack."""
    try:
        get_model_metadata(directory)
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


@lru_cache(maxsize=8)
def _load_checked_model(directory: Path, digest: str):
    from stable_baselines3 import DQN

    model_path = directory / MODEL_FILENAME
    model = DQN.load(model_path, device="cpu")
    if (model.action_space.n != ACTION_COUNT or
            tuple(model.observation_space.shape) != (len(DYNAMIC_FEATURE_NAMES),)):
        raise ValueError("Dynamic DQN model spaces are incompatible with the current schema.")
    if sha256(model_path.read_bytes()).hexdigest() != digest:
        raise ValueError("Dynamic DQN model changed while loading.")
    return model


def load_model(directory: Path = DEFAULT_ARTIFACT_DIR):
    """Reuse one verified model instance for each model file digest and directory."""
    directory = Path(directory).resolve()
    with _model_lock:
        metadata = get_model_metadata(directory)
        return _load_checked_model(directory, metadata["artifact_sha256"])


def save_model(model, metadata: dict, directory: Path = DEFAULT_ARTIFACT_DIR) -> dict:
    """Save a policy and its evidence, replacing only complete individual files."""
    with _model_lock:
        return _save_model(model, metadata, directory)


def _save_model(model, metadata: dict, directory: Path) -> dict:
    if (model.action_space.n != ACTION_COUNT or
            tuple(model.observation_space.shape) != (len(DYNAMIC_FEATURE_NAMES),)):
        raise ValueError("Dynamic DQN model spaces are incompatible with the current schema.")
    payload = dict(metadata)
    _validate_metadata(payload)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    nonce = uuid4().hex
    pending_model = directory / f".{nonce}.zip"
    pending_metadata = directory / f".{nonce}.json"
    try:
        model.save(pending_model)
        payload["artifact_sha256"] = sha256(pending_model.read_bytes()).hexdigest()
        pending_metadata.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(pending_model, directory / MODEL_FILENAME)
        os.replace(pending_metadata, directory / METADATA_FILENAME)
    finally:
        pending_model.unlink(missing_ok=True)
        pending_metadata.unlink(missing_ok=True)
    _load_checked_model.cache_clear()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the saved monthly DQN without loading PyTorch.")
    parser.add_argument("--directory", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    metadata = get_model_metadata(args.directory)
    keys = ("model_name", "model_version", "training_date", "training_steps",
            "environment_version", "seed", "dataset_version", "artifact_sha256")
    print(json.dumps({key: metadata[key] for key in keys}, indent=2))


if __name__ == "__main__":
    main()
