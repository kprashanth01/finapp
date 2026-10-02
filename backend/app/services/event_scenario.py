"""Temporary, account-scoped event calculations over the saved financial picture."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.advisory.service import run_advisory
from app.models import FinancialGoal, FinancialMonth, FinancialProfile, Loan, PlannedExpense, RecurringExpense, User
from app.schemas import Money, ProfileWrite
from app.services.financial_picture import Fact, FinancialPicture, build_financial_picture


EventKind = Literal[
    "income_increase", "income_decrease", "unexpected_expense", "upcoming_expense",
    "subscription_reduction", "additional_loan_payment", "additional_savings",
    "goal_contribution_change",
]
ONE_TIME_EXPENSES = {"unexpected_expense", "upcoming_expense"}
MAX_MONEY = Decimal("9999999999.99")
CENT = Decimal("0.01")


class EventScenarioWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EventKind
    amount: Money
    expense_id: int | None = Field(default=None, gt=0)
    loan_id: int | None = Field(default=None, gt=0)
    goal_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None
    reserved_amount: Money = Decimal("0")
    is_essential: bool = False
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def relevant_fields_only(self):
        self.amount = self.amount.quantize(CENT, rounding=ROUND_HALF_UP)
        self.reserved_amount = self.reserved_amount.quantize(CENT, rounding=ROUND_HALF_UP)
        if self.amount == 0 and self.kind != "goal_contribution_change":
            raise ValueError("Enter a positive event amount.")
        expected = {
            "expense_id": self.kind == "subscription_reduction",
            "loan_id": self.kind == "additional_loan_payment",
            "goal_id": self.kind == "goal_contribution_change",
            "due_date": self.kind == "upcoming_expense",
        }
        for field, required in expected.items():
            if (getattr(self, field) is not None) != required:
                raise ValueError(f"{field} must be supplied only for its matching event.")
        if self.kind not in ONE_TIME_EXPENSES and (self.reserved_amount != 0 or self.name is not None or self.is_essential):
            raise ValueError("Reserved amount, name, and essential flag apply only to expense events.")
        if self.reserved_amount > self.amount:
            raise ValueError("Reserved amount cannot exceed the expense amount.")
        return self


class LoanEffect(BaseModel):
    loan_id: int
    balance_before: Decimal
    balance_after: Decimal


class GoalEffect(BaseModel):
    goal_id: int
    current_plan_allocation: Decimal | None
    hypothetical_contribution: Decimal
    current_plan_gap: Decimal | None
    hypothetical_gap: Decimal | None
    budget_shortfall: Decimal | None


class EventScenarioRead(BaseModel):
    schema_version: Literal["event-scenario-v1"] = "event-scenario-v1"
    event: EventScenarioWrite
    before: FinancialPicture
    after: FinancialPicture
    one_time_cash_need: Decimal
    illustrative_current_month_cash_after_event: Decimal | None
    loan_effect: LoanEffect | None = None
    goal_effect: GoalEffect | None = None
    limitations: list[str]


def _profile_copy(profile: FinancialProfile) -> SimpleNamespace:
    values = ProfileWrite.model_validate(profile, from_attributes=True).model_dump()
    values["guaranteed_monthly_income"] = profile.guaranteed_monthly_income
    return SimpleNamespace(**values)


def _goal_effect(before, goal_id: int, contribution: Decimal,
                 total_budget: Decimal | None) -> GoalEffect:
    prior = next(item for item in before.advice.monthly_plan.goal_allocations
                 if item.requirement.goal.id == goal_id)
    required = prior.requirement.required_monthly
    return GoalEffect(
        goal_id=goal_id,
        current_plan_allocation=prior.allocated_monthly,
        hypothetical_contribution=contribution,
        current_plan_gap=prior.funding_gap,
        hypothetical_gap=max(Decimal("0"), required - contribution) if required is not None else None,
        budget_shortfall=(max(Decimal("0"), contribution - total_budget)
                          if total_budget is not None else None),
    )


def _mark_hypothetical(before: FinancialPicture, after: FinancialPicture, kind: EventKind) -> FinancialPicture:
    def changed_fact(earlier: Fact, current: Fact) -> Fact:
        if earlier.value == current.value:
            return current
        return current.model_copy(update={
            "source": f"scenario.{kind}+{current.source}",
            "status": "estimate" if current.status == "known" else current.status,
            "note": f"Hypothetical event; not saved. {current.note}",
        })

    for group_name in ("income", "spending", "reserve"):
        old_group, new_group = getattr(before, group_name), getattr(after, group_name)
        for field in type(new_group).model_fields:
            old_value, new_value = getattr(old_group, field), getattr(new_group, field)
            if isinstance(old_value, Fact) and isinstance(new_value, Fact):
                setattr(new_group, field, changed_fact(old_value, new_value))
    updates = {}
    for field in ("planned_due_90_days", "unreserved_due_90_days", "goal_funding_gap"):
        updates[field] = changed_fact(getattr(before, field), getattr(after, field))
    for obligation in after.obligations:
        if obligation.id == -1 and obligation.kind == "planned_expense":
            obligation.note = "Hypothetical one-time cost; not saved. " + obligation.note
    return after.model_copy(update=updates)


def preview_event(
    user: User, profile: FinancialProfile, event: EventScenarioWrite, *,
    expenses: Sequence[RecurringExpense], loans: Sequence[Loan], plans: Sequence[PlannedExpense],
    goals: Sequence[FinancialGoal], months: Sequence[FinancialMonth], as_of_date: date,
) -> EventScenarioRead:
    """Build before/after facts in memory; never update an ORM row or session."""
    before = build_financial_picture(user, profile, expenses=expenses, loans=loans, plans=plans,
                                     goals=goals, months=months, as_of_date=as_of_date)
    changed_user = SimpleNamespace(monthly_income=user.monthly_income)
    changed_profile = _profile_copy(profile)
    changed_expenses, changed_plans = list(expenses), list(plans)
    one_time_need = Decimal("0")
    cash_this_month = False
    loan_effect = goal_effect = None
    limitations = [
        "This is a temporary calculation. It does not save a Profile, Month, Goal, loan, or plan.",
        "Gross cash flow is before tax and unrecorded costs; it is not spendable cash.",
    ]

    if event.kind in ("income_increase", "income_decrease"):
        direction = 1 if event.kind == "income_increase" else -1
        changed_user.monthly_income += direction * event.amount
        if not 0 <= changed_user.monthly_income <= MAX_MONEY:
            raise ValueError("The changed monthly income must be between zero and the supported money limit.")
        if (changed_profile.guaranteed_monthly_income is not None and
                changed_profile.guaranteed_monthly_income > changed_user.monthly_income):
            changed_profile.guaranteed_monthly_income = None
            limitations.append("The lower hypothetical income overrides the saved guaranteed portion for this preview.")
        limitations.append("Recorded income history is unchanged; this event changes only the current estimate.")

    elif event.kind == "subscription_reduction":
        selected = next((row for row in expenses if row.id == event.expense_id), None)
        if selected is None or selected.category != "discretionary":
            raise ValueError("Choose a saved discretionary recurring expense in this account.")
        if event.amount > selected.monthly_amount:
            raise ValueError("The reduction cannot exceed that expense's saved monthly amount.")
        changed_profile.monthly_expenses -= event.amount
        changed_expenses = [SimpleNamespace(id=row.id, name=row.name, category=row.category,
                            monthly_amount=row.monthly_amount - event.amount) if row.id == event.expense_id else row
                            for row in expenses]
        limitations.append("Assumes the selected recurring cost falls by this amount every month; no cancellation is made.")

    elif event.kind in ONE_TIME_EXPENSES:
        due = as_of_date if event.kind == "unexpected_expense" else event.due_date
        if due < as_of_date:
            raise ValueError("An upcoming expense date cannot be in the past.")
        changed_plans.append(SimpleNamespace(
            id=-1, name=event.name or ("Unexpected expense" if event.kind == "unexpected_expense" else "Upcoming expense"),
            estimated_amount=event.amount, amount_reserved=event.reserved_amount,
            due_date=due, is_essential=event.is_essential,
        ))
        one_time_need = event.amount - event.reserved_amount
        cash_this_month = (due.year, due.month) == (as_of_date.year, as_of_date.month)
        limitations.append("A one-time cost is listed separately; it does not become a recurring monthly expense.")
        limitations.append("The entered reserved amount is assumed available for this cost and is not deducted from the emergency reserve.")

    elif event.kind == "additional_loan_payment":
        selected = next((row for row in loans if row.id == event.loan_id), None)
        if selected is None or selected.remaining_balance is None:
            raise ValueError("Choose a saved loan with a known remaining balance in this account.")
        if event.amount > selected.remaining_balance or event.amount > profile.existing_debt:
            raise ValueError("The extra payment cannot exceed the saved remaining debt.")
        changed_profile.existing_debt -= event.amount
        loan_effect = LoanEffect(loan_id=selected.id, balance_before=selected.remaining_balance,
                                 balance_after=selected.remaining_balance - event.amount)
        one_time_need = event.amount
        cash_this_month = True
        limitations.append("Assumes the entire extra payment reduces principal; interest, fees, and EMI changes are not modeled.")

    elif event.kind == "additional_savings":
        if (changed_profile.emergency_fund + event.amount > MAX_MONEY or
                changed_profile.savings + event.amount > MAX_MONEY):
            raise ValueError("The changed savings balance exceeds the supported money limit.")
        changed_profile.emergency_fund += event.amount
        changed_profile.savings += event.amount
        one_time_need = event.amount
        cash_this_month = True
        limitations.append("Assumes new cash is added to emergency savings, not transferred from existing savings.")

    elif event.kind == "goal_contribution_change":
        selected = next((row for row in goals if row.id == event.goal_id and not row.archived), None)
        if selected is None:
            raise ValueError("Choose an active saved goal in this account.")
        earlier = run_advisory(user, profile, goals, as_of_date)
        goal_effect = _goal_effect(earlier, selected.id, event.amount,
                                   profile.monthly_savings_contribution)
        limitations.append("The before amount is the current plan suggestion; the after amount is your hypothetical goal contribution, not a saved commitment.")
        limitations.append("Other goal and emergency allocations are not rebalanced for this one-goal check.")
        if goal_effect.budget_shortfall is not None and goal_effect.budget_shortfall > 0:
            limitations.append("This goal contribution alone exceeds the saved total monthly savings budget.")
        if event.amount > max(Decimal("0"), user.monthly_income - profile.monthly_expenses):
            limitations.append("The goal contribution also exceeds the gross monthly surplus ceiling before tax.")

    after = build_financial_picture(changed_user, changed_profile, expenses=changed_expenses,
                                    loans=loans, plans=changed_plans, goals=goals,
                                    months=months, as_of_date=as_of_date)
    after = _mark_hypothetical(before, after, event.kind)
    illustrative = after.spending.gross_cash_flow.value - one_time_need if cash_this_month else None
    if cash_this_month:
        limitations.append("Current-month cash after the one-time amount uses gross-income arithmetic; check actual take-home cash and due dates.")
    return EventScenarioRead(
        event=event, before=before, after=after, one_time_cash_need=one_time_need,
        illustrative_current_month_cash_after_event=illustrative,
        loan_effect=loan_effect, goal_effect=goal_effect, limitations=limitations,
    )
