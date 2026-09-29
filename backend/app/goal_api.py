from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.auth_dependencies import require_owner
from app.goal_schemas import GoalArchiveWrite, GoalRead, GoalWrite
from app.models import FinancialGoal, User

router = APIRouter(prefix="/users/{user_id}/goals", tags=["goals"], dependencies=[Depends(require_owner)])


def load_active_goals(session: Session, user_id: int) -> list[FinancialGoal]:
    return list(session.scalars(select(FinancialGoal).where(
        FinancialGoal.user_id == user_id, FinancialGoal.archived.is_(False)
    ).order_by(FinancialGoal.id)))


def _user(session: Session, user_id: int) -> None:
    if session.get(User, user_id) is None:
        raise HTTPException(404, "User not found.")


def _goal(session: Session, user_id: int, goal_id: int) -> FinancialGoal:
    row = session.scalar(select(FinancialGoal).where(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id))
    if row is None:
        raise HTTPException(404, "Goal not found.")
    return row


@router.get("", response_model=list[GoalRead])
def list_goals(user_id: int, include_archived: bool = False, session: Session = Depends(get_session)):
    _user(session, user_id)
    query = select(FinancialGoal).where(FinancialGoal.user_id == user_id)
    if not include_archived:
        query = query.where(FinancialGoal.archived.is_(False))
    return list(session.scalars(query.order_by(FinancialGoal.id)))


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(user_id: int, payload: GoalWrite, session: Session = Depends(get_session)):
    _user(session, user_id)
    row = FinancialGoal(user_id=user_id, **payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(user_id: int, goal_id: int, payload: GoalWrite, session: Session = Depends(get_session)):
    row = _goal(session, user_id, goal_id)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    session.commit()
    session.refresh(row)
    return row


@router.patch("/{goal_id}", response_model=GoalRead)
def archive_goal(user_id: int, goal_id: int, payload: GoalArchiveWrite, session: Session = Depends(get_session)):
    row = _goal(session, user_id, goal_id)
    row.archived = payload.archived
    session.commit()
    session.refresh(row)
    return row
