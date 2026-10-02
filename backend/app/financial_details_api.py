"""Atomic edit of optional, account-owned financial detail."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_dependencies import require_owner
from app.database import get_session
from app.financial_detail_schemas import (
    DetailSubtotals, FinancialDetailsRead, FinancialDetailsWrite,
    LoanRead, PlannedExpenseRead, RecurringExpenseRead,
)
from app.models import FinancialProfile, Loan, PlannedExpense, RecurringExpense, User
from app.services.financial_details import validate_detail_totals


router = APIRouter(prefix="/users/{user_id}/financial-details", tags=["financial-details"],
                   dependencies=[Depends(require_owner)])


def _profile(session: Session, user_id: int, *, lock: bool = False) -> tuple[User, FinancialProfile]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    query = select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    profile = session.scalar(query.with_for_update() if lock else query)
    if profile is None:
        raise HTTPException(404, "Save a financial profile before adding details.")
    return user, profile


def _rows(session: Session, model, user_id: int):
    return list(session.scalars(select(model).where(model.user_id == user_id).order_by(model.id)))


def _snapshot(session: Session, user_id: int, profile: FinancialProfile) -> FinancialDetailsRead:
    expenses = _rows(session, RecurringExpense, user_id)
    loans = _rows(session, Loan, user_id)
    plans = _rows(session, PlannedExpense, user_id)
    def total(values):
        return sum(values, Decimal("0")).quantize(Decimal("0.01"))
    return FinancialDetailsRead(
        income_pattern=profile.income_pattern,
        guaranteed_monthly_income=profile.guaranteed_monthly_income,
        recurring_expenses=[RecurringExpenseRead.model_validate(row) for row in expenses],
        loans=[LoanRead.model_validate(row) for row in loans],
        planned_expenses=[PlannedExpenseRead.model_validate(row) for row in plans],
        subtotals=DetailSubtotals(
            recurring_monthly=total(row.monthly_amount for row in expenses),
            loan_balance=(None if any(row.remaining_balance is None for row in loans)
                          else total(row.remaining_balance for row in loans)),
            loan_monthly_payments=(None if any(row.monthly_payment is None for row in loans)
                                   else total(row.monthly_payment for row in loans)),
            planned_estimated=total(row.estimated_amount for row in plans),
            planned_reserved=(None if any(row.amount_reserved is None for row in plans)
                              else total(row.amount_reserved for row in plans)),
        ),
    )


def _replace(session: Session, user_id: int, model, items: list) -> None:
    existing = {row.id: row for row in _rows(session, model, user_id)}
    ids = [item.id for item in items if item.id is not None]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "The same detail ID was provided twice.")
    if any(identifier not in existing for identifier in ids):
        raise HTTPException(422, "A detail ID does not belong to this account.")
    for item in items:
        values = item.model_dump(exclude={"id"})
        if item.id is None:
            session.add(model(user_id=user_id, **values))
        else:
            for key, value in values.items():
                setattr(existing[item.id], key, value)
    for identifier, row in existing.items():
        if identifier not in ids:
            session.delete(row)


@router.get("", response_model=FinancialDetailsRead)
def get_financial_details(user_id: int, session: Session = Depends(get_session)) -> FinancialDetailsRead:
    _, profile = _profile(session, user_id)
    return _snapshot(session, user_id, profile)


@router.put("", response_model=FinancialDetailsRead)
def save_financial_details(user_id: int, payload: FinancialDetailsWrite,
                           session: Session = Depends(get_session)) -> FinancialDetailsRead:
    user, profile = _profile(session, user_id, lock=True)
    profile.income_pattern = payload.income_pattern
    profile.guaranteed_monthly_income = payload.guaranteed_monthly_income
    _replace(session, user_id, RecurringExpense, payload.recurring_expenses)
    _replace(session, user_id, Loan, payload.loans)
    _replace(session, user_id, PlannedExpense, payload.planned_expenses)
    session.flush()
    try:
        validate_detail_totals(user, profile, _rows(session, RecurringExpense, user_id),
                               _rows(session, Loan, user_id))
    except ValueError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error
    session.commit()
    return _snapshot(session, user_id, profile)
