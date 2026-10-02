"""Deterministic analysis of stored user inputs; no advice or LLM calls."""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Sequence

from app.models import FinancialGoal, FinancialMonth, FinancialProfile, Loan, PlannedExpense, RecurringExpense, User
from app.schemas import AnalysisRead
from app.services.financial_picture import build_financial_picture


HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def _percent(numerator: Decimal | None, denominator: Decimal) -> Decimal | None:
    if numerator is None or denominator <= 0:
        return None
    return (numerator / denominator * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def _clamp(value: Decimal) -> Decimal:
    return min(Decimal("1"), max(Decimal("0"), value))


class FinancialAnalysisService:
    @staticmethod
    def analyze(user: User, profile: FinancialProfile, *,
                expenses: Sequence[RecurringExpense] = (), loans: Sequence[Loan] = (),
                plans: Sequence[PlannedExpense] = (), goals: Sequence[FinancialGoal] = (),
                months: Sequence[FinancialMonth] = (), as_of_date: date | None = None) -> AnalysisRead:
        income = user.monthly_income
        total_expenses = profile.monthly_expenses
        monthly_savings = profile.monthly_savings_contribution
        monthly_debt_payments = profile.monthly_debt_payments

        savings_rate = _percent(monthly_savings, income)
        debt_to_income = _percent(monthly_debt_payments, income)
        expense_to_income = _percent(total_expenses, income)
        emergency_months = (
            (profile.emergency_fund / total_expenses).quantize(CENT, rounding=ROUND_HALF_UP)
            if total_expenses > 0
            else None
        )

        score = None
        if income > 0 and total_expenses > 0 and monthly_savings is not None and monthly_debt_payments is not None:
            savings_fraction = monthly_savings / income
            debt_fraction = monthly_debt_payments / income
            emergency_coverage = profile.emergency_fund / total_expenses
            points = (
                Decimal("30") * _clamp(savings_fraction / Decimal("0.20"))
                + Decimal("30") * _clamp(Decimal("1") - debt_fraction / Decimal("0.50"))
                + Decimal("40") * _clamp(emergency_coverage / Decimal("6"))
            )
            score = int(points.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        return AnalysisRead(
            savings_rate_percent=savings_rate,
            debt_to_income_percent=debt_to_income,
            expense_to_income_percent=expense_to_income,
            emergency_fund_months=emergency_months,
            health_score=score,
            picture=(build_financial_picture(user, profile, expenses=expenses, loans=loans,
                                            plans=plans, goals=goals, months=months,
                                            as_of_date=as_of_date) if as_of_date is not None else None),
        )
