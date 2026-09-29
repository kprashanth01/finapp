"""Pure planning from persisted inputs; the caller captures one UTC date per request."""
from datetime import date, datetime, timezone
from collections.abc import Sequence
from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.registry import AgentRegistry
from app.advisory.state import PlanningState, build_planning_state
from app.advisory.planning_types import AdvisoryResultV2
from app.models import FinancialGoal, FinancialProfile, User
from app.services.financial_analysis import FinancialAnalysisService


def planning_date() -> date:
    return datetime.now(timezone.utc).date()


def financial_state(user: User, profile: FinancialProfile, goals: Sequence[FinancialGoal], as_of_date: date) -> PlanningState:
    return build_planning_state(user,profile,FinancialAnalysisService.analyze(user,profile),goals,as_of_date)


def run_advisory(user: User, profile: FinancialProfile, goals: Sequence[FinancialGoal], as_of_date: date) -> AdvisoryResultV2:
    return RuleBasedOrchestrator().run(financial_state(user,profile,goals,as_of_date),AgentRegistry.default())
