"""Synthetic monthly trajectories are Gymnasium episodes with inspectable selections."""

from dataclasses import replace
from datetime import date
import json
import subprocess
import sys

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from app.rl.dynamic_environment import (
    DYNAMIC_ENVIRONMENT_VERSION, DynamicAgentSelectionEnv, DynamicEpisode,
)
from app.rl.dynamic_state import (
    DYNAMIC_FEATURE_NAMES, DYNAMIC_OBSERVATION_VERSION,
    build_dynamic_financial_state, encode_dynamic_observation,
)
from app.rl.population import generate_population
from app.rl.selection import ACTION_VERSION
from app.rl.trajectories import ShockConfig, generate_trajectory


@pytest.fixture(scope="module")
def episode():
    profile = generate_population(seed=91)[0]
    months = generate_trajectory(profile, months=3, seed=4)
    states = tuple(build_dynamic_financial_state(profile, month) for month in months)
    return DynamicEpisode(profile=profile, months=states, as_of_date=date(2026, 10, 1))


def test_three_month_episode_runs_selected_agents_and_terminates(episode):
    environment = DynamicAgentSelectionEnv(episode)
    original = [month.model_dump(mode="json") for month in episode.months]
    observation, reset_info = environment.reset(seed=7)
    assert environment.observation_space.contains(observation)
    assert observation.shape == (len(DYNAMIC_FEATURE_NAMES),)
    assert reset_info["month_index"] == 1
    action = environment.catalog.action_for(("budget", "investment"))

    for index, month in enumerate(episode.months):
        next_observation, score, terminated, truncated, info = environment.step(action)
        assert environment.observation_space.contains(next_observation)
        assert isinstance(score, float)
        assert score == pytest.approx(sum(info["reward_components"].values()))
        assert info["month_index"] == month.month_index
        assert info["selected_agents"] == ["budget", "investment"]
        assert [result["agent_id"] for result in info["agent_results"]] == ["budget", "investment"]
        assert all(item["agent_id"] in info["selected_agents"] for item in info["priority_actions"])
        assert info["reward_audit"]["version"] == info["reward_version"]
        assert info["action_version"] == ACTION_VERSION
        assert info["observation_version"] == DYNAMIC_OBSERVATION_VERSION
        assert info["transition_source"] == "precomputed_exogenous_trajectory"
        assert not truncated and terminated == (index == len(episode.months) - 1)
        if not terminated:
            assert info["next_month_index"] == episode.months[index + 1].month_index
            assert np.array_equal(next_observation, encode_dynamic_observation(episode.months[index + 1]))
    assert info["next_month_index"] is None
    assert [month.model_dump(mode="json") for month in episode.months] == original
    with pytest.raises(RuntimeError, match="Reset"):
        environment.step(action)


def test_next_month_is_exogenous_and_seeded_episode_sampling_is_repeatable(episode):
    environment = DynamicAgentSelectionEnv(episode)
    environment.reset(seed=5)
    first_next, _, _, _, first = environment.step(environment.catalog.action_for(("budget",)))
    environment.reset(seed=5)
    second_next, _, _, _, second = environment.step(environment.catalog.action_for(("debt",)))
    assert np.array_equal(first_next, second_next)
    assert first["selected_agents"] != second["selected_agents"]
    assert first["reward_components"] != second["reward_components"]

    another = DynamicEpisode(profile=episode.profile,
                             months=episode.months[1:], as_of_date=date(2026, 11, 1))
    sampler = DynamicAgentSelectionEnv((episode, another))
    choices = [sampler.reset(seed=seed)[1]["episode_index"] for seed in range(12)]
    assert choices == [sampler.reset(seed=seed)[1]["episode_index"] for seed in range(12)]
    assert set(choices) == {0, 1}


def test_invalid_actions_and_mixed_user_or_split_trajectories_are_rejected(episode):
    environment = DynamicAgentSelectionEnv(episode)
    with pytest.raises(RuntimeError, match="Reset"):
        environment.step(0)
    environment.reset(seed=1)
    for invalid in (-1, environment.action_space.n, 1.5, True):
        with pytest.raises(ValueError, match="Action"):
            environment.step(invalid)
    with pytest.raises(ValueError, match="consecutive"):
        DynamicEpisode(profile=episode.profile, months=(episode.months[0], episode.months[2]),
                       as_of_date=episode.as_of_date)
    with pytest.raises(ValueError, match="identity"):
        DynamicEpisode(profile=episode.profile,
                       months=(episode.months[0].model_copy(update={"synthetic_id": 999}),),
                       as_of_date=episode.as_of_date)
    train_profile = replace(episode.profile, dataset_split="train")
    test_profile = replace(episode.profile, dataset_split="test")
    train = DynamicEpisode(train_profile,
                           (episode.months[0].model_copy(update={"dataset_split": "train"}),),
                           episode.as_of_date)
    test = DynamicEpisode(test_profile,
                          (episode.months[0].model_copy(update={"dataset_split": "test"}),),
                          episode.as_of_date)
    with pytest.raises(ValueError, match="split"):
        DynamicAgentSelectionEnv((train, test))


def test_gymnasium_checker_accepts_dynamic_environment(episode):
    check_env(DynamicAgentSelectionEnv(episode), skip_render_check=True)


def test_cli_prints_reproducible_monthly_actions_and_rewards():
    command = [sys.executable, "-m", "app.rl.dynamic_environment", "--synthetic-id", "1",
               "--months", "3", "--seed", "4", "--selected", "budget", "investment"]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    assert report["environment"] == DYNAMIC_ENVIRONMENT_VERSION
    assert len(report["steps"]) == 3
    assert report["steps"][-1]["terminated"] is True
    assert [step["month_index"] for step in report["steps"]] == [1, 2, 3]
    assert report["transition_source"] == "precomputed_exogenous_trajectory"
    assert all(step["reward"] == pytest.approx(sum(step["reward_components"].values()))
               for step in report["steps"])
    stressed = subprocess.run(command + ["--shocks", "--shock-probability", "0.5"],
                              capture_output=True, text=True, check=True)
    last = json.loads(stressed.stdout)["steps"][-1]
    assert last["net_cash_flow"] == "-15063.68"
    assert [item["agent_id"] for item in last["priority_actions"]] == ["budget"]
