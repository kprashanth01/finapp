"""Configurable research shocks are explicit, repeatable, and preserve v1 output."""

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from app.rl.population import SyntheticDebt, generate_population
from app.rl.trajectories import ShockConfig, export_trajectories, generate_trajectory


def _profile():
    profile = generate_population(seed=91)[0]
    return replace(
        profile, base_monthly_income=Decimal("200.00"), income_volatility=Decimal("0"),
        fixed_monthly_expenses=Decimal("100.00"), variable_monthly_expenses=Decimal("50.00"),
        monthly_expenses=Decimal("150.00"), monthly_debt_payments=Decimal("0.00"),
        existing_debt=Decimal("0.00"), debts=(), savings=Decimal("20.00"),
        emergency_fund=Decimal("10.00"), monthly_savings_contribution=Decimal("20.00"),
    )


def _forced(event_type: str, **overrides):
    return ShockConfig(probability=1, event_types=(event_type,), **overrides)


def test_zero_probability_preserves_baseline_values_and_v1_export(tmp_path):
    profile = _profile()
    baseline = generate_trajectory(profile, months=3, seed=17, expense_volatility=0)
    shocked = generate_trajectory(profile, months=3, seed=17, expense_volatility=0,
                                  shock_config=ShockConfig(probability=0))
    assert [state.income for state in shocked] == [state.income for state in baseline]
    assert [state.savings for state in shocked] == [state.savings for state in baseline]
    assert all(state.event_type is None for state in shocked)
    path = tmp_path / "v1.jsonl"
    report = export_trajectories(path, synthetic_id=1)
    assert report["dataset_version"] == "synthetic-trajectories-v1"
    assert report["sha256"] == "6297bf7f3d992849c68ebcd585b6da9cb60334da4a8b96365b32a1257c9f43a4"


@pytest.mark.parametrize("event_type,expected_income", [
    ("low_income", Decimal("100.00")),
    ("high_income", Decimal("300.00")),
])
def test_income_events_apply_configured_magnitude(event_type, expected_income):
    month = generate_trajectory(_profile(), months=1, seed=5, expense_volatility=0,
                                shock_config=_forced(event_type, magnitude=0.5))[0]
    assert month.income == expected_income
    assert month.event_type == event_type and month.event_started
    assert month.income_shock
    assert month.event_income_delta == expected_income - Decimal("200.00")


def test_temporary_income_loss_spans_configured_months():
    months = generate_trajectory(_profile(), months=3, seed=5, expense_volatility=0,
                                 shock_config=_forced("temporary_income_loss", income_loss_months=2))
    assert [month.income for month in months] == [Decimal("0.00")] * 3
    assert [month.event_started for month in months] == [True, False, True]
    assert all(month.event_type == "temporary_income_loss" for month in months)


@pytest.mark.parametrize("event_type,expected_fixed,expected_variable", [
    ("unexpected_expense", Decimal("100.00"), Decimal("90.00")),
    ("emergency_expense", Decimal("140.00"), Decimal("50.00")),
])
def test_expense_events_add_to_the_correct_obligation(event_type, expected_fixed, expected_variable):
    month = generate_trajectory(_profile(), months=1, seed=5, expense_volatility=0,
                                shock_config=_forced(event_type, unexpected_expense=Decimal("40.00"),
                                                     emergency_expense=Decimal("40.00")))[0]
    assert month.fixed_expenses == expected_fixed
    assert month.variable_expenses == expected_variable
    assert month.event_expense == Decimal("40.00")
    assert month.scheduled_expenses == Decimal("190.00")


def test_debt_pressure_increases_due_emi_without_overpaying_balance():
    debt = SyntheticDebt("personal", Decimal("100.00"), Decimal("0"), Decimal("30.00"), 4)
    profile = replace(_profile(), monthly_debt_payments=Decimal("30.00"),
                      monthly_expenses=Decimal("180.00"), existing_debt=Decimal("100.00"),
                      debts=(debt,))
    month = generate_trajectory(profile, months=1, seed=5, expense_volatility=0,
                                shock_config=_forced("debt_pressure", magnitude=0.5))[0]
    assert month.scheduled_emi == Decimal("45.00")
    assert month.paid_emi == Decimal("45.00")
    assert month.event_emi_extra == Decimal("15.00")
    assert month.outstanding_debt == Decimal("55.00")


def test_event_probability_and_income_volatility_are_configurable():
    profile = _profile()
    no_events = generate_trajectory(profile, months=12, seed=8,
                                    shock_config=ShockConfig(probability=0, income_volatility_override=0))
    assert all(month.event_type is None and month.income == Decimal("200.00") for month in no_events)
    varied = generate_trajectory(profile, months=12, seed=8,
                                 shock_config=ShockConfig(probability=0, income_volatility_override=0.4))
    assert len({month.income for month in varied}) > 1
    profiles = generate_population(seed=14)[:100]
    sampled = [month for p in profiles for month in generate_trajectory(
        p, months=12, seed=8, shock_config=ShockConfig(probability=0.1))]
    assert 0 < sum(month.event_started for month in sampled) < len(sampled) // 2


def test_shock_export_is_versioned_reproducible_and_summarized(tmp_path):
    path = tmp_path / "v2.jsonl"
    config = _forced("low_income", magnitude=0.5)
    report = export_trajectories(path, synthetic_id=1, shock_config=config)
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode().splitlines()]
    assert report["dataset_version"] == "synthetic-trajectories-v2"
    assert report["monthly_state_count"] == 12
    assert report["sha256"] == sha256(payload).hexdigest()
    assert report["event_months"]["low_income"] == 12
    assert all(row["event_type"] == "low_income" and row["income_shock"] for row in rows)
    assert export_trajectories(path, synthetic_id=1, shock_config=config) == report
    assert path.read_bytes() == payload


def test_invalid_event_settings_are_rejected():
    with pytest.raises(ValueError, match="probability"):
        ShockConfig(probability=1.1)
    with pytest.raises(ValueError, match="magnitude"):
        ShockConfig(magnitude=-0.1)
    with pytest.raises(ValueError, match="event_types"):
        ShockConfig(event_types=())
    with pytest.raises(ValueError, match="cents"):
        ShockConfig(unexpected_expense=Decimal("1.001"))
