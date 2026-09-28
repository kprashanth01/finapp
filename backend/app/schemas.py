from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class UserCreate(BaseModel):
    name: Name
    email: EmailStr
    monthly_income: Money
    age: int | None = Field(default=None, ge=0, le=120)
    occupation: str | None = Field(default=None, max_length=100)


class UserRead(UserCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ProfileWrite(BaseModel):
    monthly_expenses: Money
    savings: Money
    existing_debt: Money
    emergency_fund: Money
    monthly_savings_contribution: Money | None = None
    monthly_debt_payments: Money | None = None
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    financial_goal: str | None = Field(default=None, max_length=200)
    investment_horizon_years: int | None = Field(default=None, ge=0, le=80)

    @model_validator(mode="after")
    def debt_payments_are_part_of_expenses(self):
        if self.monthly_debt_payments is not None and self.monthly_debt_payments > self.monthly_expenses:
            raise ValueError("Monthly debt payments cannot exceed total monthly expenses.")
        return self


class ProfileRead(ProfileWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


class AnalysisRead(BaseModel):
    savings_rate_percent: Decimal | None
    debt_to_income_percent: Decimal | None
    expense_to_income_percent: Decimal | None
    emergency_fund_months: Decimal | None
    health_score: int | None
