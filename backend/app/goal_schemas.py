from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import Money, Name


class GoalWrite(BaseModel):
    name: Name
    target_amount: Money = Field(gt=0)
    saved_amount: Money
    target_date: date
    priority: Literal["high", "medium", "low"]


class GoalRead(GoalWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class GoalArchiveWrite(BaseModel):
    archived: bool
