"""Strict, account-scoped input contracts for optional financial detail."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas import Money, Name


class DetailWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: int | None = Field(default=None, ge=1)
    name: Name


class RecurringExpenseWrite(DetailWrite):
    monthly_amount: Money = Field(gt=0)
    category: Literal["essential_fixed", "essential_variable", "discretionary"]


class LoanWrite(DetailWrite):
    remaining_balance: Money | None = None
    monthly_payment: Money | None = None
    loan_type: str | None = Field(default=None, max_length=40)
    annual_interest_rate_percent: Decimal | None = Field(default=None, ge=0, le=999.99, max_digits=5, decimal_places=2)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    rate_change_date: date | None = None
    new_annual_interest_rate_percent: Decimal | None = Field(default=None, ge=0, le=999.99, max_digits=5, decimal_places=2)

    @model_validator(mode="after")
    def rate_change_is_complete(self):
        if (self.rate_change_date is None) != (self.new_annual_interest_rate_percent is None):
            raise ValueError("Enter both the rate-change date and new annual rate, or leave both blank.")
        return self


class PlannedExpenseWrite(DetailWrite):
    estimated_amount: Money = Field(gt=0)
    amount_reserved: Money | None = None
    due_date: date
    is_essential: bool = False

    @model_validator(mode="after")
    def reserved_amount_fits(self):
        if self.amount_reserved is not None and self.amount_reserved > self.estimated_amount:
            raise ValueError("Amount reserved cannot exceed the estimated cost.")
        return self


class FinancialDetailsWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    income_pattern: Literal["stable", "variable", "mixed"] | None = None
    guaranteed_monthly_income: Money | None = None
    recurring_expenses: list[RecurringExpenseWrite] = Field(max_length=100)
    loans: list[LoanWrite] = Field(max_length=100)
    planned_expenses: list[PlannedExpenseWrite] = Field(max_length=100)


class RecurringExpenseRead(RecurringExpenseWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class LoanRead(LoanWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PlannedExpenseRead(PlannedExpenseWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DetailSubtotals(BaseModel):
    recurring_monthly: Decimal
    loan_balance: Decimal | None
    loan_monthly_payments: Decimal | None
    planned_estimated: Decimal
    planned_reserved: Decimal | None


class FinancialDetailsRead(BaseModel):
    income_pattern: Literal["stable", "variable", "mixed"] | None
    guaranteed_monthly_income: Decimal | None
    recurring_expenses: list[RecurringExpenseRead]
    loans: list[LoanRead]
    planned_expenses: list[PlannedExpenseRead]
    subtotals: DetailSubtotals
