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


POPULATION_VERSION = "synthetic-population-v1"
DEFAULT_SEED = 20260930
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "population-v1.jsonl"
CENT = Decimal("0.01")

Persona = Literal["gig_worker", "salaried_with_loan", "student_fresh_graduate", "near_retiree"]


@dataclass(frozen=True)
class PersonaSpec:
    name: Persona
    count: int
    ages: tuple[int, int]
    income_range: tuple[int, int]
    expense_fraction: tuple[float, float]
    debt_probability: float
    horizon_range: tuple[int, int]


# Illustrative experiment assumptions, not population statistics or advice.
PERSONAS = (
    PersonaSpec("gig_worker", 3600, (20, 55), (12000, 80000), (0.50, 0.92), 0.30, (1, 25)),
    PersonaSpec("salaried_with_loan", 4200, (23, 60), (25000, 130000), (0.50, 0.85), 1.00, (1, 30)),
    PersonaSpec("student_fresh_graduate", 2400, (18, 28), (5000, 40000), (0.42, 0.90), 0.20, (1, 30)),
    PersonaSpec("near_retiree", 1800, (55, 72), (18000, 100000), (0.45, 0.83), 0.20, (0, 12)),
)


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


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def _sample(spec: PersonaSpec, rng: random.Random, seed: int) -> SyntheticProfile:
    income = _money(rng.uniform(*spec.income_range))
    expenses = _money(float(income) * rng.uniform(*spec.expense_fraction))
    has_debt = rng.random() < spec.debt_probability
    debt_payment = (_money(min(float(expenses) * 0.45, float(income) * rng.uniform(0.04, 0.18)))
                    if has_debt else Decimal("0.00"))
    debt = _money(float(income) * rng.uniform(0.2, 2.4)) if has_debt else Decimal("0.00")
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
    )


def generate_population(*, seed: int = DEFAULT_SEED) -> list[SyntheticProfile]:
    """Return exactly 12,000 independently sampled, non-identifying profiles."""
    rng = random.Random(seed)
    profiles = [_sample(spec, rng, seed) for spec in PERSONAS for _ in range(spec.count)]
    rng.shuffle(profiles)
    return [replace(profile, synthetic_id=index)
            for index, profile in enumerate(profiles, start=1)]


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
