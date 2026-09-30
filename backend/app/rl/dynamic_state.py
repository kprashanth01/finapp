"""Versioned monthly research state and observation; leaves the saved Advisor contract intact."""

import argparse
from decimal import Decimal
import json
from math import log1p
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from app.rl.population import DEFAULT_SEED as DEFAULT_POPULATION_SEED, Persona, SyntheticProfile, generate_population
from app.rl.splits import assign_user_splits
from app.rl.trajectories import (
    DEFAULT_MONTHS, DEFAULT_TRAJECTORY_SEED, EventType, MonthlyFinancialState,
    ShockConfig, generate_trajectory,
)


DYNAMIC_STATE_VERSION = "dynamic-financial-state-v1"
DYNAMIC_OBSERVATION_VERSION = "dynamic-observation-v1"

# Each number is an observable household fact. Identity, train/test membership,
# persona, and the simulator's hidden event label are intentionally excluded.
DYNAMIC_FEATURE_NAMES = (
    "income_log_scaled", "expense_income_scaled", "fixed_expense_income_scaled",
    "scheduled_emi_income_scaled", "liquid_savings_months_scaled",
    "emergency_months_scaled", "debt_yearly_income_scaled",
    "income_volatility_scaled", "recent_income_change_clipped",
    "cash_flow_income_clipped", "unfunded_expense_fraction",
    "missed_payment", "observed_low_income", "horizon_scaled",
    "risk_conservative", "risk_moderate", "risk_aggressive",
    "income_zero", "recent_change_missing",
)

DYNAMIC_FEATURE_RATIONALE = {
    "income_log_scaled": "Absolute monthly earning capacity, compressed for the synthetic income range.",
    "expense_income_scaled": "Share of income required by all scheduled monthly obligations.",
    "fixed_expense_income_scaled": "Non-discretionary spending pressure, separate from total expenses.",
    "scheduled_emi_income_scaled": "Debt-service burden before any missed payment.",
    "liquid_savings_months_scaled": "Total liquid buffer relative to scheduled monthly expenses.",
    "emergency_months_scaled": "Earmarked emergency reserve coverage, distinct from total savings.",
    "debt_yearly_income_scaled": "Outstanding principal relative to annualized current income.",
    "income_volatility_scaled": "Expected variation in income from the experiment configuration.",
    "recent_income_change_clipped": "Direction and size of change from the prior month's income.",
    "cash_flow_income_clipped": "Current scheduled surplus or deficit relative to income.",
    "unfunded_expense_fraction": "Share of scheduled expenses that available money could not cover.",
    "missed_payment": "Whether any scheduled EMI was not paid this month.",
    "observed_low_income": "Income at or below 60% of this user's base income, derived from observed amounts.",
    "horizon_scaled": "Time available for the user's stated investment horizon.",
    "risk_conservative": "Conservative risk preference as one categorical indicator.",
    "risk_moderate": "Moderate risk preference as one categorical indicator.",
    "risk_aggressive": "Aggressive risk preference as one categorical indicator.",
    "income_zero": "Flags that income-based ratios have a zero denominator.",
    "recent_change_missing": "Flags that recent income change is undefined after a zero-income month.",
}


class DynamicFinancialState(BaseModel):
    """One synthetic user's observed financial condition in one month."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_version: Literal["dynamic-financial-state-v1"] = DYNAMIC_STATE_VERSION
    synthetic_id: int
    persona: Persona
    dataset_split: Literal["train", "test"] | None
    month_index: int
    monthly_income: Decimal
    base_monthly_income: Decimal
    monthly_expenses: Decimal
    fixed_expenses: Decimal
    scheduled_emi: Decimal
    paid_emi: Decimal
    savings: Decimal
    emergency_fund: Decimal
    investment_value: Decimal
    outstanding_debt: Decimal
    unfunded_expenses: Decimal
    net_cash_flow: Decimal
    income_volatility: Decimal
    income_change_ratio: Decimal | None
    expense_to_income_ratio: Decimal | None
    debt_to_income_ratio: Decimal | None
    emergency_fund_months: Decimal | None
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    investment_horizon_years: int
    missed_payment: bool
    observed_low_income: bool
    liquidity_pressure: bool
    simulated_event_type: EventType | None  # Inspection metadata, never an observation feature.


def build_dynamic_financial_state(profile: SyntheticProfile, month: MonthlyFinancialState, *,
                                  income_volatility_override: float | None = None) -> DynamicFinancialState:
    """Join a generated profile and its month; reject mismatched identities or splits."""
    if profile.synthetic_id != month.synthetic_id or profile.persona != month.persona or \
            profile.generation_seed != month.population_seed:
        raise ValueError("profile and month identity do not match")
    if profile.dataset_split != month.dataset_split:
        raise ValueError("profile and month split do not match")
    if month.month_index < 1:
        raise ValueError("month_index must be positive")
    if any(value < 0 for value in (
        month.income, month.scheduled_expenses, month.fixed_expenses, month.variable_expenses,
        month.scheduled_emi, month.paid_emi, month.savings, month.emergency_fund,
        month.investment_value, month.outstanding_debt, month.unfunded_expenses,
    )) or month.scheduled_expenses != month.fixed_expenses + month.variable_expenses + month.scheduled_emi or \
            month.emergency_fund > month.savings or month.paid_emi > month.scheduled_emi:
        raise ValueError("monthly financial totals are inconsistent")
    if income_volatility_override is not None and not 0 <= income_volatility_override <= 1:
        raise ValueError("income_volatility_override must be between 0 and 1")
    volatility = (Decimal(str(income_volatility_override)) if income_volatility_override is not None
                  else profile.income_volatility)
    return DynamicFinancialState(
        synthetic_id=profile.synthetic_id, persona=profile.persona,
        dataset_split=profile.dataset_split, month_index=month.month_index,
        monthly_income=month.income, base_monthly_income=profile.base_monthly_income,
        monthly_expenses=month.scheduled_expenses, fixed_expenses=month.fixed_expenses,
        scheduled_emi=month.scheduled_emi, paid_emi=month.paid_emi,
        savings=month.savings, emergency_fund=month.emergency_fund,
        investment_value=month.investment_value,
        outstanding_debt=month.outstanding_debt, unfunded_expenses=month.unfunded_expenses,
        net_cash_flow=month.net_cash_flow, income_volatility=volatility,
        income_change_ratio=month.income_change_ratio,
        expense_to_income_ratio=month.expense_to_income_ratio,
        debt_to_income_ratio=month.debt_to_income_ratio,
        emergency_fund_months=month.emergency_fund_months,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon_years=profile.investment_horizon_years,
        missed_payment=month.missed_payment,
        observed_low_income=month.income <= profile.base_monthly_income * Decimal("0.60"),
        liquidity_pressure=month.net_cash_flow < 0 or month.unfunded_expenses > 0 or month.missed_payment,
        simulated_event_type=getattr(month, "event_type", None),
    )


def _scaled_ratio(numerator: Decimal, denominator: Decimal, ceiling: float) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(0.0, float(numerator / denominator) / ceiling))


def _clipped_ratio(numerator: Decimal, denominator: Decimal) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(-1.0, float(numerator / denominator)))


def encode_dynamic_observation(state: DynamicFinancialState) -> np.ndarray:
    """Encode observable facts to [-1, 1]; metadata cannot leak into the policy."""
    income = state.monthly_income
    expenses = state.monthly_expenses
    values = (
        min(1.0, max(0.0, log1p(float(income)) / log1p(200_000))),
        _scaled_ratio(expenses, income, 2),
        _scaled_ratio(state.fixed_expenses, income, 2),
        _scaled_ratio(state.scheduled_emi, income, 1),
        _scaled_ratio(state.savings, expenses, 12),
        _scaled_ratio(state.emergency_fund, expenses, 12),
        _scaled_ratio(state.outstanding_debt, income * 12, 5),
        min(1.0, max(0.0, float(state.income_volatility))),
        min(1.0, max(-1.0, float(state.income_change_ratio or 0))),
        _clipped_ratio(state.net_cash_flow, income),
        _scaled_ratio(state.unfunded_expenses, expenses, 1),
        float(state.missed_payment),
        float(state.observed_low_income),
        min(1.0, max(0.0, state.investment_horizon_years / 40)),
        float(state.risk_tolerance == "conservative"),
        float(state.risk_tolerance == "moderate"),
        float(state.risk_tolerance == "aggressive"),
        float(income <= 0),
        float(state.income_change_ratio is None),
    )
    vector = np.asarray(values, dtype=np.float32)
    if not np.isfinite(vector).all():
        raise ValueError("dynamic observation contains non-finite values")
    return vector


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview versioned monthly research observations for one user.")
    parser.add_argument("--synthetic-id", type=int, default=1)
    parser.add_argument("--population-seed", type=int, default=DEFAULT_POPULATION_SEED)
    parser.add_argument("--trajectory-seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--split-seed", type=int)
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS)
    parser.add_argument("--shocks", action="store_true")
    parser.add_argument("--income-volatility", type=float)
    args = parser.parse_args()
    profiles = generate_population(seed=args.population_seed)
    if args.split_seed is not None:
        profiles = assign_user_splits(profiles, seed=args.split_seed)
    profile = next((row for row in profiles if row.synthetic_id == args.synthetic_id), None)
    if profile is None:
        parser.error("synthetic-id must identify a generated profile")
    shocks = ShockConfig(income_volatility_override=args.income_volatility) \
        if args.shocks or args.income_volatility is not None else None
    months = generate_trajectory(profile, months=args.months, seed=args.trajectory_seed,
                                 shock_config=shocks)
    rows = []
    for month in months:
        state = build_dynamic_financial_state(
            profile, month,
            income_volatility_override=shocks.income_volatility_override if shocks else None,
        )
        rows.append({"state": state.model_dump(mode="json"),
                     "observation": encode_dynamic_observation(state).tolist()})
    print(json.dumps({"state_version": DYNAMIC_STATE_VERSION,
                      "observation_version": DYNAMIC_OBSERVATION_VERSION,
                      "feature_names": DYNAMIC_FEATURE_NAMES,
                      "feature_rationale": DYNAMIC_FEATURE_RATIONALE,
                      "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
