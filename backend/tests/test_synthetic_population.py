"""The research population has exact persona counts and repeatable output."""

from collections import Counter
from hashlib import sha256
import json

from app.rl.population import export_population, generate_population


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
    assert export_population(path, seed=37) == report
    assert path.read_bytes() == first_bytes
