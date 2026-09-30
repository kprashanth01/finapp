"""Adapt synthetic months to the existing agents' planning-state interface."""

import argparse
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from typing import Literal, Sequence

from pydantic import ConfigDict

from app.advisory.state import GoalSnapshot, PlanningState
from app.rl.dynamic_state import DynamicFinancialState
from app.rl.population import SyntheticProfile


HIGH_INCOME_VOLATILITY = Decimal("0.25")
HIGH_DEBT_APR = Decimal("0.12")
VOLATILE_RESERVE_MONTHS = Decimal("6")
STABLE_RESERVE_MONTHS = Decimal("3")


class DynamicPlanningState(PlanningState):
    """Research-only monthly context accepted by all six existing agents."""

    model_config = ConfigDict(frozen=True)

    dynamic_context_version: Literal["dynamic-agent-context-v1"] = "dynamic-agent-context-v1"
    fixed_expenses: Decimal
    variable_expenses: Decimal
    current_surplus: Decimal
    net_cash_flow: Decimal
    unfunded_expenses: Decimal
    income_volatility: Decimal
    recent_income_change_ratio: Decimal | None
    observed_low_income: bool
    missed_payment: bool
    highest_debt_apr: Decimal | None


def reserve_target_months(state: DynamicPlanningState) -> Decimal:
    """Illustrative stress rule; the target is not calibrated financial advice."""
    if state.income_volatility >= HIGH_INCOME_VOLATILITY or state.observed_low_income:
        return VOLATILE_RESERVE_MONTHS
    return STABLE_RESERVE_MONTHS


def build_dynamic_planning_state(
    profile: SyntheticProfile,
    month: DynamicFinancialState,
    *,
    as_of_date: date,
    goals: Sequence[GoalSnapshot] = (),
) -> DynamicPlanningState:
    """Expose current simulated amounts, without inventing a savings decision or goal."""
    if (profile.synthetic_id != month.synthetic_id or profile.persona != month.persona
            or profile.dataset_split != month.dataset_split
            or profile.base_monthly_income != month.base_monthly_income):
        raise ValueError("profile and dynamic month identity do not match")
    apr = max((debt.annual_interest_rate for debt in profile.debts), default=None)
    fingerprint_payload = {
        "month": month.model_dump(mode="json"),
        "contract_apr": str(apr) if apr is not None else None,
        "goals": [goal.model_dump(mode="json") for goal in goals],
        "as_of_date": as_of_date.isoformat(),
    }
    fingerprint = sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()
    return DynamicPlanningState(
        monthly_income=month.monthly_income,
        monthly_expenses=month.monthly_expenses,
        monthly_savings_contribution=None,
        monthly_debt_payments=month.scheduled_emi,
        existing_debt=month.outstanding_debt,
        emergency_fund=month.emergency_fund,
        savings_rate_percent=None,
        debt_to_income_percent=(month.debt_to_income_ratio * 100
                                if month.debt_to_income_ratio is not None else None),
        expense_to_income_percent=(month.expense_to_income_ratio * 100
                                   if month.expense_to_income_ratio is not None else None),
        emergency_fund_months=month.emergency_fund_months,
        input_fingerprint=fingerprint,
        savings=month.savings,
        risk_tolerance=month.risk_tolerance,
        investment_horizon_years=month.investment_horizon_years,
        financial_goal=None,
        goals=tuple(goals),
        as_of_date=as_of_date,
        fixed_expenses=month.fixed_expenses,
        variable_expenses=month.monthly_expenses - month.fixed_expenses - month.scheduled_emi,
        current_surplus=max(Decimal("0"), month.net_cash_flow),
        net_cash_flow=month.net_cash_flow,
        unfunded_expenses=month.unfunded_expenses,
        income_volatility=month.income_volatility,
        recent_income_change_ratio=month.income_change_ratio,
        observed_low_income=month.observed_low_income,
        missed_payment=month.missed_payment,
        highest_debt_apr=apr,
    )


def main() -> None:
    """Print each existing agent's structured output for reproducible synthetic months."""
    from app.advisory.registry import AgentRegistry
    from app.rl.dynamic_state import build_dynamic_financial_state
    from app.rl.population import DEFAULT_SEED as DEFAULT_POPULATION_SEED, generate_population
    from app.rl.trajectories import DEFAULT_TRAJECTORY_SEED, ShockConfig, generate_trajectory

    parser = argparse.ArgumentParser(description="Preview six agents on changing synthetic monthly states.")
    parser.add_argument("--synthetic-id", type=int, default=1)
    parser.add_argument("--population-seed", type=int, default=DEFAULT_POPULATION_SEED)
    parser.add_argument("--trajectory-seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date(2026, 10, 1))
    parser.add_argument("--shocks", action="store_true")
    parser.add_argument("--shock-probability", type=float)
    parser.add_argument("--income-volatility", type=float)
    parser.add_argument("--goal-target", type=Decimal)
    parser.add_argument("--goal-months", type=int)
    args = parser.parse_args()
    if (args.goal_target is None) != (args.goal_months is None):
        parser.error("--goal-target and --goal-months must be supplied together")
    if args.goal_target is not None and (args.goal_target <= 0 or not 1 <= args.goal_months <= 120):
        parser.error("the example goal needs a positive target and 1–120 months")
    profile = next((p for p in generate_population(seed=args.population_seed)
                    if p.synthetic_id == args.synthetic_id), None)
    if profile is None:
        parser.error("synthetic-id must identify a generated profile")
    use_shocks = (args.shocks or args.shock_probability is not None
                  or args.income_volatility is not None)
    shock_config = (ShockConfig(
        probability=(args.shock_probability if args.shock_probability is not None else
                     0.10 if args.shocks else 0),
        income_volatility_override=args.income_volatility,
    ) if use_shocks else None)
    goals = () if args.goal_target is None else (
        GoalSnapshot(id=1, name="Example goal", target_amount=args.goal_target,
                     saved_amount=Decimal("0"),
                     target_date=args.as_of_date + timedelta(days=30 * args.goal_months),
                     priority="medium"),
    )
    registry = AgentRegistry.default()
    months = generate_trajectory(profile, months=args.months, seed=args.trajectory_seed,
                                 shock_config=shock_config)
    rows = []
    for month in months:
        dynamic = build_dynamic_financial_state(
            profile, month, income_volatility_override=args.income_volatility,
        )
        state = build_dynamic_planning_state(
            profile, dynamic, as_of_date=args.as_of_date + timedelta(days=30 * (month.month_index - 1)),
            goals=goals,
        )
        rows.append({"month": month.month_index,
                     "state": state.model_dump(mode="json", exclude={"goals"}),
                     "agents": {agent_id: registry.get(agent_id).analyze(state).model_dump(mode="json")
                                for agent_id in registry.agent_ids}})
    print(json.dumps({"version": "dynamic-agent-context-v1", "synthetic_id": profile.synthetic_id,
                      "persona": profile.persona,
                      "example_goal": bool(goals),
                      "months": rows}, indent=2))


if __name__ == "__main__":
    # `python -m` names this module __main__. Run through its canonical import
    # so isinstance checks in the already imported agents see the same class.
    from app.advisory.dynamic import main as canonical_main
    canonical_main()
