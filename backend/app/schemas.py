from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints


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
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    financial_goal: str | None = Field(default=None, max_length=200)
    investment_horizon_years: int | None = Field(default=None, ge=0, le=80)


class ProfileRead(ProfileWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
