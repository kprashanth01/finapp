"""Small, account-facing projection of two runs on the same planning state."""

from typing import Literal

from pydantic import BaseModel

from app.advisory.state import PlanningState
from app.rl.orchestration import ModelUnavailableError, run_orchestration


class FirstAction(BaseModel):
    title: str
    text: str


class ApproachResult(BaseModel):
    status: Literal['complete', 'partial', 'unavailable']
    as_of_date: str
    state_fingerprint: str
    selected_agents: list[str]
    missing_agents: list[str]
    first_action: FirstAction | None
    detail: str


class AdviceApproaches(BaseModel):
    source: Literal['saved_profile'] = 'saved_profile'
    as_of_date: str
    state_fingerprint: str
    rule_based: ApproachResult
    trained_rl: ApproachResult


def _project(result: dict) -> ApproachResult:
    complete = result['plan_readiness']['can_build_full_plan']
    summary = result['advice']['summary'] if complete else None
    actions = result['advice']['priority_actions'] if complete else []
    first = actions[0] if actions else None
    return ApproachResult(
        status='complete' if complete else 'partial',
        as_of_date=result['as_of_date'],
        state_fingerprint=result['state_fingerprint'],
        selected_agents=result['selected_agents'],
        missing_agents=result['plan_readiness']['missing_agents'],
        first_action=FirstAction(title=first['title'], text=first['reason']) if first else None,
        detail=summary['text'] if summary else result['summary']['text'],
    )


def compare_advice_approaches(state: PlanningState) -> AdviceApproaches:
    rule = _project(run_orchestration(state, mode='rule_based'))
    try:
        experimental = _project(run_orchestration(state, mode='trained_rl'))
    except ModelUnavailableError:
        experimental = ApproachResult(
            status='unavailable', as_of_date=rule.as_of_date,
            state_fingerprint=rule.state_fingerprint, selected_agents=[], missing_agents=[],
            first_action=None,
            detail='The optional trained model is unavailable on this server. The standard plan is still available.',
        )
    return AdviceApproaches(
        as_of_date=rule.as_of_date, state_fingerprint=rule.state_fingerprint,
        rule_based=rule, trained_rl=experimental,
    )
