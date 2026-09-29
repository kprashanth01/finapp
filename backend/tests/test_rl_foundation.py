"""The research selector must be reproducible and never change saved finances."""

from datetime import date
from decimal import Decimal as D
import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from app.advisory.state import build_planning_state
from app.advisory.registry import AgentRegistry
from app.services.financial_analysis import FinancialAnalysisService
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import FEATURE_NAMES, encode_observation
from app.rl import reward
from app.rl.selection import (
    AGENT_IDS, ACTION_VERSION, ActionCatalog, action_for, agents_for,
    assess_plan_readiness, rule_action,
)


def planning_state(*, debt="0", emergency="4000", goal=False):
    user = SimpleNamespace(monthly_income=D("5000"))
    profile = SimpleNamespace(
        monthly_expenses=D("3000"), savings=D("8000"), existing_debt=D(debt),
        emergency_fund=D(emergency), monthly_savings_contribution=D("500"),
        monthly_debt_payments=D("200") if D(debt) else D("0"),
        risk_tolerance="moderate", investment_horizon_years=5, financial_goal=None,
    )
    goals = [SimpleNamespace(
        id=1, name="Laptop", target_amount=D("6000"), saved_amount=D("1000"),
        target_date=date(2027, 9, 29), priority="medium", archived=False,
    )] if goal else []
    analysis = FinancialAnalysisService.analyze(user, profile)
    return build_planning_state(user, profile, analysis, goals, date(2026, 9, 29))


def test_action_mapping_round_trips_and_rule_selection():
    selected = ("budget", "emergency", "goal")
    assert agents_for(action_for(selected)) == selected
    assert len(AGENT_IDS) == 6
    assert set(agents_for(rule_action(planning_state(debt="1000", goal=True)))) == set(AGENT_IDS)
    with pytest.raises(ValueError):
        agents_for(64)


def test_observation_has_documented_finite_features_and_missingness():
    state = planning_state(goal=True)
    vector = encode_observation(state)
    assert vector.shape == (len(FEATURE_NAMES),)
    assert vector.dtype == np.float32
    assert np.isfinite(vector).all()
    assert vector[FEATURE_NAMES.index("emergency_months_scaled")] == pytest.approx(1.33 / 6)
    missing = state.model_copy(update={"monthly_savings_contribution": None,
                                       "savings_rate_percent": None})
    missing_vector = encode_observation(missing)
    assert missing_vector[FEATURE_NAMES.index("savings_missing")] == 1


def test_one_step_environment_is_seeded_and_does_not_change_financial_state():
    state = planning_state(debt="1000", goal=True)
    environment = AgentSelectionEnv(state)
    first, _ = environment.reset(seed=7)
    before = state.model_dump(mode="json")
    next_observation, reward, terminated, truncated, info = environment.step(
        action_for(("budget", "emergency", "goal"))
    )
    assert terminated and not truncated
    assert np.array_equal(first, next_observation)
    assert state.model_dump(mode="json") == before
    assert reward == pytest.approx(sum(info["reward_components"].values()))
    assert info["selected_agents"] == ["budget", "emergency", "goal"]
    with pytest.raises(RuntimeError):
        environment.step(0)
    repeated, _ = environment.reset(seed=7)
    assert np.array_equal(first, repeated)


def test_environment_rejects_non_discrete_actions():
    environment = AgentSelectionEnv(planning_state())
    environment.reset(seed=1)
    with pytest.raises(ValueError):
        environment.step(1.5)


def test_configured_action_catalog_has_stable_ids_and_version():
    full = ActionCatalog.from_agents(AGENT_IDS)
    assert full.version == ACTION_VERSION
    assert full.action_count == 63
    for action in range(full.action_count):
        expected = tuple(name for index, name in enumerate(AGENT_IDS) if (action + 1) & (1 << index))
        assert full.agents_for(action) == expected
    assert full.agents_for(action_for(("budget", "goal"))) == ("budget", "goal")
    limited = ActionCatalog.from_agents(
        ("budget", "debt", "emergency"),
        allowed_selections=(("debt", "budget"), ("emergency",), ("budget",)),
    )
    reordered = ActionCatalog.from_agents(
        ("budget", "debt", "emergency"),
        allowed_selections=(("budget",), ("budget", "debt"), ("emergency",)),
    )
    assert limited == reordered
    assert limited.version != ACTION_VERSION
    assert [limited.agents_for(action) for action in range(limited.action_count)] == [
        ("budget",), ("budget", "debt"), ("emergency",)
    ]
    with pytest.raises(ValueError):
        limited.action_for(("debt",))
    with pytest.raises(ValueError):
        ActionCatalog.from_agents(("budget", "budget"))


def test_environment_can_sample_supplied_states_and_report_plan_coverage():
    low_debt = planning_state()
    with_goal_and_debt = planning_state(debt="20000", goal=True)
    environment = AgentSelectionEnv([low_debt, with_goal_and_debt])
    first, _ = environment.reset(seed=19)
    fingerprint = environment.state.fingerprint()
    environment.step(action_for(("budget", "emergency")))
    repeated, _ = environment.reset(seed=19)
    assert np.array_equal(first, repeated)
    assert environment.state.fingerprint() == fingerprint
    seen = set()
    for _ in range(20):
        environment.reset()
        seen.add(environment.state.fingerprint())
    assert seen == {low_debt.fingerprint(), with_goal_and_debt.fingerprint()}

    incomplete = assess_plan_readiness(with_goal_and_debt, ("budget", "emergency"))
    assert incomplete["can_build_full_plan"] is False
    assert set(incomplete["missing_agents"]) == {"debt", "goal", "risk", "investment"}
    complete = assess_plan_readiness(with_goal_and_debt, AGENT_IDS)
    assert complete["can_build_full_plan"] is True
    assert complete["missing_agents"] == []


def test_environment_respects_injected_catalog_and_registry():
    state = planning_state()
    catalog = ActionCatalog.from_agents(
        ("budget", "emergency"), allowed_selections=(("budget",), ("emergency",))
    )
    environment = AgentSelectionEnv(state, registry=AgentRegistry.default(), catalog=catalog)
    assert environment.action_space.n == 2
    environment.reset(seed=7)
    _, _, _, _, info = environment.step(catalog.action_for(("emergency",)))
    assert info["selected_agents"] == ["emergency"]
    assert [result["agent_id"] for result in info["agent_results"]] == ["emergency"]
    assert info["action_version"] == catalog.version
    with pytest.raises(ValueError, match="unregistered"):
        AgentSelectionEnv(state, registry=AgentRegistry.default(),
                          catalog=ActionCatalog.from_agents(("unknown",)))


def test_reward_audit_identifies_covered_and_missed_critical_checks():
    assert hasattr(reward, "audit_reward")
    state = planning_state(debt="1000", goal=True)
    report = reward.audit_reward(state, ("budget", "emergency"))
    assert report.version == reward.REWARD_VERSION
    assert report.components == {
        "relevant_coverage": 2.0,
        "critical_coverage": 2.0,
        "missed_critical_penalty": -3.0,
        "unneeded_agent_penalty": 0.0,
        "agent_call_penalty": -0.3,
    }
    assert report.total == pytest.approx(0.7)
    assert report.relevant_agents == AGENT_IDS
    assert report.critical_agents == ("emergency", "goal")
    assert report.missed_critical_agents == ("goal",)
    checks = {check.agent_id: check for check in report.checks}
    assert checks["emergency"].value == "1.33"
    assert checks["emergency"].threshold == "3"
    assert checks["emergency"].operator == "<"
    assert checks["emergency"].critical is True
    assert checks["debt"].value == "4.00"
    assert checks["debt"].threshold == "20"
    assert checks["debt"].critical is False
    assert checks["goal"].value == "1"
    assert checks["goal"].critical is True


def test_reward_audit_labels_missing_debt_input_and_zero_expenses():
    assert hasattr(reward, "audit_reward")
    state = planning_state(debt="1000").model_copy(update={
        "monthly_debt_payments": None, "debt_to_income_percent": None,
        "monthly_expenses": D("0"), "emergency_fund_months": None,
    })
    report = reward.audit_reward(state, ("budget",))
    checks = {check.agent_id: check for check in report.checks}
    assert checks["debt"].value is None
    assert checks["debt"].input_status == "unavailable"
    assert checks["debt"].critical is True
    assert checks["emergency"].value is None
    assert checks["emergency"].input_status == "not_applicable"
    assert checks["emergency"].critical is False
    assert checks["goal"].input_status == "not_applicable"
    assert report.missed_critical_agents == ("debt",)


def test_baselines_choose_valid_actions_and_random_seed_repeats():
    assert importlib.util.find_spec("app.rl.baselines") is not None
    from app.rl.baselines import RandomBaseline, RuleBaseline

    state = planning_state(debt="1000", goal=True)
    catalog = ActionCatalog.from_agents(AGENT_IDS)
    assert RuleBaseline().choose_action(state, catalog) == rule_action(state)
    first = RandomBaseline(seed=28)
    second = RandomBaseline(seed=28)
    choices = [first.choose_action(state, catalog) for _ in range(20)]
    assert choices == [second.choose_action(state, catalog) for _ in range(20)]
    assert all(0 <= action < catalog.action_count for action in choices)
    assert len(set(choices)) > 1
