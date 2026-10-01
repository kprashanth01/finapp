"""Apply the committed monthly selector to financial months entered by an account owner."""

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from statistics import fmean, pstdev
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.advisory.dynamic import DynamicPlanningState
from app.advisory.planning_types import PlanningAgentResult
from app.advisory.recommendations import RecommendationEngine, priority_actions
from app.advisory.registry import AgentRegistry
from app.advisory.rules import RULE_VERSION
from app.advisory.types import AgentSelection, OrchestratorDecision
from app.models import FinancialMonth
from app.rl.baselines import RuleBaseline
from app.rl.dynamic_model_management import get_model_metadata, load_model
from app.rl.dynamic_reward import audit_dynamic_reward
from app.rl.dynamic_state import DYNAMIC_OBSERVATION_VERSION, encode_dynamic_observation
from app.rl.selection import ACTION_VERSION, DEFAULT_CATALOG, assess_plan_readiness


Money = Decimal


class FinancialMonthWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    period: date
    monthly_income: Money = Field(ge=0, max_digits=12, decimal_places=2)
    monthly_expenses: Money = Field(ge=0, max_digits=12, decimal_places=2)
    fixed_expenses: Money = Field(ge=0, max_digits=12, decimal_places=2)
    scheduled_emi: Money = Field(ge=0, max_digits=12, decimal_places=2)
    paid_emi: Money = Field(ge=0, max_digits=12, decimal_places=2)
    savings: Money = Field(ge=0, max_digits=12, decimal_places=2)
    emergency_fund: Money = Field(ge=0, max_digits=12, decimal_places=2)
    outstanding_debt: Money = Field(ge=0, max_digits=12, decimal_places=2)
    unfunded_expenses: Money = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=2)
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    investment_horizon_years: int = Field(ge=0, le=80)

    @model_validator(mode="after")
    def consistent(self):
        if self.period.day != 1:
            raise ValueError("Choose the first day of a month.")
        if self.period > date.today().replace(day=1):
            raise ValueError("Future months cannot be recorded as financial history.")
        if self.fixed_expenses + self.scheduled_emi > self.monthly_expenses:
            raise ValueError("Fixed expenses plus debt payment cannot exceed total expenses.")
        if self.paid_emi > self.scheduled_emi:
            raise ValueError("Paid debt amount cannot exceed the scheduled payment.")
        if self.emergency_fund > self.savings:
            raise ValueError("Emergency reserve must be included in total savings.")
        return self


class FinancialMonthRead(FinancialMonthWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


def _previous_month(period: date) -> date:
    return date(period.year - 1, 12, 1) if period.month == 1 else date(period.year, period.month - 1, 1)


def _state(history: list[FinancialMonth], selected: FinancialMonth):
    prior = [row for row in history if row.period <= selected.period]
    previous = prior[-2] if len(prior) > 1 else None
    adjacent = previous is not None and previous.period == _previous_month(selected.period)
    baseline = next((row.monthly_income for row in prior if row.monthly_income > 0), selected.monthly_income)
    incomes = [float(row.monthly_income) for row in prior[-12:]]
    average = fmean(incomes)
    volatility = min(1.0, pstdev(incomes) / average) if len(incomes) > 1 and average > 0 else 0.0
    if not isfinite(volatility):
        raise ValueError("Monthly income variability is invalid.")
    change = ((selected.monthly_income - previous.monthly_income) / previous.monthly_income
              if adjacent and previous.monthly_income > 0 else None)
    income, expenses = selected.monthly_income, selected.monthly_expenses
    cash_flow = income - expenses
    expense_ratio = expenses / income if income > 0 else None
    debt_ratio = selected.scheduled_emi / income if income > 0 else None
    reserve_months = selected.emergency_fund / expenses if expenses > 0 else None
    missed = selected.paid_emi < selected.scheduled_emi
    observed_low = baseline > 0 and income <= baseline * Decimal("0.60")
    payload = {
        "month": FinancialMonthRead.model_validate(selected).model_dump(mode="json"),
        "earlier_income": [str(row.monthly_income) for row in prior[:-1]],
        "previous_period": previous.period.isoformat() if previous else None,
        "observation_version": DYNAMIC_OBSERVATION_VERSION,
    }
    fingerprint = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    planning = DynamicPlanningState(
        monthly_income=income, monthly_expenses=expenses, monthly_savings_contribution=None,
        monthly_debt_payments=selected.scheduled_emi, existing_debt=selected.outstanding_debt,
        emergency_fund=selected.emergency_fund, savings_rate_percent=None,
        debt_to_income_percent=debt_ratio * 100 if debt_ratio is not None else None,
        expense_to_income_percent=expense_ratio * 100 if expense_ratio is not None else None,
        emergency_fund_months=reserve_months, input_fingerprint=fingerprint,
        savings=selected.savings, risk_tolerance=selected.risk_tolerance,
        investment_horizon_years=selected.investment_horizon_years, financial_goal=None,
        goals=(), as_of_date=selected.period,
        fixed_expenses=selected.fixed_expenses,
        variable_expenses=expenses - selected.fixed_expenses - selected.scheduled_emi,
        current_surplus=max(Decimal(0), cash_flow), net_cash_flow=cash_flow,
        unfunded_expenses=selected.unfunded_expenses,
        income_volatility=Decimal(str(volatility)), recent_income_change_ratio=change,
        observed_low_income=observed_low, missed_payment=missed, highest_debt_apr=None,
    )
    # The encoder consumes observed financial fields only. Identity and synthetic
    # training metadata never enter the network input.
    observation = encode_dynamic_observation(SimpleNamespace(
        monthly_income=income, monthly_expenses=expenses,
        fixed_expenses=selected.fixed_expenses, scheduled_emi=selected.scheduled_emi,
        savings=selected.savings, emergency_fund=selected.emergency_fund,
        outstanding_debt=selected.outstanding_debt, income_volatility=Decimal(str(volatility)),
        income_change_ratio=change, net_cash_flow=cash_flow,
        unfunded_expenses=selected.unfunded_expenses, missed_payment=missed,
        observed_low_income=observed_low,
        investment_horizon_years=selected.investment_horizon_years,
        risk_tolerance=selected.risk_tolerance,
    ))
    context = {
        "period": selected.period.isoformat(), "previous_recorded_period": previous.period.isoformat() if previous else None,
        "previous_month_income": str(previous.monthly_income) if previous else None,
        "recent_income_change_ratio": str(change) if change is not None else None,
        "recent_income_change_percent": str((change * 100).quantize(Decimal("0.01"))) if change is not None else None,
        "income_volatility": str(volatility), "usual_income_reference": str(baseline),
        "net_cash_flow": str(cash_flow), "observed_low_income": observed_low,
        "history_months_used": len(prior), "consecutive_prior_month": adjacent,
    }
    return planning, observation, context


def _method_result(state: DynamicPlanningState, action: int, method: Literal["trained_rl", "rule_based"]):
    selected = DEFAULT_CATALOG.agents_for(action)
    registry = AgentRegistry.default()
    results = [registry.get(agent).analyze(state) for agent in selected]
    audit = audit_dynamic_reward(state, selected)
    readiness = assess_plan_readiness(state, selected)
    findings = priority_actions(results)
    plan = None
    if readiness["can_build_full_plan"]:
        decision = OrchestratorDecision(method="rl" if method == "trained_rl" else "rule_based",
            rule_version=RULE_VERSION, selections=[AgentSelection(
                agent_id=agent, selected=agent in selected,
                reason=f"Selected by the {method.replace('_', ' ')} method." if agent in selected else
                       f"Not selected by the {method.replace('_', ' ')} method.",
            ) for agent in registry.agent_ids])
        plan = RecommendationEngine().build(state, decision,
                                            [PlanningAgentResult.model_validate(result) for result in results])
    return {
        "action": action, "selected_agents": list(selected),
        "priority_actions": [item.model_dump(mode="json") for item in findings],
        "agent_results": [item.model_dump(mode="json") for item in results],
        "recommendation": {"status": "complete" if plan else "partial",
                           "plan_readiness": readiness,
                           "summary": plan.summary.model_dump(mode="json") if plan else None,
                           "coordinated_plan": plan.model_dump(mode="json") if plan else None},
        "reward": audit.total, "reward_components": audit.components,
        "reward_audit": audit.to_dict(),
    }


def interpret_investment_review(result: dict, cash_flow: Decimal | str) -> dict | None:
    """Turn the existing investment check into bounded next steps, without setting an allocation."""
    facts = result.get("facts") or {}
    status = facts.get("status")
    if status not in ("deferred", "insufficient_information", "ready_to_consider"):
        return None
    factors = set(facts.get("factor_codes") or [])
    steps = []
    if "no_current_surplus" in factors or Decimal(cash_flow) <= 0:
        steps.append("Review planned spending and required loan payments before making a new allocation.")
    if "missed_payment" in factors:
        steps.append("Review the scheduled loan payment that was not fully met.")
    if "reserve_gap" in factors:
        steps.append("Build an accessible emergency reserve before deciding on a new investment.")
    if "high_debt" in factors:
        steps.append("Confirm your loan interest rate and required payment before choosing between extra repayment and investing.")
    if "income_instability" in factors:
        steps.append("Check whether the income drop will continue and adjust planned spending.")
    if "zero_horizon" in factors or "missing_horizon" in factors:
        steps.append("Set a time horizon for money you may invest.")
    if "unknown_debt" in factors:
        steps.append("Record current income and debt payments to assess the debt burden.")
    if "unknown_reserve" in factors:
        steps.append("Record scheduled expenses to assess the emergency reserve.")
    if status == "deferred":
        headline = ("This month's investment readiness check does not support a new investment amount. "
                    "Money left after planned spending is not an investment recommendation.")
    elif status == "insufficient_information":
        headline = ("This month's investment readiness check needs more information before suggesting an investment amount. "
                    "Money left after planned spending is not an investment recommendation.")
    else:
        headline = ("This month's investment readiness checks passed, but they do not choose an investment amount or product. "
                    "Money left after planned spending is not an investment recommendation.")
    if not steps:
        steps.append("Check your emergency needs, debt interest rate, and goals before choosing an amount.")
    return {"status": status, "headline": headline, "steps": steps}


def evaluate_account_month(history: list[FinancialMonth], selected: FinancialMonth,
                           focus: Literal["all", "budget", "debt", "emergency", "goal", "risk", "investment"] = "all") -> dict:
    """Inference only; never train the policy or update an account balance."""
    ordered = sorted(history, key=lambda row: row.period)
    if not any(row.id == selected.id for row in ordered):
        raise ValueError("Selected month is not part of this account history.")
    state, observation, context = _state(ordered, selected)
    metadata = get_model_metadata()
    if metadata["action_version"] != ACTION_VERSION or metadata["observation_version"] != DYNAMIC_OBSERVATION_VERSION:
        raise ValueError("The committed DQN is incompatible with the monthly input schema.")
    model = load_model()
    predicted, _ = model.predict(observation, deterministic=True)
    action = int(predicted)
    if not 0 <= action < DEFAULT_CATALOG.action_count:
        raise ValueError("The committed DQN returned an unknown action.")
    rule_action = RuleBaseline().choose_action(state, DEFAULT_CATALOG)
    trained = _method_result(state, action, "trained_rl")
    focused = None
    if focus != "all":
        result = AgentRegistry.default().get(focus).analyze(state)
        focused = {"agent_id": focus, "selected_by_dqn": focus in trained["selected_agents"],
                   "result": result.model_dump(mode="json")}
        if focus == "investment":
            focused["interpretation"] = interpret_investment_review(focused["result"], context["net_cash_flow"])
    return {
        "source": "account_entered_months", "model_version": metadata["model_version"],
        "model_artifact_sha256": metadata["artifact_sha256"],
        "observation_version": DYNAMIC_OBSERVATION_VERSION, "state_fingerprint": state.fingerprint(),
        "month": FinancialMonthRead.model_validate(selected).model_dump(mode="json"),
        "context": context,
        "methods": {
            "trained_rl": trained,
            "rule_based": _method_result(state, rule_action, "rule_based"),
        },
        "focused_review": focused,
        "limitations": [
            "The DQN selects specialists; their financial findings come from project rules.",
            "The model was trained on generated people and months, not on this account or its outcomes.",
            "Income variability uses up to 12 entered months. A recent change needs an adjacent earlier month.",
            "Savings and debt balances are entered snapshots; the app does not infer transactions between months.",
            "Current saved goals and debt interest rates are not included in this monthly comparison.",
            "The selection proxy does not measure advice quality or financial improvement.",
        ],
    }
