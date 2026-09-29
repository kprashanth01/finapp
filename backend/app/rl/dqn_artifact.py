"""Versioned research artifact checks without importing the training stack at API startup."""

import hashlib
import json
import math
from pathlib import Path

from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION
from app.rl.reward import REWARD_VERSION
from app.rl.scenarios import SCENARIO_VERSION
from app.rl.selection import ACTION_COUNT, ACTION_VERSION

MODEL_VERSION = "dqn-bandit-v1"
MODEL_FILENAME = "dqn_policy.zip"
METADATA_FILENAME = "dqn_metadata.json"
DEFAULT_ARTIFACT_DIR = Path(__file__).parent


def verified_metadata(directory: Path) -> dict:
    directory = Path(directory)
    metadata = json.loads((directory / METADATA_FILENAME).read_text(encoding="utf-8"))
    expected = {
        "model_version": MODEL_VERSION,
        "observation_version": OBSERVATION_VERSION,
        "action_version": ACTION_VERSION,
        "reward_version": REWARD_VERSION,
        "scenario_version": SCENARIO_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "action_count": ACTION_COUNT,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("DQN artifact schema or version is incompatible.")
    counts = metadata.get("split_counts")
    history = metadata.get("validation_history")
    final = metadata.get("test")
    if (metadata.get("algorithm") != "DQN" or not isinstance(counts, dict) or
            any(not isinstance(counts.get(key), int) or counts[key] < 1
                for key in ("training", "validation", "test")) or
            not isinstance(history, list) or not history or not isinstance(final, dict) or
            not isinstance(metadata.get("selected_step"), int) or
            not isinstance(metadata.get("total_timesteps"), int)):
        raise ValueError("DQN evidence metadata is incomplete.")
    for row in [*history, final]:
        if (not isinstance(row, dict) or
                any(not isinstance(row.get(key), (int, float)) or
                    not math.isfinite(row[key]) for key in
                    ("mean_reward", "critical_miss_rate")) or
                not 0 <= row["critical_miss_rate"] <= 1):
            raise ValueError("DQN evidence metrics are invalid.")
    if (metadata["selected_step"] not in [row.get("step") for row in history] or
            metadata["selected_step"] > metadata["total_timesteps"] or
            final.get("case_count") != counts["test"]):
        raise ValueError("DQN evidence checkpoint or test split is invalid.")
    digest = hashlib.sha256((directory / MODEL_FILENAME).read_bytes()).hexdigest()
    if digest != metadata.get("artifact_sha256"):
        raise ValueError("DQN model checksum mismatch.")
    return metadata


def read_training_evidence(directory: Path = DEFAULT_ARTIFACT_DIR) -> dict:
    """Read only trusted run metadata for Research; PyTorch is not required."""
    try:
        return {"status": "available", "metadata": verified_metadata(directory)}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "reason": "DQN training artifact is not installed or compatible."}


def load_dqn_artifact(directory: Path = DEFAULT_ARTIFACT_DIR):
    """Validate local artifact before loading a trusted repository model."""
    verified_metadata(directory)
    from stable_baselines3 import DQN

    model = DQN.load(Path(directory) / MODEL_FILENAME, device="cpu")
    if (model.action_space.n != ACTION_COUNT or
            tuple(model.observation_space.shape) != (len(FEATURE_NAMES),)):
        raise ValueError("DQN model spaces are incompatible with the current schema.")
    return model
