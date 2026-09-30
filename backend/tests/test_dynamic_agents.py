"""The existing six agents react to monthly research states through one interface."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
import json
import subprocess
import sys

from app.advisory.dynamic import build_dynamic_planning_state
from app.advisory.registry import AgentRegistry
from app.advisory.state import GoalSnapshot
from app.rl.dynamic_state import build_dynamic_financial_state
from app.rl.population import SyntheticDebt, generate_population
from app.rl.trajectories import ShockConfig, generate_trajectory


AS_OF = date(2026, 10, 1)


def _profile():
    return replace(
        generate_population(seed=91)[0],
        base_monthly_income=D("5000.00"), income_volatility=D("0.00"),
        fixed_monthly_expenses=D("1800.00"), variable_monthly_expenses=D("800.00"),
        monthly_debt_payments=D("400.00"), monthly_expenses=D("3000.00"),
        existing_debt=D("10000.00"),
        debts=(SyntheticDebt("personal", D("10000.00"), D("0.08"), D("400.00"), 36),),
        savings=D("15000.00"), emergency_fund=D("9000.00"),
        monthly_savings_contribution=D("500.00"),
        risk_tolerance="aggressive", investment_horizon_years=10,
    )


def _analyze(profile, *, shock=False, volatility=None, goals=()):
    config = ShockConfig(probability=1, event_types=("temporary_income_loss",),
                         income_volatility_override=volatility) if shock else None
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0,
                                shock_config=config)[0]
    dynamic = build_dynamic_financial_state(
        profile, month, income_volatility_override=volatility,
    )
    state = build_dynamic_planning_state(profile, dynamic, as_of_date=AS_OF, goals=goals)
    registry = AgentRegistry.default()
    return state, {key: registry.get(key).analyze(state) for key in registry.agent_ids}


def test_adapter_and_registry_keep_six_shared_agents_with_monthly_inputs():
    state, results = _analyze(_profile())
    assert set(results) == {"budget", "debt", "emergency", "goal", "risk", "investment"}
    assert all(result.agent_id == key for key, result in results.items())
    assert state.monthly_income == D("5000.00")
    assert state.fixed_expenses == D("1800.00")
    assert state.variable_expenses == D("800.00")
    assert state.current_surplus == D("2000.00")
    assert state.monthly_savings_contribution is None  # No contribution decision was simulated.
    assert state.highest_debt_apr == D("0.08")
    assert results["budget"].facts.capacity == D("2000.00")


def test_income_loss_changes_budget_debt_investment_and_risk_findings():
    profile = _profile()
    stable, normal = _analyze(profile)
    loss, stressed = _analyze(profile, shock=True)
    assert stable.monthly_income > loss.monthly_income == 0
    assert normal["budget"].findings[0].priority is False
    assert stressed["budget"].findings[0].priority is True
    assert normal["debt"].facts.review_required is False
    assert stressed["debt"].facts.review_required is True
    assert stressed["debt"].facts.reason_code == "cash_shortfall"
    assert normal["investment"].facts.status == "ready_to_consider"
    assert stressed["investment"].facts.status == "deferred"
    assert "no_current_surplus" in stressed["investment"].facts.factor_codes
    assert normal["risk"].facts.category == "aggressive"
    assert stressed["risk"].facts.category == "conservative"
    assert "income_instability" in stressed["risk"].facts.factor_codes
    assert all(result.status in {"ok", "limited"} for result in stressed.values())


def test_volatility_changes_reserve_target_and_investment_readiness():
    profile = _profile()
    _, stable = _analyze(profile)
    _, volatile = _analyze(profile, volatility=0.40)
    assert stable["emergency"].facts.gap == D("0.00")
    assert volatile["emergency"].facts.gap == D("9000.00")
    assert volatile["emergency"].findings[0].priority is True
    assert volatile["investment"].facts.status == "deferred"
    assert "reserve_gap" in volatile["investment"].facts.factor_codes


def test_goal_checks_current_surplus_and_competing_priorities():
    goal = GoalSnapshot(id=7, name="Course", target_amount=D("12000.00"),
                        saved_amount=D("0.00"), target_date=AS_OF + timedelta(days=180),
                        priority="high")
    profile = _profile()
    _, stable = _analyze(profile, goals=(goal,))
    _, stressed = _analyze(profile, shock=True, goals=(goal,))
    assert stable["goal"].facts.requirements[0].required_monthly == D("2000.00")
    assert stable["goal"].findings[0].priority is False
    assert stressed["goal"].findings[0].priority is True
    assert "surplus" in stressed["goal"].findings[0].reason.lower()


def test_high_apr_and_missed_payment_are_explained_as_debt_factors():
    profile = _profile()
    costly = replace(profile, debts=(replace(profile.debts[0], annual_interest_rate=D("0.15")),))
    _, results = _analyze(costly)
    assert results["debt"].facts.review_required is True
    assert results["debt"].facts.reason_code == "high_interest"
    assert any(e.label == "Highest debt APR" and e.value == D("15.00")
               for e in results["debt"].findings[0].evidence)
    depleted = replace(profile, savings=D("100.00"), emergency_fund=D("100.00"))
    state, missed = _analyze(depleted, shock=True)
    assert state.missed_payment is True
    assert missed["debt"].facts.reason_code == "missed_payment"
    assert "missed_payment" in missed["investment"].facts.factor_codes


def test_adapter_rejects_a_different_profile():
    profile = _profile()
    month = generate_trajectory(profile, months=1, seed=4)[0]
    dynamic = build_dynamic_financial_state(profile, month)
    from pytest import raises
    with raises(ValueError, match="identity"):
        build_dynamic_planning_state(replace(profile, synthetic_id=profile.synthetic_id + 1),
                                     dynamic, as_of_date=AS_OF)


def test_preview_prints_months_and_all_six_agent_results():
    run = subprocess.run(
        [sys.executable, "-m", "app.advisory.dynamic", "--synthetic-id", "1",
         "--months", "2", "--goal-target", "12000", "--goal-months", "6"],
        capture_output=True, text=True, check=True,
    )
    output = json.loads(run.stdout)
    assert output["version"] == "dynamic-agent-context-v1"
    assert len(output["months"]) == 2
    assert set(output["months"][0]["agents"]) == {
        "budget", "debt", "emergency", "goal", "risk", "investment",
    }
    assert output["months"][0]["agents"]["goal"]["facts"]["requirements"][0]["goal"]["name"] == "Example goal"
    assert any(e["label"] == "Current surplus" for e in output["months"][0]["agents"]["goal"]["findings"][0]["evidence"])
    assert output["months"][0]["state"]["monthly_income"] != output["months"][1]["state"]["monthly_income"]
