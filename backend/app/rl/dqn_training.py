"""Reproducible, offline DQN training for one-step agent selection."""

import argparse
import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path

import gymnasium
import numpy as np
import stable_baselines3
import torch
from stable_baselines3 import DQN
from stable_baselines3.common.env_checker import check_env

from app.rl.dqn_artifact import (DEFAULT_ARTIFACT_DIR, METADATA_FILENAME,
                                 MODEL_FILENAME, MODEL_VERSION)
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION, encode_observation
from app.rl.reward import REWARD_VERSION
from app.rl.scenarios import SCENARIO_VERSION, build_splits
from app.rl.selection import ACTION_COUNT, ACTION_VERSION


@dataclass(frozen=True)
class TrainingConfig:
    training_cases: int = 1536
    validation_cases: int = 384
    test_cases: int = 384
    total_timesteps: int = 12000
    validation_interval: int = 3000
    seed: int = 137
    training_seed: int = 20260929
    validation_seed: int = 20260930
    test_seed: int = 20261001

    def __post_init__(self):
        if (min(self.training_cases, self.validation_cases, self.test_cases,
                self.total_timesteps, self.validation_interval) < 1 or
                self.validation_interval > self.total_timesteps):
            raise ValueError("Training needs positive split sizes and a valid validation interval.")
        if self.total_timesteps % 4 or self.validation_interval % 4:
            raise ValueError("Training and validation step counts must be multiples of four.")


def evaluate_model(model: DQN, states) -> dict:
    rewards, misses, calls = [], [], []
    for state in states:
        environment = AgentSelectionEnv(state)
        observation, _ = environment.reset()
        action, _ = model.predict(observation, deterministic=True)
        _, reward, terminated, truncated, info = environment.step(int(action))
        if not terminated or truncated or not np.isfinite(reward):
            raise ValueError("The selection environment returned an invalid result.")
        rewards.append(reward)
        misses.append(bool(info["reward_audit"]["missed_critical_agents"]))
        calls.append(len(info["selected_agents"]))
    return {
        "case_count": len(states),
        "mean_reward": round(float(np.mean(rewards)), 3),
        "critical_miss_rate": round(float(np.mean(misses)), 4),
        "mean_agent_calls": round(float(np.mean(calls)), 3),
    }


def run_training(output_dir: Path, config: TrainingConfig = TrainingConfig()) -> dict:
    """Train on sampled transitions, choose by validation, test the choice once."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    splits = build_splits(
        training_count=config.training_cases, validation_count=config.validation_cases,
        test_count=config.test_cases, training_seed=config.training_seed,
        validation_seed=config.validation_seed, test_seed=config.test_seed,
    )
    check_env(AgentSelectionEnv(splits.training), warn=False)
    torch.set_num_threads(1)
    environment = AgentSelectionEnv(splits.training)
    model = DQN(
        "MlpPolicy", environment, seed=config.seed, device="cpu", verbose=0,
        learning_rate=0.001, buffer_size=max(1000, config.total_timesteps),
        learning_starts=min(256, max(4, config.total_timesteps // 10)),
        batch_size=32, train_freq=4, gradient_steps=1, gamma=0.0,
        exploration_fraction=0.5, exploration_final_eps=0.05,
        policy_kwargs={"net_arch": [64, 64]},
    )
    candidate_path = output_dir / "dqn_candidate.zip"
    validation_history = []
    selected_step = None
    selected_score = float("-inf")
    for target_step in range(config.validation_interval, config.total_timesteps + config.validation_interval,
                             config.validation_interval):
        target_step = min(target_step, config.total_timesteps)
        if target_step <= model.num_timesteps:
            break
        model.learn(total_timesteps=target_step - model.num_timesteps,
                    reset_num_timesteps=False, progress_bar=False)
        metrics = evaluate_model(model, splits.validation)
        validation_history.append({"step": target_step, **metrics})
        if metrics["mean_reward"] > selected_score:
            selected_score = metrics["mean_reward"]
            selected_step = target_step
            model.save(candidate_path)
    selected = DQN.load(candidate_path, device="cpu")
    test_metrics = evaluate_model(selected, splits.test)
    model_path = output_dir / MODEL_FILENAME
    candidate_path.replace(model_path)
    metadata = {
        "model_version": MODEL_VERSION, "algorithm": "DQN",
        "observation_version": OBSERVATION_VERSION, "action_version": ACTION_VERSION,
        "reward_version": REWARD_VERSION, "scenario_version": SCENARIO_VERSION,
        "feature_names": list(FEATURE_NAMES), "action_count": ACTION_COUNT,
        "scenario_source": "generated coverage cases; no saved profiles",
        "split_seeds": splits.seeds,
        "split_counts": {"training": len(splits.training), "validation": len(splits.validation),
                         "test": len(splits.test)},
        "training_seed": config.seed, "total_timesteps": config.total_timesteps,
        "validation_interval": config.validation_interval,
        "selected_step": selected_step, "gradient_updates": int(model._n_updates),
        "validation_history": validation_history, "test": test_metrics,
        "environment": "one-step contextual bandit; no balance changes or observed outcomes",
        "dependencies": {"python": platform.python_version(), "gymnasium": gymnasium.__version__,
                         "stable_baselines3": stable_baselines3.__version__, "torch": torch.__version__},
        "artifact_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
    }
    temporary_metadata = output_dir / "dqn_metadata.pending.json"
    temporary_metadata.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary_metadata.replace(output_dir / METADATA_FILENAME)
    environment.close()
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a research-only one-step DQN agent selector.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--steps", type=int, default=12000)
    parser.add_argument("--validation-every", type=int, default=3000)
    parser.add_argument("--training-cases", type=int, default=1536)
    parser.add_argument("--validation-cases", type=int, default=384)
    parser.add_argument("--test-cases", type=int, default=384)
    parser.add_argument("--seed", type=int, default=137)
    args = parser.parse_args()
    config = TrainingConfig(training_cases=args.training_cases, validation_cases=args.validation_cases,
                            test_cases=args.test_cases, total_timesteps=args.steps,
                            validation_interval=args.validation_every, seed=args.seed)
    result = run_training(args.output_dir, config)
    print(json.dumps({"artifact": str(Path(args.output_dir) / MODEL_FILENAME),
                      "selected_step": result["selected_step"], "test": result["test"]}, indent=2))


if __name__ == "__main__":
    main()
