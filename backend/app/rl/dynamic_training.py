"""Offline DQN training on disjoint synthetic monthly user episodes."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import platform
from pathlib import Path

import gymnasium
import numpy as np
import stable_baselines3
from stable_baselines3 import DQN
from stable_baselines3.common.env_checker import check_env
import torch

from app.rl.dynamic_environment import DYNAMIC_ENVIRONMENT_VERSION, DynamicAgentSelectionEnv
from app.rl.dynamic_model_management import (
    DEFAULT_ARTIFACT_DIR, MODEL_FILENAME, MODEL_NAME,
    MODEL_VERSION as DYNAMIC_MODEL_VERSION, get_model_metadata as verified_dynamic_metadata,
    load_model as load_dynamic_dqn, save_model,
)
from app.rl.dynamic_reward import DYNAMIC_REWARD_VERSION
from app.rl.dynamic_scenarios import build_dynamic_episode_splits, DYNAMIC_SCENARIO_VERSION
from app.rl.dynamic_state import DYNAMIC_FEATURE_NAMES, DYNAMIC_OBSERVATION_VERSION
from app.rl.population import DEFAULT_SEED
from app.rl.selection import ACTION_COUNT, ACTION_VERSION
from app.rl.splits import DEFAULT_SPLIT_SEED
from app.rl.trajectories import DEFAULT_TRAJECTORY_SEED


@dataclass(frozen=True)
class DynamicTrainingConfig:
    training_users: int = 256
    validation_users: int = 64
    test_users: int = 64
    months: int = 12
    total_timesteps: int = 12000
    validation_interval: int = 3000
    population_seed: int = DEFAULT_SEED
    split_seed: int = DEFAULT_SPLIT_SEED
    selection_seed: int = 20261003
    trajectory_seed: int = DEFAULT_TRAJECTORY_SEED
    shock_probability: float = 0.10
    seed: int = 313

    def __post_init__(self):
        if (any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in
                (self.training_users, self.validation_users, self.test_users, self.months,
                 self.total_timesteps, self.validation_interval)) or
                self.validation_interval > self.total_timesteps):
            raise ValueError("Training needs positive counts and a valid validation interval.")
        if self.total_timesteps % 4 or self.validation_interval % 4:
            raise ValueError("Training and validation step counts must be multiples of four.")
        if self.training_users + self.validation_users > 9600 or self.test_users > 2400:
            raise ValueError("Requested users exceed available synthetic split users.")


def evaluate_dynamic_model(model: DQN, episodes) -> dict:
    env = DynamicAgentSelectionEnv(episodes)
    rewards, misses, calls = [], [], []
    for index in range(len(episodes)):
        observation, _ = env.reset(options={"episode_index": index})
        while True:
            action, _ = model.predict(observation, deterministic=True)
            observation, reward, terminated, truncated, info = env.step(int(action))
            if truncated or not np.isfinite(reward):
                raise ValueError("Invalid monthly selection result.")
            rewards.append(reward)
            misses.append(bool(info["reward_audit"]["missed_critical_agents"]))
            calls.append(len(info["selected_agents"]))
            if terminated:
                break
    env.close()
    return {
        "episode_count": len(episodes), "decision_count": len(rewards),
        "mean_reward": round(float(np.mean(rewards)), 3),
        "critical_miss_rate": round(float(np.mean(misses)), 4),
        "mean_agent_calls": round(float(np.mean(calls)), 3),
    }


def run_dynamic_training(output_dir: Path, config: DynamicTrainingConfig = DynamicTrainingConfig()) -> dict:
    """Choose the best validation checkpoint and evaluate it once on held-out test users."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    splits = build_dynamic_episode_splits(
        training_users=config.training_users, validation_users=config.validation_users,
        test_users=config.test_users, months=config.months, population_seed=config.population_seed,
        split_seed=config.split_seed, selection_seed=config.selection_seed,
        trajectory_seed=config.trajectory_seed, shock_probability=config.shock_probability,
    )
    check_env(DynamicAgentSelectionEnv(splits.training), warn=False)
    torch.set_num_threads(1)
    environment = DynamicAgentSelectionEnv(splits.training)
    model = DQN(
        "MlpPolicy", environment, seed=config.seed, device="cpu", verbose=0,
        learning_rate=0.001, buffer_size=max(1000, config.total_timesteps),
        learning_starts=min(256, max(4, config.total_timesteps // 10)),
        batch_size=32, train_freq=4, gradient_steps=1, gamma=0.0,
        exploration_fraction=0.5, exploration_final_eps=0.05,
        policy_kwargs={"net_arch": [64, 64]},
    )
    candidate_path = output_dir / "dynamic_dqn_candidate.zip"
    history = []
    selected_step = None
    selected_updates = None
    selected_score = float("-inf")
    for target_step in range(config.validation_interval, config.total_timesteps + config.validation_interval,
                             config.validation_interval):
        target_step = min(target_step, config.total_timesteps)
        if target_step <= model.num_timesteps:
            break
        model.learn(total_timesteps=target_step - model.num_timesteps,
                    reset_num_timesteps=False, progress_bar=False)
        metrics = evaluate_dynamic_model(model, splits.validation)
        history.append({"step": target_step, **metrics})
        if metrics["mean_reward"] > selected_score:
            selected_score = metrics["mean_reward"]
            selected_step = target_step
            selected_updates = int(model._n_updates)
            model.save(candidate_path)
    selected = DQN.load(candidate_path, device="cpu")
    test_metrics = evaluate_dynamic_model(selected, splits.test)
    metadata = {
        "model_name": MODEL_NAME, "model_version": DYNAMIC_MODEL_VERSION, "algorithm": "DQN",
        "training_date": datetime.now(timezone.utc).date().isoformat(),
        "training_steps": selected_step, "seed": config.seed,
        "environment_version": DYNAMIC_ENVIRONMENT_VERSION,
        "observation_version": DYNAMIC_OBSERVATION_VERSION,
        "action_version": ACTION_VERSION, "reward_version": DYNAMIC_REWARD_VERSION,
        "scenario_version": DYNAMIC_SCENARIO_VERSION,
        "dataset_version": DYNAMIC_SCENARIO_VERSION,
        "feature_names": list(DYNAMIC_FEATURE_NAMES), "action_count": ACTION_COUNT,
        "split_counts": splits.summary["user_counts"],
        "dataset": splits.summary,
        "training_seed": config.seed, "total_timesteps": config.total_timesteps,
        "validation_interval": config.validation_interval, "selected_step": selected_step,
        "gradient_updates": selected_updates, "validation_history": history,
        "test": test_metrics,
        "gamma": 0.0,
        "transition_note": "Precomputed exogenous months; action cannot change future balances or rewards.",
        "reward_note": "Selection proxy only; not a measured financial outcome.",
        "dependencies": {"python": platform.python_version(), "gymnasium": gymnasium.__version__,
                         "stable_baselines3": stable_baselines3.__version__, "torch": torch.__version__},
    }
    metadata = save_model(selected, metadata, output_dir)
    candidate_path.unlink(missing_ok=True)
    environment.close()
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an offline monthly agent-selection DQN.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--steps", type=int, default=12000)
    parser.add_argument("--validation-every", type=int, default=3000)
    parser.add_argument("--training-users", type=int, default=256)
    parser.add_argument("--validation-users", type=int, default=64)
    parser.add_argument("--test-users", type=int, default=64)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--population-seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--split-seed", type=int, default=DEFAULT_SPLIT_SEED)
    parser.add_argument("--selection-seed", type=int, default=20261003)
    parser.add_argument("--trajectory-seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--shock-probability", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=313)
    args = parser.parse_args()
    config = DynamicTrainingConfig(
        training_users=args.training_users, validation_users=args.validation_users,
        test_users=args.test_users, months=args.months, total_timesteps=args.steps,
        validation_interval=args.validation_every, population_seed=args.population_seed,
        split_seed=args.split_seed, selection_seed=args.selection_seed,
        trajectory_seed=args.trajectory_seed, shock_probability=args.shock_probability,
        seed=args.seed,
    )
    result = run_dynamic_training(args.output_dir, config)
    print(json.dumps({"artifact": str(args.output_dir / MODEL_FILENAME),
                      "selected_step": result["selected_step"], "test": result["test"]}, indent=2))


if __name__ == "__main__":
    main()
