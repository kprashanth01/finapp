"""Inspectable selection proxy for synthetic monthly states, separate from the v1 DQN."""

import argparse
from datetime import date, timedelta
from decimal import Decimal
import json

from app.advisory.dynamic import (
    HIGH_INCOME_VOLATILITY, DynamicPlanningState, build_dynamic_planning_state,
    reserve_target_months,
)
from app.advisory.rules import HIGH_DTI_PERCENT
from app.rl.reward import RewardAudit, RewardCheck
from app.rl.selection import AGENT_IDS


DYNAMIC_REWARD_VERSION = "dynamic-selection-proxy-v1"
RECENT_INCOME_DROP = Decimal("-0.30")


def audit_dynamic_reward(state: DynamicPlanningState,
                         selected_agents: tuple[str, ...]) -> RewardAudit:
    """Score observable selection coverage, not financial outcomes or advice quality."""
    if not isinstance(state, DynamicPlanningState):
        raise TypeError("A synthetic monthly planning state is required.")
    selected = set(selected_agents)
    if len(selected) != len(selected_agents):
        raise ValueError("Select distinct registered agents.")
    if not selected.issubset(AGENT_IDS):
        raise ValueError("Select registered agents only.")

    has_debt = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
    debt_ratio = state.debt_to_income_percent
    debt_pressure = has_debt and (state.missed_payment or debt_ratio is None
                                  or debt_ratio >= HIGH_DTI_PERCENT)
    cash_pressure = state.net_cash_flow < 0 or state.unfunded_expenses > 0
    recent_drop = (state.recent_income_change_ratio is not None
                   and state.recent_income_change_ratio <= RECENT_INCOME_DROP)
    volatile = state.income_volatility >= HIGH_INCOME_VOLATILITY
    target = reserve_target_months(state)
    reserve_gap = (state.monthly_expenses > 0 and state.emergency_fund_months is not None
                   and state.emergency_fund_months < target)
    unfinished = sum(goal.target_amount > goal.saved_amount for goal in state.goals)
    investment_ready = (state.current_surplus > 0 and state.monthly_expenses > 0
                        and state.emergency_fund_months is not None and not reserve_gap
                        and not state.missed_payment and not state.observed_low_income
                        and not recent_drop and not debt_pressure
                        and (state.investment_horizon_years or 0) > 0)

    relevant = {"budget", "emergency", "risk"}
    if has_debt:
        relevant.add("debt")
    if state.goals:
        relevant.add("goal")
    if investment_ready:
        relevant.add("investment")
    critical = set()
    if cash_pressure or state.observed_low_income or recent_drop:
        critical.add("budget")
    if reserve_gap:
        critical.add("emergency")
    if debt_pressure:
        critical.add("debt")
    if unfinished:
        critical.add("goal")
    if cash_pressure or state.missed_payment or volatile:
        critical.add("risk")

    components = {
        "relevant_coverage": float(len(selected & relevant)),
        "critical_coverage": float(2 * len(selected & critical)),
        "missed_critical_penalty": float(-3 * len(critical - selected)),
        "unneeded_agent_penalty": float(-0.75 * len(selected - relevant)),
        "agent_call_penalty": float(-0.15 * len(selected)),
    }

    def check(agent_id, label, metric, value, unit, operator, threshold, status, triggered, note):
        return RewardCheck(
            agent_id=agent_id, label=label, metric=metric,
            value=None if value is None else str(value).lower() if isinstance(value, bool) else str(value),
            unit=unit, operator=operator, threshold=str(threshold), input_status=status,
            critical=triggered, selected=agent_id in selected, note=note,
        )

    checks = (
        check("budget", "Scheduled cash flow", "net_cash_flow", state.net_cash_flow,
              "currency", "<", 0, "available", state.net_cash_flow < 0,
              "Negative scheduled cash flow makes Budget critical."),
        check("budget", "Unfunded expenses", "unfunded_expenses", state.unfunded_expenses,
              "currency", ">", 0, "available", state.unfunded_expenses > 0,
              "Unfunded scheduled expenses make Budget critical."),
        check("budget", "Observed low income", "observed_low_income", state.observed_low_income,
              "boolean", "==", "true", "available", state.observed_low_income,
              "Income at or below 60% of this synthetic user's base income makes Budget critical."),
        check("budget", "Recent income change", "recent_income_change_ratio",
              state.recent_income_change_ratio, "fraction", "<=", RECENT_INCOME_DROP,
              "unavailable" if state.recent_income_change_ratio is None else "available", recent_drop,
              "A decline of at least 30% makes Budget critical."),
        check("emergency", "Reserve coverage", "emergency_fund_months",
              state.emergency_fund_months, "months", "<", target,
              "not_applicable" if state.monthly_expenses <= 0 else
              "unavailable" if state.emergency_fund_months is None else "available", reserve_gap,
              "The illustrative target is six months during high volatility or observed low income, otherwise three."),
        check("debt", "Scheduled debt payment ratio", "debt_to_income_percent",
              debt_ratio if has_debt else None, "%", ">=", HIGH_DTI_PERCENT,
              "not_applicable" if not has_debt else "unavailable" if debt_ratio is None else "available",
              has_debt and (debt_ratio is None or debt_ratio >= HIGH_DTI_PERCENT),
              "Debt with an unavailable ratio is treated as critical; this is an explicit proxy assumption."),
        check("debt", "Missed payment", "missed_payment", state.missed_payment,
              "boolean", "==", "true", "available" if has_debt else "not_applicable",
              has_debt and state.missed_payment, "A missed scheduled payment makes Debt critical."),
        check("goal", "Unfinished goals", "unfinished_goal_count", unfinished if state.goals else None,
              "goals", ">", 0, "available" if state.goals else "not_applicable", bool(unfinished),
              "An unfinished saved research goal makes Goal planning critical, even when funding may be deferred."),
        check("risk", "Income volatility", "income_volatility", state.income_volatility,
              "fraction", ">=", HIGH_INCOME_VOLATILITY, "available", volatile,
              "At least 25% configured income volatility makes Risk critical."),
        check("risk", "Liquidity pressure", "liquidity_pressure",
              cash_pressure or state.missed_payment, "boolean", "==", "true", "available",
              cash_pressure or state.missed_payment,
              "Negative cash flow, unfunded expenses, or a missed payment make Risk critical."),
        check("investment", "Investment screening gate", "investment_ready", investment_ready,
              "boolean", "==", "true", "available", False,
              "Investment is relevant only with positive surplus, adequate reserve, manageable debt, stable recent income, and positive horizon."),
    )
    return RewardAudit(
        version=DYNAMIC_REWARD_VERSION, components=components,
        relevant_agents=tuple(agent for agent in AGENT_IDS if agent in relevant),
        critical_agents=tuple(agent for agent in AGENT_IDS if agent in critical),
        missed_critical_agents=tuple(agent for agent in AGENT_IDS if agent in critical - selected),
        unneeded_agents=tuple(agent for agent in AGENT_IDS if agent in selected - relevant),
        checks=checks,
    )


def main() -> None:
    """Print reproducible monthly proxy scores without reading user accounts."""
    from app.advisory.state import GoalSnapshot
    from app.rl.dynamic_state import build_dynamic_financial_state
    from app.rl.population import DEFAULT_SEED as POPULATION_SEED, generate_population
    from app.rl.trajectories import (
        DEFAULT_TRAJECTORY_SEED, ShockConfig, generate_trajectory,
    )

    parser = argparse.ArgumentParser(description="Inspect dynamic agent-selection reward components.")
    parser.add_argument("--synthetic-id", type=int, default=1)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--population-seed", type=int, default=POPULATION_SEED)
    parser.add_argument("--seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--selected", nargs="+", choices=AGENT_IDS,
                        default=["budget", "emergency", "risk"])
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
    profiles = generate_population(seed=args.population_seed)
    profile = next((item for item in profiles if item.synthetic_id == args.synthetic_id), None)
    if profile is None:
        parser.error("synthetic-id is outside the generated population")
    use_shocks = args.shocks or args.shock_probability is not None or args.income_volatility is not None
    config = ShockConfig(
        probability=args.shock_probability if args.shock_probability is not None else
        0.10 if args.shocks else 0,
        income_volatility_override=args.income_volatility,
    ) if use_shocks else None
    goals = () if args.goal_target is None else (
        GoalSnapshot(id=1, name="Example goal", target_amount=args.goal_target,
                     saved_amount=Decimal("0"),
                     target_date=date(2026, 10, 1) + timedelta(days=30 * args.goal_months),
                     priority="medium"),
    )
    months = generate_trajectory(profile, months=args.months, seed=args.seed, shock_config=config)
    output = []
    for month in months:
        financial = build_dynamic_financial_state(
            profile, month, income_volatility_override=args.income_volatility,
        )
        state = build_dynamic_planning_state(
            profile, financial, as_of_date=date(2026, 10, 1) + timedelta(days=30 * (month.month_index - 1)),
            goals=goals,
        )
        audit = audit_dynamic_reward(state, tuple(args.selected))
        output.append({
            "month_index": month.month_index, "monthly_income": str(state.monthly_income),
            "net_cash_flow": str(state.net_cash_flow),
            "emergency_fund_months": (str(state.emergency_fund_months)
                                      if state.emergency_fund_months is not None else None),
            "income_volatility": str(state.income_volatility),
            "observed_low_income": state.observed_low_income,
            "missed_payment": state.missed_payment,
            "total_reward": audit.total, "components": audit.components,
            "relevant_agents": audit.relevant_agents,
            "critical_agents": audit.critical_agents,
            "missed_critical_agents": audit.missed_critical_agents,
            "unneeded_agents": audit.unneeded_agents,
            "checks": [check.__dict__ for check in audit.checks],
        })
    print(json.dumps({
        "reward_version": DYNAMIC_REWARD_VERSION, "population_seed": args.population_seed,
        "trajectory_seed": args.seed, "synthetic_id": args.synthetic_id,
        "selected_agents": args.selected, "example_goal": bool(goals), "months": output,
    }, indent=2))


if __name__ == "__main__":
    main()
