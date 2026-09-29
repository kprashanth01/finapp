"""Rebuild the research policy: python -m app.rl.train."""

import json
from pathlib import Path

from app.rl.policy import evaluate_policy, train_policy
from app.rl.scenarios import SCENARIO_VERSION, generate_scenarios

MODEL_PATH = Path(__file__).with_name("model.json")


def main():
    training = generate_scenarios(1536, seed=20260929)
    held_out = generate_scenarios(384, seed=20260930)
    train_fingerprints = {state.fingerprint() for state in training}
    if train_fingerprints.intersection(state.fingerprint() for state in held_out):
        raise RuntimeError("Training and evaluation cases overlap.")
    policy = train_policy(training, seed=137, epochs=100, hidden=48)
    benchmark = evaluate_policy(held_out, policy, seed=38)
    policy.training.update({
        "scenario_version": SCENARIO_VERSION,
        "scenario_source": "generated coverage cases; no observed outcomes or survey records",
        "training_scenario_seed": 20260929,
        "evaluation_scenario_seed": 20260930,
        "evaluation_random_seed": 38,
        "held_out_benchmark": benchmark,
    })
    policy.save(MODEL_PATH)
    print(json.dumps({"model_path": str(MODEL_PATH), "benchmark": benchmark}, indent=2))


if __name__ == "__main__":
    main()
