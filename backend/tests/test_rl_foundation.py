"""The research selector must be reproducible and never change saved finances."""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import numpy as np
import pytest

from app.advisory.state import build_planning_state
from app.services.financial_analysis import FinancialAnalysisService
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import FEATURE_NAMES, encode_observation
from app.rl.selection import AGENT_IDS, action_for, agents_for, rule_action


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
