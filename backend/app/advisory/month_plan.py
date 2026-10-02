"""Read-only coordinated plan using one account-entered month and current goals."""

from datetime import date
from types import SimpleNamespace
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from app.advisory.planning_types import AdvisoryResultV2
from app.advisory.service import run_advisory
from app.models import FinancialGoal, FinancialMonth, FinancialProfile
from app.schemas import Money, ProfileWrite


class MonthPlanWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    monthly_savings_contribution: Money | None = None


class MonthPlanPreview(BaseModel):
    source_period: date
    result: AdvisoryResultV2


def preview_month_plan(month: FinancialMonth, profile: FinancialProfile,
                       goals: Sequence[FinancialGoal], as_of_date: date,
                       contribution: Money | None) -> MonthPlanPreview:
    values = ProfileWrite.model_validate(profile, from_attributes=True).model_dump()
    values.update(
        monthly_expenses=month.monthly_expenses,
        monthly_savings_contribution=contribution,
        monthly_debt_payments=month.scheduled_emi,
        savings=month.savings,
        emergency_fund=month.emergency_fund,
        existing_debt=month.outstanding_debt,
        risk_tolerance=month.risk_tolerance,
        investment_horizon_years=month.investment_horizon_years,
    )
    month_profile = SimpleNamespace(**values)
    month_user = SimpleNamespace(monthly_income=month.monthly_income)
    return MonthPlanPreview(source_period=month.period,
                            result=run_advisory(month_user, month_profile, goals, as_of_date))
