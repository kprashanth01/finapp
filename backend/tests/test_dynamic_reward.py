"""A monthly selection score uses observed state, with no claimed financial outcome."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
import json
import subprocess
import sys

import pytest

from app.advisory.dynamic import build_dynamic_planning_state
from app.advisory.state import GoalSnapshot
from app.rl.dynamic_reward import DYNAMIC_REWARD_VERSION, audit_dynamic_reward
from app.rl.dynamic_state import build_dynamic_financial_state
from app.rl.population import SyntheticDebt, generate_population
from app.rl.reward import REWARD_VERSION, audit_reward
from app.rl.trajectories import ShockConfig, generate_trajectory


def _state(*, shock=False, volatility=None):
    profile = replace(
        generate_population(seed=91)[0],
        base_monthly_income=D("5000"), income_volatility=D("0"),
        fixed_monthly_expenses=D("1800"), variable_monthly_expenses=D("800"),
        monthly_debt_payments=D("400"), monthly_expenses=D("3000"),
        existing_debt=D("10000"),
        debts=(SyntheticDebt("personal", D("10000"), D("0.08"), D("400"), 36),),
        savings=D("15000"), emergency_fund=D("9000"),
        monthly_savings_contribution=D("500"),
        risk_tolerance="aggressive", investment_horizon_years=10,
    )
    config = ShockConfig(probability=1, event_types=("temporary_income_loss",)) if shock else None
    month = generate_trajectory(profile, months=1, seed=4, expense_volatility=0,
                                shock_config=config)[0]
    financial = build_dynamic_financial_state(profile, month,
                                              income_volatility_override=volatility)
    return build_dynamic_planning_state(profile, financial, as_of_date=date(2026, 10, 1))


def test_income_loss_changes_score_and_exposes_every_component():
    selection = ("budget", "investment")
    stable = audit_dynamic_reward(_state(), selection)
    stressed = audit_dynamic_reward(_state(shock=True), selection)

    assert stable.version == stressed.version == DYNAMIC_REWARD_VERSION
    assert "investment" in stable.relevant_agents
    assert stable.components == {
        "relevant_coverage": 2.0, "critical_coverage": 0.0,
        "missed_critical_penalty": 0.0, "unneeded_agent_penalty": 0.0,
        "agent_call_penalty": -0.3,
    }
    assert "investment" in stressed.unneeded_agents
    assert {"budget", "emergency", "debt", "risk"}.issubset(stressed.critical_agents)
    assert stressed.total < stable.total
    assert stressed.total == pytest.approx(sum(stressed.components.values()))
    assert set(stressed.components) == {
        "relevant_coverage", "critical_coverage", "missed_critical_penalty",
        "unneeded_agent_penalty", "agent_call_penalty",
    }
    assert stressed.components["missed_critical_penalty"] < stable.components["missed_critical_penalty"]
    assert {"net_cash_flow", "observed_low_income", "emergency_fund_months",
            "debt_to_income_percent", "missed_payment", "income_volatility",
            "unfinished_goal_count"}.issubset({check.metric for check in stressed.checks})


def test_volatility_and_missed_payment_change_critical_checks():
    stable = _state()
    volatile = _state(volatility=0.4)
    missed = stable.model_copy(update={"missed_payment": True})

    stable_audit = audit_dynamic_reward(stable, ("budget", "emergency"))
    volatile_audit = audit_dynamic_reward(volatile, ("budget", "emergency"))
    missed_audit = audit_dynamic_reward(missed, ("budget", "emergency"))

    assert "emergency" not in stable_audit.critical_agents
    assert {"emergency", "risk"}.issubset(volatile_audit.critical_agents)
    assert "debt" in missed_audit.critical_agents
    reserve = next(check for check in volatile_audit.checks
                   if check.metric == "emergency_fund_months")
    assert reserve.threshold == "6"
    assert reserve.value == "3.0000"


def test_unfinished_goal_is_visible_and_scored_without_claiming_funding():
    state = _state()
    goal = GoalSnapshot(id=7, name="Course", target_amount=D("12000"),
                        saved_amount=D("1000"), target_date=date(2026, 10, 1) + timedelta(days=180),
                        priority="high")
    state = state.model_copy(update={"goals": (goal,)})
    omitted = audit_dynamic_reward(state, ("budget",))
    included = audit_dynamic_reward(state, ("budget", "goal"))
    assert "goal" in omitted.missed_critical_agents
    assert "goal" in included.critical_agents
    assert included.total > omitted.total
    check = next(check for check in included.checks if check.metric == "unfinished_goal_count")
    assert check.value == "1" and check.selected and check.critical


def test_dynamic_score_rejects_invalid_selection_and_preserves_legacy_version():
    state = _state()
    with pytest.raises(ValueError, match="registered"):
        audit_dynamic_reward(state, ("unknown",))
    with pytest.raises(ValueError, match="distinct"):
        audit_dynamic_reward(state, ("budget", "budget"))
    assert REWARD_VERSION == "selection-proxy-v1"
    assert audit_reward(state, ("budget",)).version == REWARD_VERSION


def test_seeded_cli_reports_actual_monthly_components_reproducibly():
    command = [sys.executable, "-m", "app.rl.dynamic_reward", "--synthetic-id", "1",
               "--months", "2", "--seed", "4", "--selected", "budget", "emergency"]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    assert report["reward_version"] == DYNAMIC_REWARD_VERSION
    assert len(report["months"]) == 2
    assert all(month["total_reward"] == pytest.approx(sum(month["components"].values()))
               for month in report["months"])
    assert report["months"][0]["monthly_income"] != report["months"][1]["monthly_income"]
    with_goal = subprocess.run(command + ["--goal-target", "12000", "--goal-months", "6"],
                               capture_output=True, text=True, check=True)
    assert all("goal" in month["critical_agents"] for month in json.loads(with_goal.stdout)["months"])
