"""Small, ephemeral coverage scenarios for method validation, not customer data."""

from datetime import date, timedelta
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

import numpy as np

from app.advisory.state import PlanningState, build_planning_state
from app.services.financial_analysis import FinancialAnalysisService

SCENARIO_VERSION = "coverage-scenarios-v1"
AS_OF_DATE = date(2026, 9, 29)
CENT = Decimal("0.01")


@dataclass(frozen=True)
class ScenarioSplits:
    training: tuple[PlanningState, ...]
    validation: tuple[PlanningState, ...]
    test: tuple[PlanningState, ...]
    seeds: dict[str, int]


def build_splits(*, training_count: int = 1536, validation_count: int = 384,
                 test_count: int = 384, training_seed: int = 20260929,
                 validation_seed: int = 20260930, test_seed: int = 20261001) -> ScenarioSplits:
    """Create separate generated cases; no saved user data enters these splits."""
    counts = (training_count, validation_count, test_count)
    seeds = (training_seed, validation_seed, test_seed)
    if any(count < 1 for count in counts) or len(set(seeds)) != 3:
        raise ValueError("Splits need positive counts and distinct seeds.")
    groups = tuple(tuple(generate_scenarios(count, seed=seed))
                   for count, seed in zip(counts, seeds))
    fingerprints = [set(state.fingerprint() for state in group) for group in groups]
    if any(a.intersection(b) for index, a in enumerate(fingerprints)
           for b in fingerprints[index + 1:]):
        raise ValueError("Scenario splits overlap.")
    return ScenarioSplits(*groups, seeds=dict(zip(("training", "validation", "test"), seeds)))


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def generate_scenarios(count: int, *, seed: int) -> list[PlanningState]:
    """Vary application inputs; rows never enter the app database.

    These figures are explicit assumptions for checking policy mechanics. They
    are not sampled from a household survey and carry no outcome labels.
    """
    if count < 1:
        raise ValueError("Generate at least one scenario.")
    rng = np.random.default_rng(seed)
    states: list[PlanningState] = []
    for index in range(count):
        income = _money(rng.uniform(1800, 14000))
        expense_fraction = (0.38, 0.62, 0.83, 1.04)[index % 4] + rng.uniform(-0.035, 0.035)
        expenses = _money(float(income) * expense_fraction)
        debt_mode = (index // 4) % 4
        debt = _money(float(income) * 12 * (0.0, 0.12, 0.65, 1.8)[debt_mode])
        debt_payment = (None if debt_mode == 3 and index % 2 == 0 else
                        _money(min(float(expenses), float(income) * (0.0, 0.04, 0.14, 0.27)[debt_mode])))
        reserve_months = (0.0, 0.8, 2.4, 3.5, 6.5)[index % 5] + rng.uniform(0, 0.15)
        emergency = _money(float(expenses) * reserve_months)
        contribution = None if index % 5 == 0 else _money(float(income) * (0.04, 0.12, 0.23)[index % 3])
        horizon = (None, 2, 5, 12)[(index // 3) % 4]
        goal_mode = (index // 8) % 4
        goals = []
        if goal_mode:
            target = _money(float(income) * (3 + goal_mode * 2))
            saved = _money(float(target) * (0.0, 0.25, 0.8)[goal_mode - 1])
            days = (-20, 180, 720)[goal_mode - 1]
            goals.append(SimpleNamespace(
                id=index + 1, name="Scenario goal", target_amount=target, saved_amount=saved,
                target_date=AS_OF_DATE + timedelta(days=days),
                priority=("high", "medium", "low")[goal_mode - 1], archived=False,
            ))
        user = SimpleNamespace(monthly_income=income)
        profile = SimpleNamespace(
            monthly_expenses=expenses, savings=emergency + _money(rng.uniform(0, 5000)),
            existing_debt=debt, emergency_fund=emergency,
            monthly_savings_contribution=contribution, monthly_debt_payments=debt_payment,
            risk_tolerance=("conservative", "moderate", "aggressive")[index % 3],
            investment_horizon_years=horizon, financial_goal=None,
        )
        analysis = FinancialAnalysisService.analyze(user, profile)
        states.append(build_planning_state(user, profile, analysis, goals, AS_OF_DATE))
    return states
