"""Longitudinal synthetic states preserve identity, money flows, and seed reproducibility."""

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from itertools import islice
import json
from statistics import fmean, pstdev

import pytest

from app.rl.population import SyntheticDebt, generate_population
from app.rl.trajectories import export_trajectories, generate_trajectory


def _profile():
    profile = generate_population(seed=91)[0]
    return replace(
        profile, base_monthly_income=Decimal("200.00"), income_volatility=Decimal("0"),
        fixed_monthly_expenses=Decimal("100.00"), variable_monthly_expenses=Decimal("50.00"),
        monthly_expenses=Decimal("150.00"), monthly_debt_payments=Decimal("0.00"),
        existing_debt=Decimal("0.00"), debts=(), savings=Decimal("20.00"),
        emergency_fund=Decimal("10.00"), monthly_savings_contribution=Decimal("20.00"),
    )


def test_seeded_months_are_ordered_repeatable_and_independent_of_other_users():
    profiles = generate_population(seed=12)
    gig = next(profile for profile in profiles if profile.persona == "gig_worker")
    first = generate_trajectory(gig, months=12, seed=88)
    assert first == generate_trajectory(gig, months=12, seed=88)
    assert first != generate_trajectory(gig, months=12, seed=89)
    assert [month.month_index for month in first] == list(range(1, 13))
    assert {month.synthetic_id for month in first} == {gig.synthetic_id}
    assert len({month.income for month in first}) > 1
    assert all(month.income >= 0 and month.savings >= month.emergency_fund >= 0 for month in first)
    assert all(month.outstanding_debt >= 0 for month in first)
    other = next(profile for profile in profiles if profile.synthetic_id != gig.synthetic_id)
    generate_trajectory(other, months=12, seed=88)
    assert first == generate_trajectory(gig, months=12, seed=88)


def test_zero_volatility_cash_flow_carries_savings_without_invented_investment_returns():
    months = generate_trajectory(_profile(), months=3, seed=4, expense_volatility=0)
    assert [month.income for month in months] == [Decimal("200.00")] * 3
    assert [month.savings for month in months] == [Decimal("70.00"), Decimal("120.00"), Decimal("170.00")]
    assert all(month.emergency_fund == Decimal("10.00") for month in months)
    assert all(month.scheduled_expenses == Decimal("150.00") for month in months)
    assert all(month.net_cash_flow == Decimal("50.00") for month in months)
    assert all(month.investment_value == Decimal("0.00") for month in months)
    assert all(not month.missed_payment and month.unfunded_expenses == 0 for month in months)


def test_gig_income_varies_substantially_more_than_salaried_income():
    profiles = generate_population(seed=19)
    def within_user_cv(profile):
        incomes = [float(month.income) for month in generate_trajectory(profile, months=12, seed=77)]
        return pstdev(incomes) / float(profile.base_monthly_income)
    gig = [within_user_cv(profile) for profile in islice(
        (p for p in profiles if p.persona == "gig_worker"), 100)]
    salaried = [within_user_cv(profile) for profile in islice(
        (p for p in profiles if p.persona == "salaried_with_loan"), 100)]
    assert fmean(gig) > 3 * fmean(salaried)


def test_unaffordable_emi_is_marked_missed_and_not_removed_from_debt():
    debt = SyntheticDebt("personal", Decimal("100.00"), Decimal("0.12"), Decimal("30.00"), 4)
    profile = replace(
        _profile(), base_monthly_income=Decimal("100.00"),
        fixed_monthly_expenses=Decimal("100.00"), variable_monthly_expenses=Decimal("0.00"),
        monthly_expenses=Decimal("130.00"), monthly_debt_payments=Decimal("30.00"),
        existing_debt=Decimal("100.00"), debts=(debt,), savings=Decimal("0.00"),
        emergency_fund=Decimal("0.00"), monthly_savings_contribution=Decimal("0.00"),
    )
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0)[0]
    assert month.scheduled_emi == Decimal("30.00")
    assert month.paid_emi == Decimal("0.00")
    assert month.missed_payment
    assert month.outstanding_debt == Decimal("101.00")
    assert month.debt_to_income_ratio == Decimal("0.3000")


def test_non_emergency_savings_are_used_before_emergency_reserve():
    profile = replace(
        _profile(), base_monthly_income=Decimal("100.00"),
        fixed_monthly_expenses=Decimal("110.00"), variable_monthly_expenses=Decimal("0.00"),
        monthly_expenses=Decimal("110.00"), monthly_savings_contribution=Decimal("0.00"),
    )
    months = generate_trajectory(profile, months=2, seed=4, expense_volatility=0)
    assert [month.savings for month in months] == [Decimal("10.00"), Decimal("0.00")]
    assert [month.emergency_fund for month in months] == [Decimal("10.00"), Decimal("0.00")]


def test_selected_user_export_has_twelve_rows_and_matching_digest(tmp_path):
    path = tmp_path / "trajectories.jsonl"
    report = export_trajectories(path, population_seed=91, trajectory_seed=22,
                                 months=12, synthetic_id=1)
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode().splitlines()]
    assert len(rows) == 12
    assert {row["synthetic_id"] for row in rows} == {1}
    assert [row["month_index"] for row in rows] == list(range(1, 13))
    assert report["dataset_version"] == "synthetic-trajectories-v1"
    assert report["user_count"] == 1 and report["monthly_state_count"] == 12
    assert report["sha256"] == sha256(payload).hexdigest()
    assert json.loads(path.with_suffix(".summary.json").read_text()) == report
    assert export_trajectories(path, population_seed=91, trajectory_seed=22,
                               months=12, synthetic_id=1) == report
    assert path.read_bytes() == payload


def test_invalid_trajectory_parameters_are_rejected():
    with pytest.raises(ValueError, match="months"):
        generate_trajectory(_profile(), months=0)
    with pytest.raises(ValueError, match="expense_volatility"):
        generate_trajectory(_profile(), expense_volatility=-0.1)
