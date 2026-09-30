"""Monthly research states expose bounded observable features without split leakage."""

from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest

from app.rl.dynamic_state import (
    DYNAMIC_FEATURE_NAMES, DYNAMIC_FEATURE_RATIONALE, DYNAMIC_OBSERVATION_VERSION, DynamicFinancialState,
    build_dynamic_financial_state, encode_dynamic_observation,
)
from app.rl.population import generate_population
from app.rl.trajectories import ShockConfig, generate_trajectory


def _profile():
    profile = generate_population(seed=91)[0]
    return replace(
        profile, base_monthly_income=Decimal("200.00"), income_volatility=Decimal("0"),
        fixed_monthly_expenses=Decimal("100.00"), variable_monthly_expenses=Decimal("50.00"),
        monthly_expenses=Decimal("150.00"), monthly_debt_payments=Decimal("0.00"),
        existing_debt=Decimal("0.00"), debts=(), savings=Decimal("20.00"),
        emergency_fund=Decimal("10.00"), monthly_savings_contribution=Decimal("20.00"),
    )


def test_dynamic_state_uses_current_month_and_profile_context():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0)[0]
    state = build_dynamic_financial_state(profile, month)
    assert isinstance(state, DynamicFinancialState)
    assert state.schema_version == "dynamic-financial-state-v1"
    assert state.synthetic_id == profile.synthetic_id and state.month_index == 1
    assert state.monthly_income == Decimal("200.00")
    assert state.monthly_expenses == Decimal("150.00")
    assert state.savings == Decimal("70.00")
    assert state.emergency_fund == Decimal("10.00")
    assert state.investment_value == Decimal("0.00")
    assert state.expense_to_income_ratio == Decimal("0.7500")
    assert state.emergency_fund_months == Decimal("0.0667")
    assert state.income_volatility == Decimal("0")
    assert state.observed_low_income is False
    assert state.liquidity_pressure is False
    vector = encode_dynamic_observation(state)
    assert vector.dtype == np.float32
    assert vector.shape == (len(DYNAMIC_FEATURE_NAMES),)
    assert vector[DYNAMIC_FEATURE_NAMES.index("expense_income_scaled")] == pytest.approx(0.375)
    assert vector[DYNAMIC_FEATURE_NAMES.index("fixed_expense_income_scaled")] == pytest.approx(0.25)
    assert vector[DYNAMIC_FEATURE_NAMES.index("income_zero")] == 0


def test_observation_changes_with_month_and_stays_finite_and_bounded():
    profile = next(p for p in generate_population(seed=12) if p.persona == "gig_worker")
    months = generate_trajectory(profile, months=12, seed=19,
                                 shock_config=ShockConfig(probability=0.5))
    vectors = [encode_dynamic_observation(build_dynamic_financial_state(profile, month))
               for month in months]
    assert all(np.isfinite(vector).all() for vector in vectors)
    assert all(np.all((-1 <= vector) & (vector <= 1)) for vector in vectors)
    assert any(not np.array_equal(vectors[0], vector) for vector in vectors[1:])


def test_zero_income_uses_missing_denominator_flag_without_infinity():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0,
                                shock_config=ShockConfig(probability=1,
                                                         event_types=("temporary_income_loss",)))[0]
    state = build_dynamic_financial_state(profile, month)
    vector = encode_dynamic_observation(state)
    assert state.monthly_income == 0 and state.observed_low_income
    assert state.expense_to_income_ratio is None
    assert np.isfinite(vector).all()
    assert vector[DYNAMIC_FEATURE_NAMES.index("income_zero")] == 1
    assert vector[DYNAMIC_FEATURE_NAMES.index("expense_income_scaled")] == 0


def test_split_and_simulator_event_label_are_metadata_not_policy_features():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0,
                                shock_config=ShockConfig(probability=1,
                                                         event_types=("low_income",)))[0]
    train = build_dynamic_financial_state(replace(profile, dataset_split="train"),
                                          replace(month, dataset_split="train"))
    test = build_dynamic_financial_state(replace(profile, dataset_split="test"),
                                         replace(month, dataset_split="test", event_type="high_income"))
    assert train.dataset_split == "train" and test.dataset_split == "test"
    assert train.simulated_event_type != test.simulated_event_type
    assert np.array_equal(encode_dynamic_observation(train), encode_dynamic_observation(test))
    assert "dataset_split" not in DYNAMIC_FEATURE_NAMES
    assert "simulated_event_type" not in DYNAMIC_FEATURE_NAMES


def test_builder_rejects_month_from_another_user_or_split():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4)[0]
    with pytest.raises(ValueError, match="identity"):
        build_dynamic_financial_state(profile, replace(month, synthetic_id=profile.synthetic_id + 1))
    with pytest.raises(ValueError, match="split"):
        build_dynamic_financial_state(replace(profile, dataset_split="train"), month)
    with pytest.raises(ValueError, match="financial totals"):
        build_dynamic_financial_state(profile, replace(month, emergency_fund=month.savings + 1))


def test_effective_volatility_override_is_encoded_and_every_feature_has_a_reason():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4,
                                shock_config=ShockConfig(probability=0, income_volatility_override=0.4))[0]
    state = build_dynamic_financial_state(profile, month, income_volatility_override=0.4)
    assert state.income_volatility == Decimal("0.4")
    assert encode_dynamic_observation(state)[DYNAMIC_FEATURE_NAMES.index("income_volatility_scaled")] == pytest.approx(0.4)
    assert set(DYNAMIC_FEATURE_NAMES) == set(DYNAMIC_FEATURE_RATIONALE)
    assert all(DYNAMIC_FEATURE_RATIONALE[name] for name in DYNAMIC_FEATURE_NAMES)


def test_new_observation_has_its_own_version_and_does_not_replace_current_dqn():
    from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION
    assert DYNAMIC_OBSERVATION_VERSION == "dynamic-observation-v1"
    assert OBSERVATION_VERSION == "planning-observation-v1"
    assert len(FEATURE_NAMES) == 16
    assert len(DYNAMIC_FEATURE_NAMES) > len(FEATURE_NAMES)
