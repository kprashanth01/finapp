"""Read-only comparison of a saved profile with one hypothetical month."""

from datetime import date
from types import SimpleNamespace
from typing import Sequence

from pydantic import BaseModel

from app.advisory.planning_types import AdvisoryResultV2
from app.advisory.service import run_advisory
from app.models import FinancialGoal, FinancialProfile, User
from app.schemas import ProfileWrite, ScenarioWrite


class ScenarioPreview(BaseModel):
    baseline: AdvisoryResultV2
    scenario: AdvisoryResultV2


def preview_scenario(user: User, profile: FinancialProfile, goals: Sequence[FinancialGoal],
                     as_of_date: date, changes: ScenarioWrite) -> ScenarioPreview:
    hypothetical_user = SimpleNamespace(monthly_income=changes.monthly_income)
    values = ProfileWrite.model_validate(profile, from_attributes=True).model_dump()
    values.update(monthly_expenses=changes.monthly_expenses,
                  monthly_savings_contribution=changes.monthly_savings_contribution)
    hypothetical_profile = SimpleNamespace(**values)
    return ScenarioPreview(
        baseline=run_advisory(user, profile, goals, as_of_date),
        scenario=run_advisory(hypothetical_user, hypothetical_profile, goals, as_of_date),
    )
