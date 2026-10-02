"""Account financial facts with explicit provenance; no recommendation or forecast."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from app.advisory.rules import EMERGENCY_TARGET_MONTHS
from app.models import FinancialGoal, FinancialMonth, FinancialProfile, Loan, PlannedExpense, RecurringExpense, User


CENT = Decimal("0.01")
ZERO = Decimal("0")
Status = Literal["known", "partial", "unknown", "estimate"]


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: Decimal | None
    source: str
    status: Status
    note: str


class IncomeFacts(BaseModel):
    expected_monthly: Fact
    guaranteed_monthly: Fact
    observed_average: Fact
    observed_recent: Fact
    observed_minimum: Fact
    variability_percent: Fact
    conservative_reference: Fact
    observed_months: int
    recent_period: date | None


class SpendingFacts(BaseModel):
    monthly_total: Fact
    known_essential_fixed: Fact
    known_essential_variable: Fact
    known_essential: Fact
    known_discretionary: Fact
    unclassified_monthly: Fact
    exact_essential: Fact
    exact_discretionary: Fact
    gross_cash_flow: Fact
    available_surplus_upper_bound: Fact
    entered_savings_capacity: Fact
    savings_rate_percent: Fact
    debt_to_income_percent: Fact


class ReserveFacts(BaseModel):
    total_expense_coverage_months: Fact
    essential_coverage_months: Fact
    target_months: Decimal
    funding_gap: Fact


class GoalGap(BaseModel):
    id: int
    name: str
    target_date: date
    priority: str
    remaining_amount: Decimal


class Obligation(BaseModel):
    id: int
    kind: Literal["planned_expense", "loan_payment"]
    name: str
    due_date: date | None
    amount: Decimal | None
    unreserved_amount: Decimal | None
    is_essential: bool
    is_overdue: bool
    annual_interest_rate_percent: Decimal | None = None
    rate_change_date: date | None = None
    new_annual_interest_rate_percent: Decimal | None = None
    note: str


class FinancialPicture(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal["financial-picture-v1"] = "financial-picture-v1"
    as_of_date: date
    income: IncomeFacts
    spending: SpendingFacts
    reserve: ReserveFacts
    goal_funding_gap: Fact
    goals: list[GoalGap]
    planned_due_90_days: Fact
    unreserved_due_90_days: Fact
    obligations: list[Obligation]
    limitations: list[str]


def _fact(value: Decimal | None, source: str, note: str, status: Status | None = None) -> Fact:
    return Fact(value=value, source=source, status=status or ("known" if value is not None else "unknown"), note=note)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _percent(value: Decimal | None, denominator: Decimal) -> Decimal | None:
    return _money(value / denominator * 100) if value is not None and denominator > 0 else None


def _previous_month(period: date) -> date:
    return date(period.year - 1, 12, 1) if period.month == 1 else date(period.year, period.month - 1, 1)


def _next_due(as_of_date: date, day: int) -> date:
    year, month = as_of_date.year, as_of_date.month
    candidate = date(year, month, min(day, monthrange(year, month)[1]))
    if candidate < as_of_date:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        candidate = date(year, month, min(day, monthrange(year, month)[1]))
    return candidate


def build_financial_picture(
    user: User, profile: FinancialProfile, *,
    expenses: Sequence[RecurringExpense] = (), loans: Sequence[Loan] = (),
    plans: Sequence[PlannedExpense] = (), goals: Sequence[FinancialGoal] = (),
    months: Sequence[FinancialMonth] = (), as_of_date: date,
) -> FinancialPicture:
    income, total = user.monthly_income, profile.monthly_expenses
    recorded = sorted((row for row in months if row.period <= as_of_date.replace(day=1)),
                      key=lambda row: row.period)[-12:]
    incomes = [row.monthly_income for row in recorded]
    average = sum(incomes, ZERO) / len(incomes) if incomes else None
    variability = None
    if len(incomes) >= 2 and average > 0:
        variance = sum(((item - average) ** 2 for item in incomes), ZERO) / len(incomes)
        variability = _money(variance.sqrt() / average * 100)
    recent = recorded[-1] if recorded else None
    recent_three = recorded[-3:]
    consecutive = (len(recent_three) == 3
                   and all(recent_three[i - 1].period == _previous_month(recent_three[i].period)
                           for i in (1, 2))
                   and recent_three[-1].period in (as_of_date.replace(day=1), _previous_month(as_of_date.replace(day=1))))
    conservative = min(income, *(row.monthly_income for row in recent_three)) if consecutive else None
    income_facts = IncomeFacts(
        expected_monthly=_fact(income, "user.current_income_estimate", "Current gross monthly estimate; not take-home pay."),
        guaranteed_monthly=_fact(profile.guaranteed_monthly_income, "profile.guaranteed_income",
                                 "Only the amount you identified as assured; blank means unknown."),
        observed_average=_fact(_money(average) if average is not None else None, "recorded_months.last_12",
                               "Mean of recorded gross monthly income; not a guarantee."),
        observed_recent=_fact(recent.monthly_income if recent else None, "recorded_months.latest",
                              "Most recently recorded month; check its date."),
        observed_minimum=_fact(min(incomes) if incomes else None, "recorded_months.last_12",
                               "Lowest entered month in this sample, not a predicted floor."),
        variability_percent=_fact(variability, "recorded_months.last_12",
                                  "Population standard deviation divided by mean; needs two months and a positive mean."),
        conservative_reference=_fact(conservative, "current_estimate_and_recent_recorded_months",
                                     "Lesser of current estimate and lowest of three consecutive recent months; a stress reference, not guaranteed income.",
                                     "estimate" if conservative is not None else "unknown"),
        observed_months=len(recorded), recent_period=recent.period if recent else None,
    )

    fixed_items = sum((row.monthly_amount for row in expenses if row.category == "essential_fixed"), ZERO)
    variable_items = sum((row.monthly_amount for row in expenses if row.category == "essential_variable"), ZERO)
    essential_items = fixed_items + variable_items
    discretionary_items = sum((row.monthly_amount for row in expenses if row.category == "discretionary"), ZERO)
    item_total = essential_items + discretionary_items
    debt_payment = profile.monthly_debt_payments
    remainder = total - item_total - debt_payment if debt_payment is not None else None
    complete = remainder == 0 if remainder is not None else False
    essential_floor = essential_items + (debt_payment if debt_payment is not None else ZERO)
    cash_flow = income - total
    spending = SpendingFacts(
        monthly_total=_fact(total, "profile.monthly_expenses", "Includes required debt payments."),
        known_essential_fixed=_fact(fixed_items, "expense_details", "Itemized essential fixed costs; excludes loan payments.",
                                    "partial" if not complete else "known"),
        known_essential_variable=_fact(variable_items, "expense_details", "Itemized essential variable costs.",
                                       "partial" if not complete else "known"),
        known_essential=_fact(essential_floor, "expense_details_and_profile_debt_payment",
                              "Known monthly essential floor; other spending may be uncategorized.", "partial" if not complete else "known"),
        known_discretionary=_fact(discretionary_items, "expense_details",
                                  "Only itemized discretionary spending.", "partial" if not complete else "known"),
        unclassified_monthly=_fact(remainder, "profile_minus_itemized_expenses_and_debt_payment",
                                   "Unclassified non-debt spending; unknown when aggregate debt payment is missing."),
        exact_essential=_fact(essential_floor if complete else None, "complete_expense_breakdown",
                              "Needs a known aggregate debt payment and itemized non-debt spending that covers the total."),
        exact_discretionary=_fact(discretionary_items if complete else None, "complete_expense_breakdown",
                                  "Needs a complete non-debt expense breakdown."),
        gross_cash_flow=_fact(cash_flow, "current_income_estimate_minus_profile_expenses",
                              "Gross-income arithmetic before taxes and unrecorded costs; negative means a gross shortfall."),
        available_surplus_upper_bound=_fact(max(ZERO, cash_flow), "gross_cash_flow",
                                            "An upper bound only; not verified spendable cash.", "estimate"),
        entered_savings_capacity=_fact(profile.monthly_savings_contribution, "profile.monthly_savings_contribution",
                                       "Your entered monthly allocation budget, not inferred from gross cash flow."),
        savings_rate_percent=_fact(_percent(profile.monthly_savings_contribution, income), "profile_contribution_divided_by_gross_income",
                                   "Needs a savings contribution and positive gross income."),
        debt_to_income_percent=_fact(_percent(debt_payment, income), "profile_debt_payment_divided_by_gross_income",
                                     "Needs an aggregate debt payment and positive gross income; loan items do not replace it."),
    )

    total_coverage = _money(profile.emergency_fund / total) if total > 0 else None
    essential_coverage = _money(profile.emergency_fund / essential_floor) if complete and essential_floor > 0 else None
    reserve = ReserveFacts(
        total_expense_coverage_months=_fact(total_coverage, "profile_emergency_fund_divided_by_total_expenses",
                                            "Uses total monthly expenses, matching the current saved Advisor."),
        essential_coverage_months=_fact(essential_coverage, "profile_emergency_fund_divided_by_complete_essentials",
                                        "Available only with a complete expense breakdown and positive essentials."),
        target_months=EMERGENCY_TARGET_MONTHS,
        funding_gap=_fact(max(ZERO, _money(total * EMERGENCY_TARGET_MONTHS - profile.emergency_fund)),
                          "profile_total_expenses_and_emergency_fund",
                          "Gap to the current Advisor's three-month total-expense reserve target."),
    )

    goal_rows = sorted((row for row in goals if not row.archived), key=lambda row: (row.target_date, row.id))
    goal_gaps = [GoalGap(id=row.id, name=row.name, target_date=row.target_date, priority=row.priority,
                         remaining_amount=max(ZERO, row.target_amount - row.saved_amount)) for row in goal_rows]
    obligations = []
    for row in plans:
        obligations.append(Obligation(
            id=row.id, kind="planned_expense", name=row.name, due_date=row.due_date,
            amount=row.estimated_amount,
            unreserved_amount=(max(ZERO, row.estimated_amount - row.amount_reserved)
                               if row.amount_reserved is not None else None),
            is_essential=row.is_essential, is_overdue=row.due_date < as_of_date,
            note="One-time cost; reserved amount is unknown when blank.",
        ))
    for row in loans:
        obligations.append(Obligation(
            id=row.id, kind="loan_payment", name=row.name,
            due_date=_next_due(as_of_date, row.payment_day) if row.payment_day is not None else None,
            amount=row.monthly_payment, unreserved_amount=None,
            is_essential=True, is_overdue=False,
            annual_interest_rate_percent=getattr(row, "annual_interest_rate_percent", None),
            rate_change_date=getattr(row, "rate_change_date", None),
            new_annual_interest_rate_percent=getattr(row, "new_annual_interest_rate_percent", None),
            note="Recurring payment already in Profile expenses. Next date follows the entered calendar day and may differ from the lender schedule; rate changes do not recalculate the payment.",
        ))
    obligations.sort(key=lambda row: (row.due_date is None, row.due_date or date.max, row.kind, row.id))
    due_90 = [row for row in obligations if row.kind == "planned_expense" and as_of_date <= row.due_date <= as_of_date + timedelta(days=90)]
    due_total = sum((row.amount for row in due_90), ZERO)
    due_unreserved = (sum((row.unreserved_amount for row in due_90), ZERO)
                      if all(row.unreserved_amount is not None for row in due_90) else None)
    limitations = [
        "Income uses gross values; taxes, take-home pay, and payment timing are not modeled.",
        "Recorded months are observations. Three consecutive recent months give a stress reference, not a forecast.",
        "Partial expense detail gives lower bounds, not a complete essential/discretionary split.",
        "One-time planned costs and goal targets are shown separately; avoid entering the same cost twice.",
        "These calculations do not alter the existing saved Advisor recommendation.",
    ]
    if profile.monthly_savings_contribution is not None and profile.monthly_savings_contribution > max(ZERO, cash_flow):
        limitations.append("The entered monthly savings budget exceeds the gross surplus ceiling; review taxes, timing, or the entered amounts.")
    if debt_payment is None:
        limitations.append("Aggregate debt payment is unknown; entered loan payments do not silently replace it in ratios or expense categories.")
    return FinancialPicture(
        as_of_date=as_of_date, income=income_facts, spending=spending, reserve=reserve,
        goal_funding_gap=_fact(sum((row.remaining_amount for row in goal_gaps), ZERO), "active_goals",
                               "Total remaining target amount, not the monthly amount needed by each deadline."),
        goals=goal_gaps,
        planned_due_90_days=_fact(due_total, "planned_expenses_due_within_90_days",
                                  "One-time estimated costs only; excludes recurring loan payments."),
        unreserved_due_90_days=_fact(due_unreserved, "planned_expenses_due_within_90_days",
                                     "Unknown if any included cost has no entered reserved amount."),
        obligations=obligations,
        limitations=limitations,
    )
