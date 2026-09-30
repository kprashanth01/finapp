"""Seeded synthetic profiles for research; never reads or writes account data."""

import argparse
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import fmean, pstdev
from typing import Literal


POPULATION_VERSION = "synthetic-population-v2"
DEFAULT_SEED = 20260930
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "population-v2.jsonl"
CENT = Decimal("0.01")

Persona = Literal["gig_worker", "salaried_with_loan", "student_fresh_graduate", "near_retiree"]
DebtType = Literal["education", "home", "personal", "vehicle"]
DatasetSplit = Literal["train", "test"]


@dataclass(frozen=True)
class PersonaSpec:
    name: Persona
    count: int
    ages: tuple[int, int]
    income_range: tuple[int, int]
    expense_fraction: tuple[float, float]
    debt_probability: float
    horizon_range: tuple[int, int]
    volatility_range: tuple[float, float]
    dependents_range: tuple[int, int]
    debt_types: tuple[DebtType, ...]


# Illustrative experiment assumptions, not population statistics or advice.
PERSONAS = (
    PersonaSpec("gig_worker", 3600, (20, 55), (12000, 80000), (0.50, 0.92), 0.30, (1, 25),
                (0.25, 0.55), (0, 3), ("personal", "vehicle")),
    PersonaSpec("salaried_with_loan", 4200, (23, 60), (25000, 130000), (0.50, 0.85), 1.00, (1, 30),
                (0.02, 0.10), (0, 4), ("home", "personal", "vehicle")),
    PersonaSpec("student_fresh_graduate", 2400, (18, 28), (5000, 40000), (0.42, 0.90), 0.20, (1, 30),
                (0.10, 0.30), (0, 1), ("education", "personal")),
    PersonaSpec("near_retiree", 1800, (55, 72), (18000, 100000), (0.45, 0.83), 0.20, (0, 12),
                (0.03, 0.12), (0, 3), ("home", "personal")),
)


@dataclass(frozen=True)
class SyntheticDebt:
    debt_type: DebtType
    outstanding_principal: Decimal
    annual_interest_rate: Decimal  # Fraction, e.g. 0.12 means 12% APR.
    monthly_emi: Decimal
    remaining_months: int


@dataclass(frozen=True)
class SyntheticProfile:
    synthetic_id: int
    persona: Persona
    generation_seed: int
    age: int
    base_monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_debt_payments: Decimal
    existing_debt: Decimal
    monthly_savings_contribution: Decimal
    emergency_fund: Decimal
    savings: Decimal
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    investment_horizon_years: int
    dependents: int
    income_volatility: Decimal  # Relative monthly standard deviation used by later trajectory generation.
    fixed_monthly_expenses: Decimal  # Excludes EMI.
    variable_monthly_expenses: Decimal
    debts: tuple[SyntheticDebt, ...]
    dataset_split: DatasetSplit | None  # Assigned at the user level in Issue 6.


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def _sample_debts(spec: PersonaSpec, rng: random.Random, payment: Decimal) -> tuple[SyntheticDebt, ...]:
    if payment == 0:
        return ()
    count = 2 if payment >= Decimal("200.00") and rng.random() < 0.25 else 1
    first_payment = _money(float(payment) * rng.uniform(0.30, 0.70)) if count == 2 else payment
    payments = (first_payment, payment - first_payment) if count == 2 else (payment,)
    debts = []
    for emi in payments:
        rate = Decimal(str(round(rng.uniform(0.04, 0.18), 4)))
        months = rng.randint(12, 84)
        monthly_rate = rate / 12
        principal = (emi * (1 - (1 + monthly_rate) ** -months) / monthly_rate).quantize(CENT)
        debts.append(SyntheticDebt(rng.choice(spec.debt_types), principal, rate, emi, months))
    return tuple(debts)


def _sample(spec: PersonaSpec, rng: random.Random, seed: int) -> SyntheticProfile:
    income = _money(rng.uniform(*spec.income_range))
    expenses = _money(float(income) * rng.uniform(*spec.expense_fraction))
    has_debt = rng.random() < spec.debt_probability
    debt_payment = (_money(min(float(expenses) * 0.45, float(income) * rng.uniform(0.04, 0.18)))
                    if has_debt else Decimal("0.00"))
    debts = _sample_debts(spec, rng, debt_payment)
    debt = sum((item.outstanding_principal for item in debts), Decimal("0.00"))
    non_debt_expenses = expenses - debt_payment
    fixed_expenses = _money(float(non_debt_expenses) * rng.uniform(0.55, 0.85))
    variable_expenses = non_debt_expenses - fixed_expenses
    surplus = max(Decimal("0.00"), income - expenses)
    contribution = _money(float(surplus) * rng.uniform(0.10, 0.80))
    emergency = _money(float(expenses) * rng.uniform(0, 6))
    savings = emergency + _money(float(income) * rng.uniform(0, 3))
    return SyntheticProfile(
        synthetic_id=0, persona=spec.name, generation_seed=seed,
        age=rng.randint(*spec.ages), base_monthly_income=income,
        monthly_expenses=expenses, monthly_debt_payments=debt_payment,
        existing_debt=debt, monthly_savings_contribution=contribution,
        emergency_fund=emergency, savings=savings,
        risk_tolerance=rng.choice(("conservative", "moderate", "aggressive")),
        investment_horizon_years=rng.randint(*spec.horizon_range),
        dependents=rng.randint(*spec.dependents_range),
        income_volatility=Decimal(str(round(rng.uniform(*spec.volatility_range), 4))),
        fixed_monthly_expenses=fixed_expenses, variable_monthly_expenses=variable_expenses,
        debts=debts, dataset_split=None,
    )


def validate_profile(profile: SyntheticProfile) -> None:
    """Reject malformed offline profiles before export or trajectory generation."""
    if profile.synthetic_id < 1 or profile.persona not in {spec.name for spec in PERSONAS}:
        raise ValueError("Invalid synthetic identity or persona")
    if not 18 <= profile.age <= 120 or not 0 <= profile.dependents <= 5:
        raise ValueError("Invalid age or dependent count")
    if profile.base_monthly_income <= 0 or not 0 <= profile.income_volatility <= 1:
        raise ValueError("Invalid income assumptions")
    if any(value < 0 for value in (profile.monthly_expenses, profile.fixed_monthly_expenses,
                                  profile.variable_monthly_expenses, profile.existing_debt,
                                  profile.monthly_debt_payments, profile.savings,
                                  profile.emergency_fund, profile.monthly_savings_contribution)):
        raise ValueError("Negative financial balance or expense")
    if profile.fixed_monthly_expenses + profile.variable_monthly_expenses + profile.monthly_debt_payments != profile.monthly_expenses:
        raise ValueError("Expense components do not reconcile")
    if sum((debt.outstanding_principal for debt in profile.debts), Decimal("0.00")) != profile.existing_debt:
        raise ValueError("Debt principal does not reconcile")
    if sum((debt.monthly_emi for debt in profile.debts), Decimal("0.00")) != profile.monthly_debt_payments:
        raise ValueError("Debt payments do not reconcile")
    if any(debt.outstanding_principal <= 0 or debt.monthly_emi <= 0 or debt.remaining_months <= 0
           or not 0 <= debt.annual_interest_rate <= 1 or
           debt.monthly_emi <= debt.outstanding_principal * debt.annual_interest_rate / 12
           for debt in profile.debts):
        raise ValueError("Invalid or non-amortizing debt")
    if profile.savings < profile.emergency_fund or profile.monthly_debt_payments > profile.monthly_expenses:
        raise ValueError("Invalid financial totals")
    if profile.monthly_savings_contribution > max(Decimal("0"), profile.base_monthly_income - profile.monthly_expenses):
        raise ValueError("Savings contribution exceeds available income")
    if profile.risk_tolerance not in ("conservative", "moderate", "aggressive") or not 0 <= profile.investment_horizon_years <= 80:
        raise ValueError("Invalid risk preference or investment horizon")
    if any(debt.debt_type not in ("education", "home", "personal", "vehicle") for debt in profile.debts):
        raise ValueError("Invalid debt type")
    if profile.dataset_split not in (None, "train", "test"):
        raise ValueError("Invalid dataset split")


def generate_population(*, seed: int = DEFAULT_SEED) -> list[SyntheticProfile]:
    """Return exactly 12,000 independently sampled, non-identifying profiles."""
    rng = random.Random(seed)
    profiles = [_sample(spec, rng, seed) for spec in PERSONAS for _ in range(spec.count)]
    rng.shuffle(profiles)
    numbered = [replace(profile, synthetic_id=index)
                for index, profile in enumerate(profiles, start=1)]
    for profile in numbered:
        validate_profile(profile)
    return numbered


def export_population(path: Path, *, seed: int = DEFAULT_SEED) -> dict:
    """Write JSONL plus a validation summary; amounts are decimal strings."""
    profiles = generate_population(seed=seed)
    payload = "".join(json.dumps(asdict(profile), default=str, sort_keys=True,
                                 separators=(",", ":")) + "\n" for profile in profiles).encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    groups = {spec.name: [row for row in profiles if row.persona == spec.name] for spec in PERSONAS}
    report = {
        "dataset_version": POPULATION_VERSION,
        "seed": seed,
        "source": "illustrative synthetic experiment assumptions; not demographic estimates",
        "currency": "INR",
        "total_users": len(profiles),
        "sha256": sha256(payload).hexdigest(),
        "personas": {},
        "income_variation_note": "Standard deviation is across synthetic users, not month-to-month volatility.",
        "income_volatility_note": "Profile volatility is an assumed relative monthly standard deviation; no monthly incomes are generated yet.",
        "dataset_split_note": "All profiles are unassigned; user-level train/test splitting is Issue 6.",
    }
    for name, group in groups.items():
        incomes = [float(row.base_monthly_income) for row in group]
        report["personas"][name] = {
            "count": len(group),
            "mean_base_monthly_income": round(fmean(incomes), 2),
            "income_stddev_across_users": round(pstdev(incomes), 2),
            "mean_monthly_expenses": round(fmean(float(row.monthly_expenses) for row in group), 2),
            "debt_prevalence": round(fmean(row.existing_debt > 0 for row in group), 4),
            "mean_monthly_debt_payment": round(fmean(float(row.monthly_debt_payments) for row in group), 2),
            "mean_assumed_income_volatility": round(fmean(float(row.income_volatility) for row in group), 4),
        }
    path.with_suffix(".summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a research-only synthetic financial population.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(export_population(args.output, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
