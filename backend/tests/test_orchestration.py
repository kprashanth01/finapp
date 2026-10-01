"""Live policy modes must execute their actual selections without inventing a plan."""

import pytest

from app.rl.scenarios import generate_scenarios
from app.rl.selection import action_for


def state():
    return generate_scenarios(1, seed=91)[0]


def test_rule_and_seeded_random_use_the_same_selection_flow():
    from app.rl.orchestration import run_orchestration

    current = state()
    rule = run_orchestration(current, mode="rule_based", seed=42)
    random_one = run_orchestration(current, mode="random", seed=42)
    random_two = run_orchestration(current, mode="random", seed=42)
    assert rule["mode"] == "rule_based"
    assert rule["action"] == action_for(rule["selected_agents"])
    assert [item["agent_id"] for item in rule["agent_results"]] == rule["selected_agents"]
    assert rule["plan_readiness"]["can_build_full_plan"] is True
    assert rule["advice"] is not None
    assert random_one["action"] == random_two["action"]
    assert random_one["total_reward"] == random_two["total_reward"]
    assert random_one["seed"] == 42
    assert random_one["explanation"] == random_two["explanation"]
    assert random_one["explanation"]["seed"] == 42
    assert "did not cause this selection" in random_one["explanation"]["policy_explanation"]


def test_partial_selection_never_builds_a_complete_monthly_plan(monkeypatch):
    from app.rl import orchestration

    class PartialPolicy:
        def choose_action(self, state, catalog):
            return catalog.action_for(("budget",))

    monkeypatch.setattr(orchestration, "get_policy", lambda mode, seed: PartialPolicy())
    result = orchestration.run_orchestration(state(), mode="rl", seed=42)
    assert result["selected_agents"] == ["budget"]
    assert result["advice"] is None
    assert result["plan_readiness"]["can_build_full_plan"] is False
    assert "emergency" in result["plan_readiness"]["missing_agents"]
    assert result["summary"]["title"] == "Partial analysis"


def test_dqn_prediction_uses_verified_model_cached_once(monkeypatch):
    from app.rl import orchestration

    class FakeModel:
        def predict(self, observation, deterministic):
            assert deterministic is True
            assert observation.shape == (16,)
            return 0, None

    calls = []
    monkeypatch.setattr(orchestration, "load_dqn_artifact", lambda: calls.append(1) or FakeModel())
    orchestration.cached_dqn_model.cache_clear()
    try:
        one = orchestration.run_orchestration(state(), mode="rl", seed=1)
        two = orchestration.run_orchestration(state(), mode="rl", seed=2)
        assert one["action"] == two["action"] == 0
        assert len(calls) == 1
    finally:
        orchestration.cached_dqn_model.cache_clear()


def test_unavailable_dqn_is_reported_without_fallback(monkeypatch):
    from app.rl import orchestration

    def missing():
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(orchestration, "load_dqn_artifact", missing)
    orchestration.cached_dqn_model.cache_clear()
    with pytest.raises(orchestration.ModelUnavailableError):
        orchestration.run_orchestration(state(), mode="rl", seed=42)


def test_configured_mode_resolves_each_policy_without_changing_explicit_comparisons(monkeypatch):
    from app.rl import orchestration

    for configured, expected in (("rule_based", "rule_based"), ("random", "random"),
                                 ("trained_rl", "trained_rl")):
        monkeypatch.setenv("ORCHESTRATOR_MODE", configured)
        result = orchestration.run_orchestration(state(), seed=17)
        assert result["mode"] == expected
        assert result["selected_agents"] == [item["agent_id"] for item in result["agent_results"]]
        assert result["action"] == action_for(result["selected_agents"])
        if expected == "trained_rl":
            assert result["policy_version"] == orchestration.MODEL_VERSION
            assert result["explanation"]["method"] == "rl"
    monkeypatch.setenv("ORCHESTRATOR_MODE", "random")
    assert orchestration.run_orchestration(state(), mode="rule_based", seed=17)["mode"] == "rule_based"


def test_bad_configured_mode_is_rejected_without_fallback(monkeypatch):
    from app.rl import orchestration

    monkeypatch.setenv("ORCHESTRATOR_MODE", "unknown")
    with pytest.raises(orchestration.InvalidOrchestratorModeError, match="ORCHESTRATOR_MODE"):
        orchestration.run_orchestration(state(), seed=42)
    assert orchestration.run_orchestration(state(), mode="rule_based", seed=42)["mode"] == "rule_based"
