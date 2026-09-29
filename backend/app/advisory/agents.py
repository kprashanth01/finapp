"""Independent agents; each consumes a state and returns structured evidence."""

from decimal import Decimal
from typing import Protocol

from app.advisory.rules import EMERGENCY_TARGET_MONTHS, HIGH_DTI_PERCENT, HIGH_EXPENSE_PERCENT
from app.advisory.state import FinancialState
from app.advisory.types import AgentResult, Evidence, Finding
from app.advisory.planning_types import BudgetFacts, DebtFacts, EmergencyFacts, PlanningAgentResult


class Agent(Protocol):
    agent_id: str

    def analyze(self, state: FinancialState) -> AgentResult: ...


class BudgetAgent:
    agent_id = "budget"

    def analyze(self, state: FinancialState) -> AgentResult:
        expense_ratio = state.expense_to_income_percent
        savings_rate = state.savings_rate_percent
        limitations = ["Ratios use gross income; they do not show spendable cash."]
        if expense_ratio is None:
            limitations.append("Expense ratio needs positive gross income.")
        if savings_rate is None:
            limitations.append("Savings rate needs a monthly contribution and positive gross income.")
        priority = (
            state.monthly_income > 0
            and state.monthly_expenses / state.monthly_income * 100 >= HIGH_EXPENSE_PERCENT
        )
        finding = Finding(
            code="expense_ratio_high" if priority else "budget_ratios",
            title="Review monthly expenses" if priority else "Budget ratios",
            reason=(
                f"Expenses are at least {HIGH_EXPENSE_PERCENT}% of gross income under this illustrative rule."
                if priority else "These ratios describe the saved monthly amounts; no budget priority was triggered."
            ),
            priority=priority,
            evidence=[
                Evidence(label="Expense-to-income ratio", value=expense_ratio, unit="%"),
                Evidence(label="Savings rate", value=savings_rate, unit="%"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            facts=BudgetFacts(capacity=state.monthly_savings_contribution),
            agent_id=self.agent_id,
            status="limited" if expense_ratio is None or savings_rate is None else "ok",
            findings=[finding],
            limitations=limitations,
        )


class DebtAgent:
    agent_id = "debt"

    def analyze(self, state: FinancialState) -> AgentResult:
        dti = state.debt_to_income_percent
        limitations = []
        if dti is None:
            limitations.append("DTI needs a monthly debt payment and positive gross income.")
        priority = (
            state.monthly_debt_payments is not None
            and state.monthly_income > 0
            and state.monthly_debt_payments / state.monthly_income * 100 >= HIGH_DTI_PERCENT
        )
        finding = Finding(
            code="dti_high" if priority else "debt_ratio",
            title="Review debt payments" if priority else "Debt payment ratio",
            reason=(
                f"Debt payments are at least {HIGH_DTI_PERCENT}% of gross income under this illustrative rule."
                if priority else "No debt-payment priority was triggered by the available inputs."
            ),
            priority=priority,
            evidence=[
                Evidence(label="Debt-to-income ratio", value=dti, unit="%"),
                Evidence(label="Outstanding debt", value=state.existing_debt, unit="currency"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            facts=DebtFacts(review_required=priority or dti is None, reason_code='high_debt' if priority else 'unknown_debt' if dti is None else None),
            agent_id=self.agent_id,
            status="limited" if dti is None else "ok",
            findings=[finding],
            limitations=limitations,
        )


class EmergencyAgent:
    agent_id = "emergency"

    def analyze(self, state: FinancialState) -> AgentResult:
        coverage = state.emergency_fund_months
        gap = (
            max(Decimal("0"), EMERGENCY_TARGET_MONTHS * state.monthly_expenses - state.emergency_fund)
            if state.monthly_expenses > 0 else None
        )
        limitations = [f"The {EMERGENCY_TARGET_MONTHS}-month target is an illustrative project rule."]
        if coverage is None:
            limitations.append("Coverage needs positive monthly expenses.")
        priority = (
            state.monthly_expenses > 0
            and state.emergency_fund / state.monthly_expenses < EMERGENCY_TARGET_MONTHS
        )
        finding = Finding(
            code="emergency_gap" if priority else "emergency_coverage",
            title="Review emergency reserve" if priority else "Emergency reserve coverage",
            reason=(
                f"Coverage is below the illustrative {EMERGENCY_TARGET_MONTHS}-month target."
                if priority else "No emergency-reserve priority was triggered by the available inputs."
            ),
            priority=priority,
            evidence=[
                Evidence(label="Emergency fund coverage", value=coverage, unit="months"),
                Evidence(label="Gap to illustrative target", value=gap, unit="currency"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            facts=EmergencyFacts(gap=gap, coverage=coverage),
            agent_id=self.agent_id,
            status="limited" if coverage is None else "ok",
            findings=[finding],
            limitations=limitations,
        )
