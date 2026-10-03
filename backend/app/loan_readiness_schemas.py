"""Contracts for user-entered loan preparation, never an approval decision."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.schemas import Money


RequirementKind = Literal[
    'minimum_history_months', 'minimum_monthly_income', 'maximum_debt_service_percent',
    'minimum_reserve_months', 'minimum_credit_score', 'maximum_credit_utilization_percent',
    'income_documents_required', 'maximum_missed_payments',
]
RequirementStatus = Literal['MET', 'NEEDS_IMPROVEMENT', 'NOT_MET', 'UNKNOWN']


class LoanCriterion(BaseModel):
    """A criterion entered by the user; a named lender is not proof of verification."""

    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    kind: RequirementKind
    value: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: HttpUrl | None = None


class LoanScenarioWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    loan_type: str = Field(min_length=1, max_length=60)
    lender_name: str | None = Field(default=None, max_length=100)
    amount: Money = Field(gt=0)
    annual_interest_rate_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    tenure_months: int = Field(ge=1, le=480)
    quoted_monthly_payment: Money | None = Field(default=None, gt=0)
    credit_score: int | None = Field(default=None, ge=0, le=1000)
    credit_history_months: int | None = Field(default=None, ge=0, le=1200)
    credit_utilization_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    income_documents_ready: bool | None = None
    missed_payments_last_12_months: int | None = Field(default=None, ge=0, le=12)
    criteria: list[LoanCriterion] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def unique_criteria(self):
        kinds = [item.kind for item in self.criteria]
        if len(kinds) != len(set(kinds)):
            raise ValueError('Enter each loan criterion only once.')
        if any(item.kind == 'income_documents_required' and item.value not in (0, 1) for item in self.criteria):
            raise ValueError('Income document requirement must be 0 or 1.')
        return self


class LoanScenarioRead(LoanScenarioWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    updated_at: datetime


class IncomeSummary(BaseModel):
    observed_months: int
    first_period: date | None
    latest_period: date | None
    average: Decimal | None
    median: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None
    variability_percent: Decimal | None
    latest_change: Decimal | None
    pattern: str | None


class CapacityPoint(BaseModel):
    label: str
    period: date | None = None
    income: Decimal
    total_expenses_including_existing_emi: Decimal
    existing_emi_included: Decimal | None
    planned_savings: Decimal | None
    proposed_emi: Decimal | None
    remaining_before_savings: Decimal | None
    remaining_after_savings: Decimal | None


class RequirementResult(BaseModel):
    key: str
    name: str
    current_value: str | None
    required_value: str | None
    status: RequirementStatus
    priority: int = Field(ge=1, le=9)
    source_type: Literal['illustrative_project', 'user_entered']
    source_label: str
    explanation: str
    action: str | None


class ReadinessAssessment(BaseModel):
    scenario_id: int | None
    evaluated_at: datetime
    as_of_date: date
    input_fingerprint: str
    summary: str
    estimated_emi: Decimal | None
    rate_based_emi: Decimal | None
    emi_source: Literal['calculated', 'entered_quote', 'missing']
    total_repayment: Decimal | None
    income: IncomeSummary
    current_month: CapacityPoint | None
    typical_month: CapacityPoint | None
    low_income_month: CapacityPoint | None
    recorded_months: list[CapacityPoint]
    reserve_coverage_months: Decimal | None
    reserve_gap: Decimal
    known_essential_expenses: Decimal
    known_discretionary_expenses: Decimal
    unclassified_expenses: Decimal | None
    existing_debt: Decimal
    existing_monthly_emi: Decimal | None
    requirements: list[RequirementResult]
    priority_actions: list[RequirementResult]
    goal_monthly_needs: list[dict]
    agent_findings: list[dict]
    assumptions: list[str]
    changes_since_previous: list[str] = []


class LoanPreviewWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    income_next_month: Money | None = None
    one_time_extra: Money | None = None
    amount: Money | None = Field(default=None, gt=0)
    annual_interest_rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    tenure_months: int | None = Field(default=None, ge=1, le=480)


class LoanPreviewRead(BaseModel):
    before: ReadinessAssessment
    after: ReadinessAssessment
    one_time_extra: Decimal | None
    one_time_cash_after_expenses_and_emi: Decimal | None
    priority_advice: list[str]
    explanation: str


class LoanChatQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=500, pattern=r'\S')


class LoanChatAnswer(BaseModel):
    answer: str
    evidence: list[RequirementResult]
    assessment: ReadinessAssessment | None = None
    preview: LoanPreviewRead | None = None
