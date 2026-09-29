"""A trained selector must be reproducible and remain a research-only policy."""

import json

import numpy as np
import pytest

from app.rl.observation import FEATURE_NAMES, encode_observation
from app.rl.policy import FittedQPolicy, evaluate_policy, reward_matrix, train_policy
from app.rl.scenarios import SCENARIO_VERSION, build_splits, generate_scenarios
from app.rl.selection import ACTION_COUNT, agents_for


def test_scenarios_cover_distinct_inputs_without_persisting_profiles():
    first = generate_scenarios(32, seed=9)
    again = generate_scenarios(32, seed=9)
    held_out = generate_scenarios(16, seed=10)
    assert len(first) == 32
    assert SCENARIO_VERSION
    assert [state.fingerprint() for state in first] == [state.fingerprint() for state in again]
    assert set(state.fingerprint() for state in first).isdisjoint(
        state.fingerprint() for state in held_out
    )
    assert any(state.goals for state in first)
    assert any(not state.goals for state in first)
    assert any(state.existing_debt > 0 for state in first)
    assert any(state.existing_debt == 0 for state in first)
    assert any(state.monthly_savings_contribution is None for state in first)


def test_three_scenario_splits_are_reproducible_and_disjoint():
    splits = build_splits(training_count=32, validation_count=12, test_count=12,
                          training_seed=101, validation_seed=102, test_seed=103)
    repeated = build_splits(training_count=32, validation_count=12, test_count=12,
                            training_seed=101, validation_seed=102, test_seed=103)
    assert [len(splits.training), len(splits.validation), len(splits.test)] == [32, 12, 12]
    fingerprints = [set(state.fingerprint() for state in group)
                    for group in (splits.training, splits.validation, splits.test)]
    assert all(a.isdisjoint(b) for i, a in enumerate(fingerprints)
               for b in fingerprints[i + 1:])
    assert [state.fingerprint() for state in splits.test] == [
        state.fingerprint() for state in repeated.test
    ]
    with pytest.raises(ValueError):
        build_splits(training_count=0, validation_count=12, test_count=12)


def test_fitted_q_policy_reproduces_training_and_uses_valid_actions(tmp_path):
    train = generate_scenarios(80, seed=3)
    test = generate_scenarios(24, seed=4)
    first = train_policy(train, seed=17, epochs=8, hidden=20)
    second = train_policy(train, seed=17, epochs=8, hidden=20)
    assert first.to_payload() == second.to_payload()
    observation = encode_observation(test[0])
    assert observation.shape == (len(FEATURE_NAMES),)
    action = first.predict_action(observation)
    assert 0 <= action < ACTION_COUNT
    assert agents_for(action)

    path = tmp_path / "policy.json"
    first.save(path)
    assert FittedQPolicy.load(path).predict_action(observation) == action
    payload = json.loads(path.read_text())
    payload["observation_version"] = "incompatible"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="incompatible|checksum"):
        FittedQPolicy.load(path)


def test_benchmark_uses_held_out_cases_and_explicit_proxy_metrics():
    train = generate_scenarios(80, seed=21)
    test = generate_scenarios(24, seed=22)
    policy = train_policy(train, seed=23, epochs=8, hidden=20)
    matrix = reward_matrix(test)
    assert matrix.shape == (24, ACTION_COUNT)
    assert np.isfinite(matrix).all()
    metrics = evaluate_policy(test, policy, seed=24)
    assert metrics["case_count"] == 24
    assert metrics["held_out"] is True
    assert set(metrics["policies"]) == {"learned", "rule", "random", "oracle"}
    for item in metrics["policies"].values():
        assert 0 <= item["critical_miss_rate"] <= 1
        assert 1 <= item["mean_agent_calls"] <= 6
    assert metrics["policies"]["oracle"]["mean_reward"] >= metrics["policies"]["learned"]["mean_reward"]
