"""Contextual, explainable actions from saved financial facts; no account writes."""

from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.advisory.rules import PLANNING_MONTH_DAYS
from app.models import FinancialProfile
from app.services.financial_picture import Fact, FinancialPicture


ZERO = Decimal("0")
CENT = Decimal("0.01")
Area = Literal["cash_flow", "income", "upcoming_cost", "debt", "emergency", "goals", "data"]
Urgency = Literal["urgent", "high", "normal", "information"]


class SupportingCalculation(BaseModel):
    label: str
    value: Decimal | None
    unit: Literal["currency", "months", "percent", "days", "count"]
    source: str


class UserRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)

    priority: int
    code: str
    area: Area
    urgency: Urgency
    action: str
    reason: str
    supporting_calculations: list[SupportingCalculation]
    assumptions: list[str]
    priority_factors: list[str]
    target_view: Literal["profile", "goals", "months"]
    target_id: int | None = None


class UserRecommendationsRead(BaseModel):
    schema_version: Literal["user-recommendations-v1"] = "user-recommendations-v1"
    as_of_date: date
    basis: Literal["saved_financial_picture"] = "saved_financial_picture"
    summary: str
    recommendations: list[UserRecommendation]
    limitations: list[str]


def _fact(label: str, fact: Fact, unit: Literal["currency", "months", "percent"] = "currency") -> SupportingCalculation:
    return SupportingCalculation(label=label, value=fact.value, unit=unit, source=fact.source)


def _value(label: str, value: Decimal | None, source: str,
           unit: Literal["currency", "months", "percent", "days", "count"] = "currency") -> SupportingCalculation:
    return SupportingCalculation(label=label, value=value, unit=unit, source=source)


def _urgency(score: int) -> Urgency:
    return "urgent" if score >= 110 else "high" if score >= 80 else "normal" if score >= 50 else "information"


def recommend(picture: FinancialPicture, profile: FinancialProfile) -> UserRecommendationsRead:
    """Rank concrete actions from the current account picture and entered priorities."""
    as_of = picture.as_of_date
    cash = picture.spending.gross_cash_flow.value
    surplus_ceiling = picture.spending.available_surplus_upper_bound.value
    budget = picture.spending.entered_savings_capacity.value
    candidates: list[tuple[int, date, str, UserRecommendation]] = []

    def add(score: int, code: str, area: Area, action: str, reason: str,
            calculations: list[SupportingCalculation], assumptions: list[str],
            factors: list[str], view: Literal["profile", "goals", "months"],
            due: date | None = None, target_id: int | None = None) -> None:
        item = UserRecommendation(
            priority=0, code=code, area=area, urgency=_urgency(score), action=action,
            reason=reason, supporting_calculations=calculations, assumptions=assumptions,
            priority_factors=factors, target_view=view, target_id=target_id,
        )
        candidates.append((score, due or date.max, code, item))

    if cash < 0:
        add(120, "cash_shortfall", "cash_flow", "Review this month's cash shortfall",
            f"Entered monthly expenses exceed the current gross income estimate by {abs(cash):,.2f}. "
            "Check required payments, actual take-home income, and costs that can be changed before assigning new savings.",
            [_value("Gross shortfall", abs(cash), picture.spending.gross_cash_flow.source),
             _fact("Monthly expenses", picture.spending.monthly_total)],
            ["Gross income omits tax and payment timing; the actual cash shortfall may differ."],
            ["Current gross deficit", "Required bills and debt remain due"], "profile")

    if budget is not None and budget > surplus_ceiling:
        add(104, "savings_budget_over_ceiling", "cash_flow", "Check the monthly savings amount you entered",
            "The saved monthly savings budget exceeds gross income left after entered expenses. Confirm take-home cash and revise the amount if needed.",
            [_fact("Saved monthly savings budget", picture.spending.entered_savings_capacity),
             _fact("Gross surplus ceiling", picture.spending.available_surplus_upper_bound)],
            ["The gross ceiling is not verified spendable money.", "No savings transfer is made."],
            ["Entered savings budget exceeds gross ceiling"], "profile")

    for item in picture.obligations:
        if item.kind != "planned_expense":
            continue
        days = (item.due_date - as_of).days
        if days > 90 or (item.unreserved_amount == 0 and days >= 0):
            continue
        if item.is_essential:
            score = 130 if days < 0 else 115 if days <= 7 else 95 if days <= 30 else 70
        else:
            score = 75 if days < 0 else 60 if days <= 30 else 45
        unknown = item.unreserved_amount is None
        label = "overdue" if days < 0 else f"due in {days} days"
        reason = (f"{item.name} is {label}. The amount already reserved is unknown, so its funding need cannot be confirmed."
                  if unknown else
                  f"{item.name} is {label} with {item.unreserved_amount:,.2f} not marked as reserved.")
        add(score, f"planned_cost_{item.id}", "upcoming_cost",
            f"Check funding and due date for {item.name}" if unknown else f"Review payment for {item.name}",
            reason,
            [_value("Estimated cost", item.amount, "saved_planned_expense"),
             _value("Amount not marked reserved", item.unreserved_amount, "saved_planned_expense"),
             _value("Days until due", Decimal(days), "saved_planned_expense.due_date", "days")],
            ["Reserved means entered as set aside, not verified cash.",
             "This one-time cost is separate from recurring monthly expenses."],
            ["Marked essential" if item.is_essential else "Marked nonessential",
             "Overdue" if days < 0 else "Near due date" if days <= 30 else "Due within 90 days"],
            "profile", due=item.due_date)

    for item in picture.obligations:
        if item.kind != "loan_payment":
            continue
        if item.rate_change_date is not None:
            days = (item.rate_change_date - as_of).days
            if 0 <= days <= 90:
                increased = (item.annual_interest_rate_percent is not None and
                             item.new_annual_interest_rate_percent > item.annual_interest_rate_percent)
                score = 98 if increased and days <= 30 else 72 if days <= 30 else 54
                add(score, f"loan_rate_{item.id}", "debt", f"Review the rate change for {item.name}",
                    f"The entered rate-change date is {item.rate_change_date.isoformat()}. Confirm the lender's new payment and terms before relying on the current budget.",
                    [_value("Current entered annual rate", item.annual_interest_rate_percent, "saved_loan_detail", "percent"),
                     _value("New entered annual rate", item.new_annual_interest_rate_percent, "saved_loan_detail", "percent"),
                     _value("Current monthly payment", item.amount, "saved_loan_detail")],
                    ["The regular loan payment is already included in Profile expenses; it is not added again.",
                     "A rate change does not automatically recalculate the monthly payment."],
                    ["Rate increases" if increased else "Loan terms change",
                     "Change within 30 days" if days <= 30 else "Change within 90 days"],
                    "profile", due=item.rate_change_date)
        if item.due_date is not None and item.amount is not None:
            days = (item.due_date - as_of).days
            if 0 <= days <= 7:
                add(108 if cash < 0 else 48, f"loan_due_{item.id}", "debt",
                    f"Confirm the upcoming {item.name} payment",
                    f"The entered payment day places the next {item.name} payment in {days} days. Check the lender schedule and available cash.",
                    [_value("Entered monthly loan payment", item.amount, "saved_loan_detail"),
                     _value("Days until estimated due date", Decimal(days), "saved_loan_detail.payment_day", "days")],
                    ["This payment is already included in Profile expenses; do not add it again.",
                     "The date follows the entered day of month and may differ from the lender schedule."],
                    ["Payment within 7 days", "Current gross shortfall" if cash < 0 else "No current gross shortfall"],
                    "profile", due=item.due_date)

    reference = picture.income.conservative_reference.value
    essential = picture.spending.known_essential.value
    if reference is not None and essential is not None and reference < essential:
        gap = essential - reference
        add(106, "income_stress", "income", "Plan for a lower-income month",
            f"The recent low-income reference is {gap:,.2f} below even the known monthly essential spending floor. "
            "Review which obligations must be covered if that lower income recurs.",
            [_fact("Conservative income reference", picture.income.conservative_reference),
             _fact("Known essential spending floor", picture.spending.known_essential),
             _value("Gap against known essentials", gap, "income_reference_minus_known_essentials")],
            ["The reference uses three consecutive recent recorded months and is not a forecast.",
             "Partial expense detail can understate the true essential amount."],
            ["Recent lower income", "Known essential costs exceed stress reference"], "months")
    elif getattr(profile, "income_pattern", None) in ("variable", "mixed") and reference is None:
        add(42, "income_history", "data", "Record more income months",
            "The saved income pattern is variable, but three consecutive recent recorded months are not available for a conservative stress reference.",
            [_value("Recorded months", Decimal(picture.income.observed_months), "recorded_months.last_12", "count")],
            ["Recorded months are observations, not guaranteed future income."],
            ["Variable income", "Short recorded history"], "months")

    reserve_gap = picture.reserve.funding_gap.value
    coverage = picture.reserve.total_expense_coverage_months.value
    if reserve_gap > 0:
        score = 50 if cash < 0 else 85 if coverage is not None and coverage < 1 else 56
        action = ("Revisit your reserve after the current shortfall" if cash < 0 else
                  "Review your emergency reserve plan")
        reason = (f"The saved emergency reserve is {reserve_gap:,.2f} below the app's "
                  f"{picture.reserve.target_months:g}-month total-expense target.")
        if budget is None:
            reason += " Add a realistic monthly savings budget before estimating an allocation."
        elif cash >= 0:
            reason += " Consider it alongside due bills and your saved goal priorities."
        add(score, "reserve_gap", "emergency", action, reason,
            [_fact("Reserve funding gap", picture.reserve.funding_gap),
             _fact("Coverage of monthly expenses", picture.reserve.total_expense_coverage_months, "months"),
             _fact("Entered monthly savings budget", picture.spending.entered_savings_capacity)],
            ["The three-month target is the app's illustrative project rule; the right reserve depends on your circumstances.",
             "A gross surplus does not prove the entered savings budget is affordable."],
            ["Current cash shortfall" if cash < 0 else "Reserve below one month" if coverage is not None and coverage < 1 else "Reserve below project target"],
            "profile")

    goal_bonus = {"high": 10, "medium": 5, "low": 0}
    for goal in picture.goals:
        if goal.remaining_amount <= 0:
            continue
        days = (goal.target_date - as_of).days
        if days <= 0:
            score = 90 + goal_bonus[goal.priority]
            action = f"Review the target date for {goal.name}"
            reason = f"The saved target date has passed with {goal.remaining_amount:,.2f} still needed."
            monthly = None
        else:
            score = (75 if days <= 30 else 60 if days <= 90 else 32) + goal_bonus[goal.priority]
            action = f"Review the funding plan for {goal.name}"
            months = (days + PLANNING_MONTH_DAYS - 1) // PLANNING_MONTH_DAYS
            monthly = (goal.remaining_amount / months).quantize(CENT, rounding=ROUND_CEILING)
            reason = (f"{goal.remaining_amount:,.2f} remains for this {goal.priority}-priority goal by "
                      f"{goal.target_date.isoformat()}; roughly {monthly:,.2f} per 30-day month would be needed.")
            if budget is not None and monthly > budget:
                reason += " That amount exceeds the entire saved monthly savings budget."
        add(score, f"goal_{goal.id}", "goals", action, reason,
            [_value("Remaining goal target", goal.remaining_amount, "saved_goal.target_minus_saved"),
             _value("Approximate monthly need", monthly, "remaining_goal_target_and_date"),
             _fact("Entered monthly savings budget", picture.spending.entered_savings_capacity)],
            ["Monthly need uses 30-day months, no growth, and no competing allocations.",
             "The saved goal priority is user entered; no contribution is committed."],
            [f"User priority: {goal.priority}", "Overdue goal" if days <= 0 else
             "Deadline within 30 days" if days <= 30 else "Deadline within 90 days" if days <= 90 else "Later deadline"],
            "goals", due=goal.target_date, target_id=goal.id)

    if profile.monthly_debt_payments is None:
        add(43, "missing_debt_payment", "data", "Add the total monthly debt payment",
            "Individual loan details cannot replace the missing aggregate payment in debt ratios or the expense breakdown.",
            [_fact("Debt payment share", picture.spending.debt_to_income_percent, "percent")],
            ["Leave unknown amounts blank rather than entering zero."],
            ["Debt payment unknown"], "profile")

    if not candidates:
        add(10, "review_when_changed", "data", "Review your plan when your circumstances change",
            "No immediate issue is flagged by the saved facts used for this check.",
            [_fact("Gross monthly cash flow", picture.spending.gross_cash_flow)],
            ["This does not prove all future costs are covered or that the plan is affordable after tax."],
            ["No flagged shortfall, due cost, reserve gap, or unfinished goal"], "profile")

    ordered = sorted(candidates, key=lambda entry: (-entry[0], entry[1], entry[2]))
    recommendations = [item.model_copy(update={"priority": index})
                       for index, (_, _, _, item) in enumerate(ordered, start=1)]
    return UserRecommendationsRead(
        as_of_date=as_of,
        summary=recommendations[0].action,
        recommendations=recommendations,
        limitations=[
            "Decisions use saved values and a gross-income estimate; tax, take-home pay, and payment timing are not modeled.",
            "Expense detail may be incomplete, and a reserved amount is not verified cash.",
            "These are deterministic planning prompts, not transactions or guaranteed financial outcomes.",
        ],
    )
