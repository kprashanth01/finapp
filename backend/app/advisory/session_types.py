from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.advisory.types import AdvisoryResult
from app.advisory.planning_types import AdvisoryResultV2


class AdvisorySessionRead(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    method: str
    rule_version: str
    is_stale: bool
    stale_reasons: list[Literal['inputs', 'planning_date', 'rule_version']]
    result: AdvisoryResultV2 | AdvisoryResult


class AdvisorySessionSummary(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    method: str
    rule_version: str
    is_stale: bool
    stale_reasons: list[Literal['inputs', 'planning_date', 'rule_version']]
    priority_titles: list[str]
    priority_count: int


class AdvisoryHistoryPage(BaseModel):
    items: list[AdvisorySessionSummary]
    next_before_id: int | None


def get_priority_actions(result):
    return result.advice.priority_actions if isinstance(result, AdvisoryResultV2) else result.priority_actions
