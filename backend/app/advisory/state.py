"""Snapshot of saved financial inputs, with no contact information."""

import hashlib
import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import FinancialProfile, User
from app.schemas import AnalysisRead


class FinancialState(BaseModel):
    model_config = ConfigDict(frozen=True)

    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_savings_contribution: Decimal | None
    monthly_debt_payments: Decimal | None
    existing_debt: Decimal
    emergency_fund: Decimal
    savings_rate_percent: Decimal | None
    debt_to_income_percent: Decimal | None
    expense_to_income_percent: Decimal | None
    emergency_fund_months: Decimal | None
    input_fingerprint: str

    @classmethod
    def from_saved(
        cls, user: User, profile: FinancialProfile, analysis: AnalysisRead
    ) -> "FinancialState":
        # Include every saved financial input so any profile edit calls for a new run.
        fingerprint_inputs = {
            "monthly_income": user.monthly_income,
            "monthly_expenses": profile.monthly_expenses,
            "savings": profile.savings,
            "existing_debt": profile.existing_debt,
            "emergency_fund": profile.emergency_fund,
            "monthly_savings_contribution": profile.monthly_savings_contribution,
            "monthly_debt_payments": profile.monthly_debt_payments,
            "risk_tolerance": profile.risk_tolerance,
            "financial_goal": profile.financial_goal,
            "investment_horizon_years": profile.investment_horizon_years,
        }
        canonical = json.dumps(
            {key: str(value) if isinstance(value, Decimal) else value for key, value in fingerprint_inputs.items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        return cls(
            monthly_income=user.monthly_income,
            monthly_expenses=profile.monthly_expenses,
            monthly_savings_contribution=profile.monthly_savings_contribution,
            monthly_debt_payments=profile.monthly_debt_payments,
            existing_debt=profile.existing_debt,
            emergency_fund=profile.emergency_fund,
            savings_rate_percent=analysis.savings_rate_percent,
            debt_to_income_percent=analysis.debt_to_income_percent,
            expense_to_income_percent=analysis.expense_to_income_percent,
            emergency_fund_months=analysis.emergency_fund_months,
            input_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def fingerprint(self) -> str:
        return self.input_fingerprint
