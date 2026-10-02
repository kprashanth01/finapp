"""Reconcile optional descriptions with the existing aggregate profile."""

from decimal import Decimal
from typing import Iterable

from app.models import FinancialProfile, Loan, RecurringExpense, User


def validate_detail_totals(
    user: User,
    profile: FinancialProfile,
    recurring_expenses: Iterable[RecurringExpense],
    loans: Iterable[Loan],
) -> None:
    expenses = tuple(recurring_expenses)
    debts = tuple(loans)
    guarantee = profile.guaranteed_monthly_income
    if guarantee is not None and guarantee > user.monthly_income:
        raise ValueError("Guaranteed income cannot exceed the current gross monthly income estimate.")
    debt_payment = profile.monthly_debt_payments
    described_loan_payments = sum((item.monthly_payment for item in debts if item.monthly_payment is not None), Decimal("0"))
    expense_limit = profile.monthly_expenses - (debt_payment if debt_payment is not None else described_loan_payments)
    if sum((item.monthly_amount for item in expenses), Decimal("0")) > expense_limit:
        raise ValueError("Recurring expense details exceed monthly expenses after known debt payments.")
    if sum((item.remaining_balance for item in debts if item.remaining_balance is not None), Decimal("0")) > profile.existing_debt:
        raise ValueError("Loan balances exceed the outstanding debt total in Profile.")
    if debt_payment is not None and described_loan_payments > debt_payment:
        raise ValueError("Loan payments exceed the monthly debt payment total in Profile.")
