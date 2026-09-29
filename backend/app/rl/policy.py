"""Research-only fitted reward predictor for the one-step selection problem."""

import hashlib
import json
from pathlib import Path

import numpy as np

from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION, encode_observation
from app.rl.baselines import RandomBaseline, RuleBaseline
from app.rl.reward import REWARD_VERSION, reward_components
from app.rl.selection import ACTION_COUNT, ACTION_VERSION, DEFAULT_CATALOG, agents_for

POLICY_VERSION = "fitted-proxy-q-v1"


def reward_matrix(states):
    """All counterfactual proxy rewards are computable without running advice."""
    return np.asarray([
        [sum(reward_components(state, agents_for(action)).values())
         for action in range(ACTION_COUNT)] for state in states
    ], dtype=np.float32)


class FittedQPolicy:
    def __init__(self, weights, biases, *, training=None):
        self.weights = [np.asarray(value, dtype=np.float32) for value in weights]
        self.biases = [np.asarray(value, dtype=np.float32) for value in biases]
        if (len(self.weights) != 2 or len(self.biases) != 2 or
                self.weights[0].shape[0] != len(FEATURE_NAMES) or
                self.weights[1].shape != (self.weights[0].shape[1], ACTION_COUNT) or
                self.biases[0].shape != (self.weights[0].shape[1],) or
                self.biases[1].shape != (ACTION_COUNT,)):
            raise ValueError("Incompatible policy dimensions.")
        self.training = training or {}

    def predict_rewards(self, observations):
        values = np.asarray(observations, dtype=np.float32)
        if values.shape[-1] != len(FEATURE_NAMES):
            raise ValueError("Incompatible observation dimensions.")
        hidden = np.maximum(0, values @ self.weights[0] + self.biases[0])
        return hidden @ self.weights[1] + self.biases[1]

    def predict_action(self, observation):
        return int(np.argmax(self.predict_rewards(observation)))

    def to_payload(self):
        return {
            "policy_version": POLICY_VERSION,
            "observation_version": OBSERVATION_VERSION,
            "action_version": ACTION_VERSION,
            "reward_version": REWARD_VERSION,
            "feature_names": list(FEATURE_NAMES),
            "training": self.training,
            "weights": [value.tolist() for value in self.weights],
            "biases": [value.tolist() for value in self.biases],
        }

    def save(self, path):
        payload = self.to_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        payload["checksum_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        checksum = payload.pop("checksum_sha256", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if checksum != hashlib.sha256(canonical.encode()).hexdigest():
            raise ValueError("Policy checksum mismatch.")
        expected = {
            "policy_version": POLICY_VERSION,
            "observation_version": OBSERVATION_VERSION,
            "action_version": ACTION_VERSION,
            "reward_version": REWARD_VERSION,
            "feature_names": list(FEATURE_NAMES),
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ValueError("Incompatible policy schema or reward version.")
        return cls(payload["weights"], payload["biases"], training=payload.get("training"))


def train_policy(states, *, seed=42, epochs=100, hidden=48, learning_rate=0.004):
    if not states or epochs < 1 or hidden < 1:
        raise ValueError("Training needs cases, epochs, and a hidden layer.")
    x = np.stack([encode_observation(state) for state in states]).astype(np.float64)
    y = reward_matrix(states).astype(np.float64)
    rng = np.random.default_rng(seed)
    w1 = rng.normal(0, np.sqrt(2 / x.shape[1]), (x.shape[1], hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, np.sqrt(2 / hidden), (hidden, ACTION_COUNT))
    b2 = np.zeros(ACTION_COUNT)
    parameters = [w1, b1, w2, b2]
    first = [np.zeros_like(value) for value in parameters]
    second = [np.zeros_like(value) for value in parameters]
    step = 0
    for _ in range(epochs):
        for indices in np.array_split(rng.permutation(len(x)), max(1, int(np.ceil(len(x) / 256)))):
            batch_x, batch_y = x[indices], y[indices]
            preactivation = batch_x @ w1 + b1
            activation = np.maximum(0, preactivation)
            difference = (activation @ w2 + b2 - batch_y) * (2 / (len(indices) * ACTION_COUNT))
            gradients = [
                batch_x.T @ ((difference @ w2.T) * (preactivation > 0)),
                np.sum((difference @ w2.T) * (preactivation > 0), axis=0),
                activation.T @ difference,
                np.sum(difference, axis=0),
            ]
            step += 1
            for index, (parameter, gradient) in enumerate(zip(parameters, gradients)):
                first[index] = 0.9 * first[index] + 0.1 * gradient
                second[index] = 0.999 * second[index] + 0.001 * gradient**2
                parameter -= learning_rate * (first[index] / (1 - 0.9**step)) / (
                    np.sqrt(second[index] / (1 - 0.999**step)) + 1e-8
                )
    return FittedQPolicy([w1, w2], [b1, b2], training={
        "seed": seed, "epochs": epochs, "hidden": hidden, "training_cases": len(states),
        "method": "full-information proxy reward regression",
    })


def evaluate_policy(states, policy, *, seed=42):
    if not states:
        raise ValueError("Benchmark needs held-out cases.")
    matrix = reward_matrix(states)
    observations = np.stack([encode_observation(state) for state in states])
    rule = RuleBaseline()
    random = RandomBaseline(seed=seed)
    actions = {
        "learned": np.argmax(policy.predict_rewards(observations), axis=1),
        "rule": np.asarray([rule.choose_action(state, DEFAULT_CATALOG) for state in states]),
        "random": np.asarray([random.choose_action(state, DEFAULT_CATALOG) for state in states]),
        "oracle": np.argmax(matrix, axis=1),
    }
    results = {}
    for name, choices in actions.items():
        rewards = matrix[np.arange(len(states)), choices]
        calls = [len(agents_for(int(action))) for action in choices]
        misses = [reward_components(state, agents_for(int(action)))["missed_critical_penalty"] < 0
                  for state, action in zip(states, choices)]
        results[name] = {
            "mean_reward": round(float(np.mean(rewards)), 3),
            "critical_miss_rate": round(float(np.mean(misses)), 4),
            "mean_agent_calls": round(float(np.mean(calls)), 3),
        }
    return {"case_count": len(states), "held_out": True, "policies": results}
