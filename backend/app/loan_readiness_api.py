"""Account-owned proposed loans, fresh assessments, and read-only previews."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisory.service import planning_date
from app.auth_dependencies import require_owner
from app.database import get_session
from app.loan_readiness_schemas import (LoanChatAnswer, LoanChatQuestion, LoanPreviewRead,
                                         LoanPreviewWrite, LoanScenarioRead, LoanScenarioWrite,
                                         ReadinessAssessment)
from app.models import (FinancialGoal, FinancialMonth, FinancialProfile, Loan, LoanReadinessSnapshot,
                        LoanScenario, PlannedExpense, RecurringExpense, User)
from app.services.loan_readiness import assess_loan, preview_loan
from app.services.loan_readiness_chat import answer_loan_question


router = APIRouter(prefix='/users/{user_id}/loan-readiness', tags=['loan-readiness'],
                   dependencies=[Depends(require_owner)])


def _scenario(session: Session, user_id: int, scenario_id: int) -> LoanScenario:
    row = session.scalar(select(LoanScenario).where(LoanScenario.id == scenario_id,
                                                    LoanScenario.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail='Loan scenario not found for this account.')
    return row


def _inputs(session: Session, user_id: int):
    user = session.get(User, user_id)
    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if user is None or profile is None:
        raise HTTPException(status_code=404, detail='Save a financial profile before assessing a loan.')
    def rows(model):
        return list(session.scalars(select(model).where(model.user_id == user_id).order_by(model.id)))
    return user, profile, dict(months=rows(FinancialMonth), expenses=rows(RecurringExpense),
                               loans=rows(Loan), goals=[goal for goal in rows(FinancialGoal) if not goal.archived],
                               plans=rows(PlannedExpense))


def _changes(before: ReadinessAssessment, after: ReadinessAssessment) -> list[str]:
    changes = []
    comparisons = [
        ('Proposed EMI', before.estimated_emi, after.estimated_emi),
        ('Current gross room after the proposed EMI',
         before.current_month.remaining_before_savings, after.current_month.remaining_before_savings),
        ('Current gross income', before.current_month.income, after.current_month.income),
        ('Current monthly expenses', before.current_month.total_expenses_including_existing_emi,
         after.current_month.total_expenses_including_existing_emi),
        ('Existing monthly debt payments', before.existing_monthly_emi, after.existing_monthly_emi),
        ('Existing debt balance', before.existing_debt, after.existing_debt),
        ('Lowest-income gross room',
         before.low_income_month.remaining_before_savings if before.low_income_month else None,
         after.low_income_month.remaining_before_savings if after.low_income_month else None),
        ('Emergency reserve coverage', before.reserve_coverage_months, after.reserve_coverage_months),
        ('Emergency reserve gap', before.reserve_gap, after.reserve_gap),
        ('Recorded income months', before.income.observed_months, after.income.observed_months),
        ('Average recorded income', before.income.average, after.income.average),
        ('Lowest recorded income', before.income.minimum, after.income.minimum),
    ]
    for label, old, new in comparisons:
        if old != new:
            changes.append(f'{label} changed from {old if old is not None else "unknown"} to {new if new is not None else "unknown"}')
    old_results = {item.key: item for item in before.requirements}
    for item in after.requirements:
        old = old_results.get(item.key)
        if old is None:
            changes.append(f'{item.name} was added to the review')
        elif old.status != item.status:
            changes.append(f'{item.name} changed from {old.status} to {item.status}')
        elif old.current_value != item.current_value or old.required_value != item.required_value:
            changes.append(f'{item.name} comparison changed')
    if not changes:
        changes.append('A saved input or proposed-loan detail changed; the displayed key figures and statuses stayed the same')
    return changes[:12]


def _assess_and_snapshot(session: Session, user_id: int, row: LoanScenario) -> ReadinessAssessment:
    user, profile, context = _inputs(session, user_id)
    result = assess_loan(user, profile, LoanScenarioRead.model_validate(row),
                         as_of_date=planning_date(), **context)
    latest = session.scalar(select(LoanReadinessSnapshot).where(LoanReadinessSnapshot.scenario_id == row.id)
                            .order_by(LoanReadinessSnapshot.id.desc()).limit(1))
    if latest is not None and latest.input_fingerprint == result.input_fingerprint:
        result.changes_since_previous = latest.result_payload.get('changes_since_previous', [])
        return result
    if latest is not None:
        result.changes_since_previous = _changes(ReadinessAssessment.model_validate(latest.result_payload), result)
    session.add(LoanReadinessSnapshot(scenario_id=row.id, input_fingerprint=result.input_fingerprint,
                                      result_payload=result.model_dump(mode='json'),
                                      evaluated_at=result.evaluated_at))
    session.commit()
    return result


@router.get('/scenarios', response_model=list[LoanScenarioRead])
def list_scenarios(user_id: int, session: Session = Depends(get_session)):
    return list(session.scalars(select(LoanScenario).where(LoanScenario.user_id == user_id)
                                .order_by(LoanScenario.id.desc())))


@router.post('/scenarios', response_model=LoanScenarioRead, status_code=201)
def create_scenario(user_id: int, payload: LoanScenarioWrite, session: Session = Depends(get_session)):
    _inputs(session, user_id)
    values = payload.model_dump(exclude={'criteria'})
    row = LoanScenario(user_id=user_id, **values,
                       criteria=[item.model_dump(mode='json') for item in payload.criteria])
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get('/scenarios/{scenario_id}', response_model=LoanScenarioRead)
def get_scenario(user_id: int, scenario_id: int, session: Session = Depends(get_session)):
    return _scenario(session, user_id, scenario_id)


@router.put('/scenarios/{scenario_id}', response_model=LoanScenarioRead)
def update_scenario(user_id: int, scenario_id: int, payload: LoanScenarioWrite,
                    session: Session = Depends(get_session)):
    row = _scenario(session, user_id, scenario_id)
    for key, value in payload.model_dump(exclude={'criteria'}).items():
        setattr(row, key, value)
    row.criteria = [item.model_dump(mode='json') for item in payload.criteria]
    session.commit()
    session.refresh(row)
    return row


@router.delete('/scenarios/{scenario_id}', status_code=204)
def delete_scenario(user_id: int, scenario_id: int, session: Session = Depends(get_session)):
    session.delete(_scenario(session, user_id, scenario_id))
    session.commit()


@router.post('/scenarios/{scenario_id}/assess', response_model=ReadinessAssessment)
def assess_scenario(user_id: int, scenario_id: int, session: Session = Depends(get_session)):
    return _assess_and_snapshot(session, user_id, _scenario(session, user_id, scenario_id))


@router.post('/scenarios/{scenario_id}/preview', response_model=LoanPreviewRead)
def preview_scenario(user_id: int, scenario_id: int, payload: LoanPreviewWrite,
                     session: Session = Depends(get_session)):
    row = _scenario(session, user_id, scenario_id)
    user, profile, context = _inputs(session, user_id)
    return preview_loan(user, profile, LoanScenarioRead.model_validate(row), payload,
                        as_of_date=planning_date(), **context)


@router.post('/scenarios/{scenario_id}/chat', response_model=LoanChatAnswer)
def chat_about_loan(user_id: int, scenario_id: int, payload: LoanChatQuestion,
                    session: Session = Depends(get_session)):
    row = _scenario(session, user_id, scenario_id)
    assessment = _assess_and_snapshot(session, user_id, row)
    user, profile, context = _inputs(session, user_id)
    return answer_loan_question(payload.question, assessment, LoanScenarioRead.model_validate(row),
                                user=user, profile=profile, as_of_date=planning_date(), **context)
