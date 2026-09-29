"""Versioned, bounded numerical view of the same saved planning state."""

from datetime import date

import numpy as np

from app.advisory.state import PlanningState

OBSERVATION_VERSION = "planning-observation-v1"
FEATURE_NAMES = (
    "expense_income_scaled", "savings_income_scaled", "debt_payment_income_scaled",
    "emergency_months_scaled", "debt_balance_yearly_income_scaled", "active_goals_scaled",
    "nearest_goal_years_scaled", "goal_gap_yearly_income_scaled", "horizon_scaled",
    "risk_conservative", "risk_moderate", "risk_aggressive", "savings_missing",
    "debt_payment_missing", "horizon_missing", "income_missing",
)


def _bounded(value, denominator, ceiling=2.0):
    if value is None or denominator <= 0:
        return 0.0
    return min(ceiling, max(0.0, float(value / denominator)))


def encode_observation(state: PlanningState) -> np.ndarray:
    """Convert money to ratios; zero plus flags represents missing values."""
    income = state.monthly_income
    active = [goal for goal in state.goals if goal.target_amount > goal.saved_amount]
    nearest = min((max(0, (goal.target_date - state.as_of_date).days) for goal in active), default=0)
    goal_gap = sum((max(0, goal.target_amount - goal.saved_amount) for goal in active), 0)
    values = (
        _bounded(state.monthly_expenses, income),
        _bounded(state.monthly_savings_contribution, income, 1.0),
        _bounded(state.monthly_debt_payments, income, 1.0),
        _bounded(state.emergency_fund_months, 6),
        _bounded(state.existing_debt, income * 12),
        min(1.0, len(active) / 5),
        min(2.0, nearest / 365),
        _bounded(goal_gap, income * 12),
        min(1.0, max(0, (state.investment_horizon_years or 0) / 20)),
        float(state.risk_tolerance == "conservative"),
        float(state.risk_tolerance == "moderate"),
        float(state.risk_tolerance == "aggressive"),
        float(state.monthly_savings_contribution is None),
        float(state.monthly_debt_payments is None),
        float(state.investment_horizon_years is None),
        float(income <= 0),
    )
    return np.asarray(values, dtype=np.float32)
