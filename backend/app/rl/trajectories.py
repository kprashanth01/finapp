"""Seeded monthly household states for offline research, independent of advisory actions."""

import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import fmean, pstdev

from app.rl.population import (
    CENT, DEFAULT_SEED as DEFAULT_POPULATION_SEED, POPULATION_VERSION,
    DatasetSplit, Persona, SyntheticProfile, generate_population, validate_profile,
)


TRAJECTORY_VERSION = "synthetic-trajectories-v1"
DEFAULT_TRAJECTORY_SEED = 20261001
DEFAULT_MONTHS = 12
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "trajectories-v1.jsonl"
ZERO = Decimal("0.00")
RATIO = Decimal("0.0001")


@dataclass(frozen=True)
class MonthlyFinancialState:
    synthetic_id: int
    persona: Persona
    population_seed: int
    trajectory_seed: int
    dataset_split: DatasetSplit | None
    month_index: int
    income: Decimal
    fixed_expenses: Decimal
    variable_expenses: Decimal
    scheduled_emi: Decimal
    paid_emi: Decimal
    scheduled_expenses: Decimal  # Includes scheduled EMI.
    unfunded_expenses: Decimal  # Non-debt expenses the household could not fund.
    net_cash_flow: Decimal  # Income minus scheduled expenses, before reserve draw.
    savings: Decimal  # Total liquid balance; includes emergency fund.
    emergency_fund: Decimal
    investment_value: Decimal  # Zero until a portfolio model is introduced.
    outstanding_debt: Decimal
    missed_payment: bool
    income_change_ratio: Decimal | None
    debt_to_income_ratio: Decimal | None
    expense_to_income_ratio: Decimal | None
    emergency_fund_months: Decimal | None


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return (numerator / denominator).quantize(RATIO) if denominator > 0 else None


def _rng(profile: SyntheticProfile, seed: int) -> random.Random:
    identity = f"{profile.generation_seed}:{profile.synthetic_id}:{seed}".encode("ascii")
    return random.Random(int.from_bytes(sha256(identity).digest(), "big"))


def generate_trajectory(profile: SyntheticProfile, *, months: int = DEFAULT_MONTHS,
                        seed: int = DEFAULT_TRAJECTORY_SEED,
                        expense_volatility: float = 0.08) -> tuple[MonthlyFinancialState, ...]:
    """Simulate changing income and cash/debt balances without taking advisory actions."""
    if not 1 <= months <= 120:
        raise ValueError("months must be between 1 and 120")
    if not 0 <= expense_volatility <= 1:
        raise ValueError("expense_volatility must be between 0 and 1")
    validate_profile(profile)
    rng = _rng(profile, seed)
    savings = profile.savings
    emergency = profile.emergency_fund
    debt_balances = [debt.outstanding_principal for debt in profile.debts]
    previous_income = profile.base_monthly_income
    states = []

    for month_index in range(1, months + 1):
        income = _money(max(0, float(profile.base_monthly_income) *
                            (1 + rng.gauss(0, float(profile.income_volatility)))))
        fixed = profile.fixed_monthly_expenses
        variable = _money(max(0, float(profile.variable_monthly_expenses) *
                              (1 + rng.gauss(0, expense_volatility))))

        balances_with_interest = []
        scheduled_by_debt = []
        for debt, balance in zip(profile.debts, debt_balances, strict=True):
            with_interest = (balance * (1 + debt.annual_interest_rate / 12)).quantize(CENT)
            balances_with_interest.append(with_interest)
            scheduled_by_debt.append(min(debt.monthly_emi, with_interest))
        scheduled_emi = sum(scheduled_by_debt, ZERO)
        scheduled_expenses = fixed + variable + scheduled_emi

        # Fixed necessities, then debt obligations, then variable spending. Existing liquid
        # savings cover a deficit; a remaining shortfall is recorded, never made negative.
        available = income + savings
        paid_fixed = min(fixed, available)
        available -= paid_fixed
        paid_emi = min(scheduled_emi, available)
        available -= paid_emi
        paid_variable = min(variable, available)
        available -= paid_variable
        unfunded = fixed - paid_fixed + variable - paid_variable

        unpaid_emi_budget = paid_emi
        next_balances = []
        for with_interest, scheduled in zip(balances_with_interest, scheduled_by_debt, strict=True):
            payment = min(scheduled, unpaid_emi_budget)
            unpaid_emi_budget -= payment
            next_balances.append(with_interest - payment)
        debt_balances = next_balances
        savings = available
        emergency = min(emergency, savings)  # Other savings are spent before earmarked reserves.

        states.append(MonthlyFinancialState(
            synthetic_id=profile.synthetic_id, persona=profile.persona,
            population_seed=profile.generation_seed, trajectory_seed=seed,
            dataset_split=profile.dataset_split, month_index=month_index,
            income=income, fixed_expenses=fixed, variable_expenses=variable,
            scheduled_emi=scheduled_emi, paid_emi=paid_emi,
            scheduled_expenses=scheduled_expenses, unfunded_expenses=unfunded,
            net_cash_flow=income - scheduled_expenses,
            savings=savings, emergency_fund=emergency,
            investment_value=ZERO, outstanding_debt=sum(debt_balances, ZERO),
            missed_payment=paid_emi < scheduled_emi,
            income_change_ratio=_ratio(income - previous_income, previous_income),
            debt_to_income_ratio=_ratio(scheduled_emi, income),
            expense_to_income_ratio=_ratio(scheduled_expenses, income),
            emergency_fund_months=_ratio(emergency, scheduled_expenses),
        ))
        previous_income = income
    return tuple(states)


def export_trajectories(path: Path, *, population_seed: int = DEFAULT_POPULATION_SEED,
                        trajectory_seed: int = DEFAULT_TRAJECTORY_SEED,
                        months: int = DEFAULT_MONTHS, synthetic_id: int | None = None,
                        expense_volatility: float = 0.08) -> dict:
    """Stream monthly JSONL and a reproducibility/variation summary to disk."""
    profiles = generate_population(seed=population_seed)
    if synthetic_id is not None:
        profiles = [profile for profile in profiles if profile.synthetic_id == synthetic_id]
        if not profiles:
            raise ValueError("synthetic_id must identify a generated profile")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    persona_stats: dict[str, dict[str, int | list[float]]] = {}
    count = 0
    with path.open("wb") as output:
        for profile in profiles:
            states = generate_trajectory(profile, months=months, seed=trajectory_seed,
                                         expense_volatility=expense_volatility)
            stats = persona_stats.setdefault(profile.persona, {"users": 0, "missed_payment_months": 0,
                                                              "unfunded_expense_months": 0, "income_cv": []})
            stats["users"] += 1
            incomes = [float(state.income) for state in states]
            stats["income_cv"].append(pstdev(incomes) / float(profile.base_monthly_income))
            for state in states:
                stats["missed_payment_months"] += state.missed_payment
                stats["unfunded_expense_months"] += state.unfunded_expenses > 0
                line = (json.dumps(asdict(state), default=str, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8")
                output.write(line)
                digest.update(line)
                count += 1
    report = {
        "dataset_version": TRAJECTORY_VERSION,
        "population_version": POPULATION_VERSION,
        "population_seed": population_seed,
        "trajectory_seed": trajectory_seed,
        "months_per_user": months,
        "expense_volatility": expense_volatility,
        "synthetic_id_filter": synthetic_id,
        "user_count": len(profiles),
        "monthly_state_count": count,
        "sha256": digest.hexdigest(),
        "mean_within_user_income_cv_note": "Mean monthly income standard deviation divided by each user's base income; not cross-user dispersion.",
        "personas": {
            name: {
                "users": stats["users"],
                "mean_within_user_income_cv": round(fmean(stats["income_cv"]), 4),
                "missed_payment_months": stats["missed_payment_months"],
                "unfunded_expense_months": stats["unfunded_expense_months"],
            }
            for name, stats in persona_stats.items()
        },
    }
    path.with_suffix(".summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline monthly financial trajectories.")
    parser.add_argument("--population-seed", type=int, default=DEFAULT_POPULATION_SEED)
    parser.add_argument("--trajectory-seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS)
    parser.add_argument("--synthetic-id", type=int, help="Export one user for inspection; omit for all 12,000")
    parser.add_argument("--expense-volatility", type=float, default=0.08)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(export_trajectories(
        args.output, population_seed=args.population_seed, trajectory_seed=args.trajectory_seed,
        months=args.months, synthetic_id=args.synthetic_id,
        expense_volatility=args.expense_volatility,
    ), indent=2))


if __name__ == "__main__":
    main()
