"""Build complete advisory results only from persisted user and profile data."""

from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.registry import AgentRegistry
from app.advisory.state import FinancialState
from app.advisory.types import AdvisoryResult
from app.models import FinancialProfile, User
from app.services.financial_analysis import FinancialAnalysisService


def financial_state(user: User, profile: FinancialProfile) -> FinancialState:
    analysis = FinancialAnalysisService.analyze(user, profile)
    return FinancialState.from_saved(user, profile, analysis)


def run_advisory(user: User, profile: FinancialProfile) -> AdvisoryResult:
    state = financial_state(user, profile)
    return RuleBasedOrchestrator().run(state, AgentRegistry.default())
