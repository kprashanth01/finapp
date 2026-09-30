"""Disjoint, reproducible synthetic-user episodes for monthly RL experiments."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import floor

from app.rl.dynamic_environment import DynamicEpisode
from app.rl.dynamic_state import build_dynamic_financial_state
from app.rl.population import DEFAULT_SEED, PERSONAS, POPULATION_VERSION, SyntheticProfile, generate_population
from app.rl.splits import DEFAULT_SPLIT_SEED, SPLIT_VERSION, assign_user_splits
from app.rl.trajectories import (DEFAULT_TRAJECTORY_SEED, SHOCK_SPLIT_TRAJECTORY_VERSION,
                                 ShockConfig, generate_trajectory)


DYNAMIC_SCENARIO_VERSION = "dynamic-user-episodes-v1"


@dataclass(frozen=True)
class DynamicEpisodeSplits:
    training: tuple[DynamicEpisode, ...]
    validation: tuple[DynamicEpisode, ...]
    test: tuple[DynamicEpisode, ...]
    summary: dict


def _sample(profiles: list[SyntheticProfile], count: int, *, seed: int, role: str
            ) -> tuple[SyntheticProfile, ...]:
    """Allocate exact quotas proportionally, then rank identities within personas."""
    if count > len(profiles):
        raise ValueError("Requested users exceed available users in the split.")
    grouped = {spec.name: [] for spec in PERSONAS}
    for profile in profiles:
        grouped[profile.persona].append(profile)
    quotas = {name: count * len(group) / len(profiles) for name, group in grouped.items()}
    assigned = {name: floor(quota) for name, quota in quotas.items()}
    order = sorted(grouped, key=lambda name: (-(quotas[name] - assigned[name]), name))
    for name in order[:count - sum(assigned.values())]:
        assigned[name] += 1
    chosen = []
    for name, group in grouped.items():
        ranked = sorted(group, key=lambda profile: sha256(
            f"{seed}:{role}:{profile.synthetic_id}".encode("ascii")).digest())
        chosen.extend(ranked[:assigned[name]])
    return tuple(sorted(chosen, key=lambda profile: profile.synthetic_id))


def _digest(episodes: tuple[DynamicEpisode, ...]) -> str:
    ids = ",".join(str(episode.profile.synthetic_id) for episode in episodes)
    return sha256(ids.encode("ascii")).hexdigest()


def build_dynamic_episode_splits(*, training_users: int = 256, validation_users: int = 64,
                                 test_users: int = 64, months: int = 12,
                                 population_seed: int = DEFAULT_SEED,
                                 split_seed: int = DEFAULT_SPLIT_SEED,
                                 selection_seed: int = 20261003,
                                 trajectory_seed: int = DEFAULT_TRAJECTORY_SEED,
                                 shock_probability: float = 0.10) -> DynamicEpisodeSplits:
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
           for value in (training_users, validation_users, test_users)):
        raise ValueError("All user counts must be positive integers.")
    if not isinstance(months, int) or isinstance(months, bool) or not 1 <= months <= 120:
        raise ValueError("months must be between 1 and 120")
    shock_config = ShockConfig(probability=shock_probability)
    profiles = assign_user_splits(generate_population(seed=population_seed), seed=split_seed)
    train_pool = [profile for profile in profiles if profile.dataset_split == "train"]
    test_pool = [profile for profile in profiles if profile.dataset_split == "test"]
    if training_users + validation_users > len(train_pool) or test_users > len(test_pool):
        raise ValueError("Requested users exceed available users in the split.")
    validation_profiles = _sample(train_pool, validation_users, seed=selection_seed, role="validation")
    validation_ids = {profile.synthetic_id for profile in validation_profiles}
    remaining = [profile for profile in train_pool if profile.synthetic_id not in validation_ids]
    training_profiles = _sample(remaining, training_users, seed=selection_seed, role="training")
    test_profiles = _sample(test_pool, test_users, seed=selection_seed, role="test")

    def episodes(selected: tuple[SyntheticProfile, ...]) -> tuple[DynamicEpisode, ...]:
        return tuple(DynamicEpisode(
            profile=profile,
            months=tuple(build_dynamic_financial_state(profile, raw) for raw in generate_trajectory(
                profile, months=months, seed=trajectory_seed, shock_config=shock_config)),
            as_of_date=date(2026, 10, 1),
        ) for profile in selected)

    groups = {"training": episodes(training_profiles), "validation": episodes(validation_profiles),
              "test": episodes(test_profiles)}
    summary = {
        "scenario_version": DYNAMIC_SCENARIO_VERSION,
        "population_version": POPULATION_VERSION,
        "split_version": SPLIT_VERSION,
        "trajectory_version": SHOCK_SPLIT_TRAJECTORY_VERSION,
        "seeds": {"population": population_seed, "split": split_seed,
                  "selection": selection_seed, "trajectory": trajectory_seed},
        "months_per_user": months,
        "shock_probability": shock_probability,
        "user_counts": {role: len(group) for role, group in groups.items()},
        "persona_counts": {role: {spec.name: Counter(
            episode.profile.persona for episode in group)[spec.name] for spec in PERSONAS}
                           for role, group in groups.items()},
        "user_id_sha256": {role: _digest(group) for role, group in groups.items()},
        "split_unit": "synthetic user; validation is held out from the training cohort",
    }
    return DynamicEpisodeSplits(**groups, summary=summary)
