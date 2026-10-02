"""Independent agents; each consumes a state and returns structured evidence."""

from decimal import Decimal
from typing import Protocol

from app.advisory.rules import EMERGENCY_TARGET_MONTHS, HIGH_DTI_PERCENT, HIGH_EXPENSE_PERCENT
from app.advisory.state import FinancialState
from app.advisory.types import AgentResult, Evidence, Finding
from app.advisory.planning_types import BudgetFacts, DebtFacts, EmergencyFacts, PlanningAgentResult
from app.advisory.dynamic import DynamicPlanningState, HIGH_DEBT_APR, reserve_target_months


class Agent(Protocol):
    agent_id: str

    def analyze(self, state: FinancialState) -> AgentResult: ...


class BudgetAgent:
    agent_id = "budget"

    def analyze(self, state: FinancialState) -> AgentResult:
        if isinstance(state, DynamicPlanningState):
            return self._analyze_dynamic(state)
        picture = getattr(state, "picture", None)
        cash_shortfall = (max(Decimal(0), -picture.spending.gross_cash_flow.value)
                          if picture is not None else Decimal(0))
        expense_ratio = state.expense_to_income_percent
        savings_rate = state.savings_rate_percent
        limitations = ["Ratios use gross income; they do not show spendable cash."]
        if expense_ratio is None:
            limitations.append("Expense ratio needs positive gross income.")
        if savings_rate is None:
            limitations.append("Savings rate needs a monthly contribution and positive gross income.")
        ratio_high = (
            state.monthly_income > 0
            and state.monthly_expenses / state.monthly_income * 100 >= HIGH_EXPENSE_PERCENT
        )
        priority = ratio_high and cash_shortfall == 0
        finding = Finding(
            code="expense_ratio_high" if ratio_high else "budget_ratios",
            title="Review monthly expenses" if ratio_high else "Budget ratios",
            reason=(
                f"Expenses are at least {HIGH_EXPENSE_PERCENT}% of gross income under this illustrative rule."
                if ratio_high else "These ratios describe the saved monthly amounts; no budget priority was triggered."
            ),
            priority=priority,
            evidence=[
                Evidence(label="Expense-to-income ratio", value=expense_ratio, unit="%",
                         source="profile.monthly_expenses_divided_by_gross_income" if picture else None),
                Evidence(label="Savings rate", value=savings_rate, unit="%",
                         source=picture.spending.savings_rate_percent.source if picture else None),
            ],
            limitations=limitations,
            impact=("Gross income is needed to judge recorded expense pressure." if expense_ratio is None else
                    "Without a recorded savings contribution, the plan cannot allocate a monthly savings budget." if savings_rate is None else
                    "A high share of gross income going to expenses may leave less room for savings and unexpected costs." if ratio_high else
                    "This project check found no high expense ratio, but gross-income ratios do not show take-home cash."),
            suggested_action=("Enter positive gross monthly income and review expenses." if expense_ratio is None else
                              "Enter your planned monthly savings contribution before relying on an allocation." if savings_rate is None else
                              "Review your largest expenses against take-home pay and update your planned savings contribution." if ratio_high else
                              "Keep expenses and your planned savings contribution current; compare the plan with take-home pay."),
        )
        findings = [finding]
        if cash_shortfall > 0:
            findings.insert(0, Finding(
                code="gross_cash_shortfall", title="Review the current cash shortfall",
                reason="Entered monthly expenses exceed the current gross income estimate; pause new savings allocations until required costs are checked.",
                priority=True,
                evidence=[Evidence(label="Gross monthly cash flow", value=picture.spending.gross_cash_flow.value,
                                   unit="currency", source=picture.spending.gross_cash_flow.source),
                          Evidence(label="Monthly expenses", value=picture.spending.monthly_total.value,
                                   unit="currency", source=picture.spending.monthly_total.source)],
                limitations=["Gross income is before tax and does not show payment timing."],
                impact="Required monthly costs exceed the entered gross income estimate.",
                suggested_action="Review take-home income, required payments, and expenses before assigning new savings.",
            ))
        return PlanningAgentResult(
            facts=BudgetFacts(capacity=state.monthly_savings_contribution, cash_shortfall=cash_shortfall),
            agent_id=self.agent_id,
            status="limited" if expense_ratio is None or savings_rate is None else "ok",
            findings=findings,
            limitations=limitations,
        )

    def _analyze_dynamic(self, state: DynamicPlanningState) -> PlanningAgentResult:
        ratio = state.expense_to_income_percent
        recent_drop = (state.recent_income_change_ratio is not None
                       and state.recent_income_change_ratio <= Decimal("-0.30"))
        priority = (state.net_cash_flow < 0 or state.unfunded_expenses > 0 or recent_drop
                    or ratio is not None and ratio >= HIGH_EXPENSE_PERCENT)
        limitations = ["Current surplus is income minus scheduled expenses, not a tracked savings contribution."]
        if ratio is None:
            limitations.append("Expense ratio needs positive current income.")
        finding = Finding(
            code="monthly_budget_pressure" if priority else "monthly_budget_capacity",
            title="Review this month's budget" if priority else "Current monthly budget",
            reason=("Scheduled expenses exceed current income, spending is unfunded, or income fell sharply."
                    if priority else "Current income covers scheduled expenses under this illustrative check."),
            priority=priority,
            evidence=[
                Evidence(label="Current income", value=state.monthly_income, unit="currency"),
                Evidence(label="Fixed essentials", value=state.fixed_expenses, unit="currency"),
                Evidence(label="Variable expenses", value=state.variable_expenses, unit="currency"),
                Evidence(label="Scheduled cash flow", value=state.net_cash_flow, unit="currency"),
                Evidence(label="Recent income change", value=(state.recent_income_change_ratio * 100
                         if state.recent_income_change_ratio is not None else None), unit="%"),
                Evidence(label="Income volatility", value=state.income_volatility * 100, unit="%"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            agent_id=self.agent_id, status="limited" if ratio is None else "ok",
            findings=[finding], limitations=limitations,
            facts=BudgetFacts(capacity=state.current_surplus),
        )


class DebtAgent:
    agent_id = "debt"

    def analyze(self, state: FinancialState) -> AgentResult:
        if isinstance(state, DynamicPlanningState):
            return self._analyze_dynamic(state)
        picture = getattr(state, "picture", None)
        dti = picture.spending.debt_to_income_percent.value if picture else state.debt_to_income_percent
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
                Evidence(label="Debt-to-income ratio", value=dti, unit="%",
                         source=picture.spending.debt_to_income_percent.source if picture else None),
                Evidence(label="Outstanding debt", value=state.existing_debt, unit="currency"),
            ],
            limitations=limitations,
            impact=("Without income and a monthly payment, the debt burden cannot be assessed." if dti is None else
                    "Required debt payments take a substantial share of gross income under this project's rule and may constrain other goals." if priority else
                    "This project check found no high payment burden, though an outstanding balance still needs attention."),
            suggested_action=("Record the required monthly debt payment and positive gross income." if dti is None else
                              "Keep required payments current and review loan terms before assigning remaining savings." if priority else
                              "Keep required payments current and check loan terms before deciding on extra repayment."),
        )
        findings = [finding]
        if picture:
            for loan in picture.obligations:
                if loan.kind != "loan_payment" or loan.rate_change_date is None:
                    continue
                days = (loan.rate_change_date - picture.as_of_date).days
                if not 0 <= days <= 90:
                    continue
                findings.append(Finding(
                    code=f"loan_rate_change_{loan.id}", title=f"Review {loan.name} rate change",
                    reason=f"The saved rate for {loan.name} changes on {loan.rate_change_date.isoformat()}; confirm the lender's payment and terms.",
                    priority=False,
                    evidence=[Evidence(label="Current annual rate", value=loan.annual_interest_rate_percent,
                                       unit="%", source="saved_loan_detail.annual_interest_rate_percent"),
                              Evidence(label="New annual rate", value=loan.new_annual_interest_rate_percent,
                                       unit="%", source="saved_loan_detail.new_annual_interest_rate_percent"),
                              Evidence(label="Monthly payment", value=loan.amount, unit="currency",
                                       source="saved_loan_detail.monthly_payment")],
                    limitations=["The entered rate change does not recalculate the payment; the payment is already in aggregate expenses."],
                    impact="A changed rate may alter future payments or the cost of debt.",
                    suggested_action="Check the lender notice and update the payment amount if it changes.",
                ))
        return PlanningAgentResult(
            facts=DebtFacts(review_required=priority or dti is None, reason_code='high_debt' if priority else 'unknown_debt' if dti is None else None),
            agent_id=self.agent_id,
            status="limited" if dti is None else "ok",
            findings=findings,
            limitations=limitations,
        )

    def _analyze_dynamic(self, state: DynamicPlanningState) -> PlanningAgentResult:
        dti = state.debt_to_income_percent
        has_debt = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
        cash_shortfall = has_debt and state.net_cash_flow < 0
        high_payment = dti is not None and dti >= HIGH_DTI_PERCENT
        high_interest = state.highest_debt_apr is not None and state.highest_debt_apr >= HIGH_DEBT_APR
        reason_code = ("missed_payment" if state.missed_payment else
                       "cash_shortfall" if cash_shortfall else
                       "high_debt" if high_payment else
                       "high_interest" if has_debt and high_interest else None)
        priority = reason_code is not None
        limitations = ["APR is the highest contractual rate in the synthetic profile; current loan-level balances are unavailable."]
        if dti is None and has_debt:
            limitations.append("Payment-to-income ratio needs positive current income.")
        finding = Finding(
            code=reason_code or "monthly_debt_position",
            title="Review current debt obligations" if priority else "Current debt position",
            reason=(
                "A scheduled debt payment was missed." if state.missed_payment else
                "Current scheduled expenses exceed income while debt remains." if cash_shortfall else
                f"Scheduled EMI is at least {HIGH_DTI_PERCENT}% of current income." if high_payment else
                "A contractual debt rate is at least 12%; review its cost alongside liquidity." if has_debt and high_interest else
                "No debt pressure was triggered by the current month."
            ),
            priority=priority,
            evidence=[
                Evidence(label="Outstanding debt", value=state.existing_debt, unit="currency"),
                Evidence(label="Scheduled EMI", value=state.monthly_debt_payments, unit="currency"),
                Evidence(label="Payment-to-income ratio", value=dti, unit="%"),
                Evidence(label="Highest debt APR", value=(state.highest_debt_apr * 100
                         if state.highest_debt_apr is not None else None), unit="%"),
                Evidence(label="Liquid savings", value=state.savings, unit="currency"),
                Evidence(label="Income volatility", value=state.income_volatility * 100, unit="%"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            agent_id=self.agent_id, status="limited" if dti is None and has_debt else "ok",
            findings=[finding], limitations=limitations,
            facts=DebtFacts(review_required=priority or dti is None and has_debt,
                            reason_code=reason_code if reason_code else "unknown_debt" if dti is None and has_debt else None),
        )


class EmergencyAgent:
    agent_id = "emergency"

    def analyze(self, state: FinancialState) -> AgentResult:
        if isinstance(state, DynamicPlanningState):
            return self._analyze_dynamic(state)
        picture = getattr(state, "picture", None)
        coverage = picture.reserve.total_expense_coverage_months.value if picture else state.emergency_fund_months
        gap = (picture.reserve.funding_gap.value if state.monthly_expenses > 0 else None) if picture else (
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
                Evidence(label="Emergency fund coverage", value=coverage, unit="months",
                         source=picture.reserve.total_expense_coverage_months.source if picture else None),
                Evidence(label="Gap to illustrative target", value=gap, unit="currency",
                         source=picture.reserve.funding_gap.source if picture else None),
            ],
            limitations=limitations,
            impact=("Without positive monthly expenses, reserve coverage and the target gap cannot be calculated." if coverage is None else
                    "A smaller accessible reserve leaves less room to absorb a loss of income or an unexpected expense." if priority else
                    "The recorded reserve meets this project's illustrative target based on current expenses."),
            suggested_action=("Enter positive monthly expenses to assess the reserve." if coverage is None else
                              "Consider directing the recorded monthly savings contribution toward the reserve, using the coordinated plan's proposed amount." if priority else
                              "Keep this reserve available for emergencies and review it when your expenses change."),
        )
        return PlanningAgentResult(
            facts=EmergencyFacts(gap=gap, coverage=coverage),
            agent_id=self.agent_id,
            status="limited" if coverage is None else "ok",
            findings=[finding],
            limitations=limitations,
        )

    def _analyze_dynamic(self, state: DynamicPlanningState) -> PlanningAgentResult:
        target = reserve_target_months(state)
        coverage = state.emergency_fund_months
        gap = (max(Decimal("0"), target * state.monthly_expenses - state.emergency_fund)
               if state.monthly_expenses > 0 else None)
        priority = gap is not None and gap > 0
        limitations = [f"The {target}-month reserve target is an illustrative stress rule, not individualized advice."]
        if coverage is None:
            limitations.append("Coverage needs positive scheduled expenses.")
        finding = Finding(
            code="dynamic_reserve_gap" if priority else "dynamic_reserve_coverage",
            title="Review emergency reserve" if priority else "Current emergency coverage",
            reason=(f"Coverage is below the illustrative {target}-month target for this month's income stability."
                    if priority else f"Coverage meets the illustrative {target}-month target."),
            priority=priority,
            evidence=[
                Evidence(label="Emergency fund coverage", value=coverage, unit="months"),
                Evidence(label="Target months", value=target, unit="months"),
                Evidence(label="Gap to illustrative target", value=gap, unit="currency"),
                Evidence(label="Income volatility", value=state.income_volatility * 100, unit="%"),
                Evidence(label="Current surplus", value=state.current_surplus, unit="currency"),
            ],
            limitations=limitations,
        )
        return PlanningAgentResult(
            agent_id=self.agent_id, status="limited" if coverage is None else "ok",
            findings=[finding], limitations=limitations,
            facts=EmergencyFacts(gap=gap, coverage=coverage),
        )
