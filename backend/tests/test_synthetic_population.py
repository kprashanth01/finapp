"""The research population has exact persona counts and repeatable output."""

from collections import Counter
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
import pytest

from app.rl.population import export_population, generate_population, validate_profile


def test_population_has_exact_personas_and_valid_financial_profiles():
    profiles = generate_population(seed=91)
    assert len(profiles) == 12_000
    assert Counter(profile.persona for profile in profiles) == {
        "gig_worker": 3_600,
        "salaried_with_loan": 4_200,
        "student_fresh_graduate": 2_400,
        "near_retiree": 1_800,
    }
    assert {profile.synthetic_id for profile in profiles} == set(range(1, 12_001))
    assert all(profile.base_monthly_income > 0 for profile in profiles)
    assert all(0 <= profile.monthly_debt_payments <= profile.monthly_expenses for profile in profiles)
    assert all(profile.savings >= profile.emergency_fund >= 0 for profile in profiles)
    assert all(profile.monthly_savings_contribution <=
               max(0, profile.base_monthly_income - profile.monthly_expenses) for profile in profiles)
    assert all(profile.existing_debt > 0 for profile in profiles
               if profile.persona == "salaried_with_loan")


def test_research_schema_has_consistent_expenses_debts_and_unassigned_split():
    profiles = generate_population(seed=91)
    assert all(profile.dataset_split is None for profile in profiles)
    assert all(0 <= profile.dependents <= 5 for profile in profiles)
    assert all(profile.fixed_monthly_expenses + profile.variable_monthly_expenses
               + profile.monthly_debt_payments == profile.monthly_expenses for profile in profiles)
    assert all(sum((debt.outstanding_principal for debt in profile.debts), start=0)
               == profile.existing_debt for profile in profiles)
    assert all(sum((debt.monthly_emi for debt in profile.debts), start=0)
               == profile.monthly_debt_payments for profile in profiles)
    assert all(0 <= profile.income_volatility <= 1 for profile in profiles)
    assert all(debt.annual_interest_rate >= 0 and debt.remaining_months > 0
               for profile in profiles for debt in profile.debts)
    assert all(validate_profile(profile) is None for profile in profiles)
    gig_volatility = [p.income_volatility for p in profiles if p.persona == "gig_worker"]
    salaried_volatility = [p.income_volatility for p in profiles if p.persona == "salaried_with_loan"]
    assert min(gig_volatility) > max(salaried_volatility)
    assert all(profile.debts for profile in profiles if profile.persona == "salaried_with_loan")


def test_schema_validation_rejects_inconsistent_aggregates_and_split():
    profile = generate_population(seed=3)[0]
    with pytest.raises(ValueError, match="Expense components"):
        validate_profile(replace(profile, monthly_expenses=profile.monthly_expenses + Decimal("1.00")))
    with pytest.raises(ValueError, match="Debt principal"):
        validate_profile(replace(profile, existing_debt=profile.existing_debt + Decimal("1.00")))
    with pytest.raises(ValueError, match="dataset split"):
        validate_profile(replace(profile, dataset_split="validation"))


def test_seed_reproduces_population_and_other_seed_changes_it():
    first = generate_population(seed=44)
    repeated = generate_population(seed=44)
    different = generate_population(seed=45)
    assert first == repeated
    assert first != different
    assert [profile.synthetic_id for profile in first] == list(range(1, 12_001))


def test_export_writes_all_profiles_and_a_matching_validation_summary(tmp_path):
    path = tmp_path / "population.jsonl"
    report = export_population(path, seed=37)
    first_bytes = path.read_bytes()
    lines = first_bytes.decode("utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert len(rows) == 12_000
    assert report["total_users"] == 12_000
    assert report["seed"] == 37
    assert report["sha256"] == sha256(first_bytes).hexdigest()
    assert json.loads(path.with_suffix(".summary.json").read_text(encoding="utf-8")) == report
    assert report["personas"]["gig_worker"]["count"] == 3_600
    assert report["personas"]["salaried_with_loan"]["debt_prevalence"] == 1.0
    assert report["personas"]["gig_worker"]["income_stddev_across_users"] > 0
    assert rows[0]["synthetic_id"] == 1
    assert "email" not in rows[0] and "name" not in rows[0]
    assert all(row["generation_seed"] == 37 for row in rows)
    assert report["dataset_version"] == "synthetic-population-v2"
    assert rows[0]["dataset_split"] is None
    assert "debts" in rows[0] and "income_volatility" in rows[0]
    assert export_population(path, seed=37) == report
    assert path.read_bytes() == first_bytes
