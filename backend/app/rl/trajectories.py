"""Seeded monthly household states for offline research, independent of advisory actions."""

import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import random
from statistics import fmean, pstdev
from typing import Literal

from app.rl.population import (
    CENT, DEFAULT_SEED as DEFAULT_POPULATION_SEED, POPULATION_VERSION,
    DatasetSplit, Persona, SyntheticProfile, generate_population, validate_profile,
)
from app.rl.splits import SPLIT_VERSION, assign_user_splits


TRAJECTORY_VERSION = "synthetic-trajectories-v1"
SHOCK_TRAJECTORY_VERSION = "synthetic-trajectories-v2"
SPLIT_TRAJECTORY_VERSION = "synthetic-trajectories-v3"
SHOCK_SPLIT_TRAJECTORY_VERSION = "synthetic-trajectories-v4"
DEFAULT_TRAJECTORY_SEED = 20261001
DEFAULT_MONTHS = 12
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "trajectories-v1.jsonl"
DEFAULT_SHOCK_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "trajectories-v2.jsonl"
ZERO = Decimal("0.00")
RATIO = Decimal("0.0001")
EventType = Literal["low_income", "temporary_income_loss", "high_income", "unexpected_expense",
                    "emergency_expense", "debt_pressure"]
EVENT_TYPES: tuple[EventType, ...] = ("low_income", "temporary_income_loss", "high_income",
                                      "unexpected_expense", "emergency_expense", "debt_pressure")


@dataclass(frozen=True)
class ShockConfig:
    probability: float = 0.10  # Chance of a new event in a month without an active income loss.
    magnitude: float = 0.50  # Fractional income change or extra EMI.
    unexpected_expense: Decimal = Decimal("20000.00")
    emergency_expense: Decimal = Decimal("30000.00")
    income_loss_months: int = 2
    income_volatility_override: float | None = None
    event_types: tuple[EventType, ...] = EVENT_TYPES

    def __post_init__(self) -> None:
        if not isfinite(self.probability) or not 0 <= self.probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        if not isfinite(self.magnitude) or not 0 <= self.magnitude <= 1:
            raise ValueError("magnitude must be between 0 and 1")
        if not self.unexpected_expense.is_finite() or self.unexpected_expense < 0 or \
                not self.emergency_expense.is_finite() or self.emergency_expense < 0:
            raise ValueError("event expense amounts must be nonnegative")
        if self.unexpected_expense != self.unexpected_expense.quantize(CENT) or \
                self.emergency_expense != self.emergency_expense.quantize(CENT):
            raise ValueError("event expense amounts must use cents")
        if self.income_loss_months < 1 or self.income_loss_months > 12:
            raise ValueError("income_loss_months must be between 1 and 12")
        if self.income_volatility_override is not None and (
            not isfinite(self.income_volatility_override) or
            not 0 <= self.income_volatility_override <= 1
        ):
            raise ValueError("income_volatility_override must be between 0 and 1")
        if not self.event_types or len(set(self.event_types)) != len(self.event_types) or \
                any(event not in EVENT_TYPES for event in self.event_types):
            raise ValueError("event_types must contain distinct supported events")


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


@dataclass(frozen=True)
class ShockedMonthlyFinancialState(MonthlyFinancialState):
    event_type: EventType | None
    event_started: bool
    income_shock: bool
    event_income_delta: Decimal  # Difference from the same month's unshocked income.
    event_expense: Decimal
    event_emi_extra: Decimal


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return (numerator / denominator).quantize(RATIO) if denominator > 0 else None


def _rng(profile: SyntheticProfile, seed: int) -> random.Random:
    identity = f"{profile.generation_seed}:{profile.synthetic_id}:{seed}".encode("ascii")
    return random.Random(int.from_bytes(sha256(identity).digest(), "big"))


def _event_rng(profile: SyntheticProfile, seed: int) -> random.Random:
    identity = f"{profile.generation_seed}:{profile.synthetic_id}:{seed}:events".encode("ascii")
    return random.Random(int.from_bytes(sha256(identity).digest(), "big"))


def generate_trajectory(profile: SyntheticProfile, *, months: int = DEFAULT_MONTHS,
                        seed: int = DEFAULT_TRAJECTORY_SEED,
                        expense_volatility: float = 0.08,
                        shock_config: ShockConfig | None = None) -> tuple[MonthlyFinancialState, ...]:
    """Simulate changing income and cash/debt balances without taking advisory actions."""
    if not 1 <= months <= 120:
        raise ValueError("months must be between 1 and 120")
    if not 0 <= expense_volatility <= 1:
        raise ValueError("expense_volatility must be between 0 and 1")
    validate_profile(profile)
    rng = _rng(profile, seed)
    event_rng = _event_rng(profile, seed) if shock_config is not None else None
    income_volatility = (shock_config.income_volatility_override
                         if shock_config is not None and shock_config.income_volatility_override is not None
                         else float(profile.income_volatility))
    loss_months_remaining = 0
    savings = profile.savings
    emergency = profile.emergency_fund
    debt_balances = [debt.outstanding_principal for debt in profile.debts]
    previous_income = profile.base_monthly_income
    states = []

    for month_index in range(1, months + 1):
        income = _money(max(0, float(profile.base_monthly_income) *
                            (1 + rng.gauss(0, income_volatility))))
        fixed = profile.fixed_monthly_expenses
        variable = _money(max(0, float(profile.variable_monthly_expenses) *
                              (1 + rng.gauss(0, expense_volatility))))

        event_type: EventType | None = None
        event_started = False
        event_income_delta = ZERO
        event_expense = ZERO
        if shock_config is not None:
            if loss_months_remaining:
                event_type = "temporary_income_loss"
                loss_months_remaining -= 1
            elif event_rng.random() < shock_config.probability:
                eligible = tuple(event for event in shock_config.event_types
                                 if event != "debt_pressure" or any(balance > 0 for balance in debt_balances))
                if eligible:
                    event_type = event_rng.choice(eligible)
                    event_started = True
                    if event_type == "temporary_income_loss":
                        loss_months_remaining = shock_config.income_loss_months - 1
            unshocked_income = income
            if event_type == "low_income":
                income = _money(float(income) * (1 - shock_config.magnitude))
            elif event_type == "temporary_income_loss":
                income = ZERO
            elif event_type == "high_income":
                income = _money(float(income) * (1 + shock_config.magnitude))
            elif event_type == "unexpected_expense":
                event_expense = shock_config.unexpected_expense
                variable += event_expense
            elif event_type == "emergency_expense":
                event_expense = shock_config.emergency_expense
                fixed += event_expense
            event_income_delta = income - unshocked_income

        balances_with_interest = []
        scheduled_by_debt = []
        event_emi_extra = ZERO
        for debt, balance in zip(profile.debts, debt_balances, strict=True):
            with_interest = (balance * (1 + debt.annual_interest_rate / 12)).quantize(CENT)
            balances_with_interest.append(with_interest)
            regular_due = min(debt.monthly_emi, with_interest)
            due = regular_due
            if event_type == "debt_pressure":
                due = min((debt.monthly_emi *
                           (1 + Decimal(str(shock_config.magnitude)))).quantize(CENT), with_interest)
                event_emi_extra += due - regular_due
            scheduled_by_debt.append(due)
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

        state = MonthlyFinancialState(
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
        )
        if shock_config is not None:
            state = ShockedMonthlyFinancialState(
                **asdict(state), event_type=event_type, event_started=event_started,
                income_shock=event_type in ("low_income", "temporary_income_loss", "high_income"),
                event_income_delta=event_income_delta, event_expense=event_expense,
                event_emi_extra=event_emi_extra,
            )
        states.append(state)
        previous_income = income
    return tuple(states)


def export_trajectories(path: Path, *, population_seed: int = DEFAULT_POPULATION_SEED,
                        trajectory_seed: int = DEFAULT_TRAJECTORY_SEED,
                        months: int = DEFAULT_MONTHS, synthetic_id: int | None = None,
                        expense_volatility: float = 0.08,
                        shock_config: ShockConfig | None = None,
                        split_seed: int | None = None,
                        selected_split: DatasetSplit | None = None) -> dict:
    """Stream monthly JSONL and a reproducibility/variation summary to disk."""
    if selected_split is not None and split_seed is None:
        raise ValueError("selected_split requires split_seed")
    if selected_split not in (None, "train", "test"):
        raise ValueError("selected_split must be train or test")
    profiles = generate_population(seed=population_seed)
    if split_seed is not None:
        profiles = assign_user_splits(profiles, seed=split_seed)
    if selected_split is not None:
        profiles = [profile for profile in profiles if profile.dataset_split == selected_split]
    if synthetic_id is not None:
        profiles = [profile for profile in profiles if profile.synthetic_id == synthetic_id]
        if not profiles:
            raise ValueError("synthetic_id must identify a profile in the selected split")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    persona_stats: dict[str, dict[str, int | list[float]]] = {}
    event_months = {event: 0 for event in EVENT_TYPES} if shock_config is not None else None
    event_starts = {event: 0 for event in EVENT_TYPES} if shock_config is not None else None
    count = 0
    with path.open("wb") as output:
        for profile in profiles:
            states = generate_trajectory(profile, months=months, seed=trajectory_seed,
                                         expense_volatility=expense_volatility,
                                         shock_config=shock_config)
            stats = persona_stats.setdefault(profile.persona, {"users": 0, "missed_payment_months": 0,
                                                              "unfunded_expense_months": 0, "income_cv": []})
            stats["users"] += 1
            incomes = [float(state.income) for state in states]
            stats["income_cv"].append(pstdev(incomes) / float(profile.base_monthly_income))
            for state in states:
                if shock_config is not None and state.event_type is not None:
                    event_months[state.event_type] += 1
                    event_starts[state.event_type] += state.event_started
                stats["missed_payment_months"] += state.missed_payment
                stats["unfunded_expense_months"] += state.unfunded_expenses > 0
                line = (json.dumps(asdict(state), default=str, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8")
                output.write(line)
                digest.update(line)
                count += 1
    report = {
        "dataset_version": (
            SHOCK_SPLIT_TRAJECTORY_VERSION if shock_config is not None else SPLIT_TRAJECTORY_VERSION
        ) if split_seed is not None else (
            SHOCK_TRAJECTORY_VERSION if shock_config is not None else TRAJECTORY_VERSION
        ),
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
    if shock_config is not None:
        report["shock_config"] = {
            "probability": shock_config.probability,
            "magnitude": shock_config.magnitude,
            "unexpected_expense": format(shock_config.unexpected_expense.quantize(CENT), ".2f"),
            "emergency_expense": format(shock_config.emergency_expense.quantize(CENT), ".2f"),
            "income_loss_months": shock_config.income_loss_months,
            "income_volatility_override": shock_config.income_volatility_override,
            "event_types": list(shock_config.event_types),
        }
        report["event_months"] = event_months
        report["event_starts"] = event_starts
    if split_seed is not None:
        report["split_version"] = SPLIT_VERSION
        report["split_seed"] = split_seed
        report["selected_split"] = selected_split
    path.with_suffix(".summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline monthly financial trajectories.")
    parser.add_argument("--population-seed", type=int, default=DEFAULT_POPULATION_SEED)
    parser.add_argument("--trajectory-seed", type=int, default=DEFAULT_TRAJECTORY_SEED)
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS)
    parser.add_argument("--synthetic-id", type=int, help="Export one user for inspection; omit for all 12,000")
    parser.add_argument("--expense-volatility", type=float, default=0.08)
    parser.add_argument("--shocks", action="store_true", help="Enable version 2 configurable event simulation")
    parser.add_argument("--shock-probability", type=float)
    parser.add_argument("--shock-magnitude", type=float)
    parser.add_argument("--unexpected-expense", type=Decimal)
    parser.add_argument("--emergency-expense", type=Decimal)
    parser.add_argument("--income-loss-months", type=int)
    parser.add_argument("--income-volatility", type=float, help="Override every profile's relative monthly volatility")
    parser.add_argument("--event-types", nargs="+", choices=EVENT_TYPES)
    parser.add_argument("--split-seed", type=int, help="Assign whole users 80/20 within each persona")
    parser.add_argument("--selected-split", choices=("train", "test"),
                        help="Export only one assigned split; requires --split-seed")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    shock_options = {
        "probability": args.shock_probability,
        "magnitude": args.shock_magnitude,
        "unexpected_expense": args.unexpected_expense,
        "emergency_expense": args.emergency_expense,
        "income_loss_months": args.income_loss_months,
        "income_volatility_override": args.income_volatility,
        "event_types": tuple(args.event_types) if args.event_types is not None else None,
    }
    enable_shocks = args.shocks or any(value is not None for value in shock_options.values())
    shock_config = ShockConfig(**{key: value for key, value in shock_options.items() if value is not None}) \
        if enable_shocks else None
    if args.output is not None:
        output = args.output
    elif args.split_seed is not None:
        version = 4 if enable_shocks else 3
        suffix = f"-{args.selected_split}" if args.selected_split else ""
        output = DEFAULT_OUTPUT.with_name(f"trajectories-v{version}{suffix}.jsonl")
    else:
        output = DEFAULT_SHOCK_OUTPUT if enable_shocks else DEFAULT_OUTPUT
    print(json.dumps(export_trajectories(
        output, population_seed=args.population_seed, trajectory_seed=args.trajectory_seed,
        months=args.months, synthetic_id=args.synthetic_id,
        expense_volatility=args.expense_volatility, shock_config=shock_config,
        split_seed=args.split_seed, selected_split=args.selected_split,
    ), indent=2))


if __name__ == "__main__":
    main()
