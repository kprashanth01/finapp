from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import FinancialProfile, User
from app.schemas import AnalysisRead, ProfileRead, ProfileWrite, UserCreate, UserRead
from app.services.financial_analysis import FinancialAnalysisService


router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> User:
    user = User(**payload.model_dump())
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email already has a user record.") from error
    session.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, payload: UserCreate, session: Session = Depends(get_session)
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    for field, value in payload.model_dump().items():
        setattr(user, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email already has a user record.") from error
    session.refresh(user)
    return user


@router.put("/users/{user_id}/financial-profile", response_model=ProfileRead)
def save_profile(
    user_id: int, payload: ProfileWrite, session: Session = Depends(get_session)
) -> FinancialProfile:
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        profile = FinancialProfile(user_id=user_id, **payload.model_dump())
        session.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)

    session.commit()
    session.refresh(profile)
    return profile


@router.get("/users/{user_id}/financial-profile", response_model=ProfileRead)
def get_profile(user_id: int, session: Session = Depends(get_session)) -> FinancialProfile:
    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found.")
    return profile


@router.get("/users/{user_id}/financial-analysis", response_model=AnalysisRead)
def get_financial_analysis(user_id: int, session: Session = Depends(get_session)) -> AnalysisRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found.")
    return FinancialAnalysisService.analyze(user, profile)
