from app.advisory.recommendations import priority_actions
from app.advisory.registry import AgentRegistry
from app.advisory.rules import RULE_VERSION
from app.advisory.state import FinancialState
from app.advisory.types import AdvisoryResult, AgentSelection, OrchestratorDecision


class RuleBasedOrchestrator:
    def run(self, state: FinancialState, registry: AgentRegistry) -> AdvisoryResult:
        debt_relevant = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
        selections = [
            AgentSelection(agent_id="budget", selected=True, reason="Budget ratios are relevant to every saved profile."),
            AgentSelection(
                agent_id="debt", selected=debt_relevant,
                reason="Saved debt balance or payment is present." if debt_relevant else "No outstanding debt or positive payment is recorded.",
            ),
            AgentSelection(agent_id="emergency", selected=True, reason="Emergency reserve coverage is relevant to every saved profile."),
        ]
        results = [registry.get(s.agent_id).analyze(state) for s in selections if s.selected]
        return AdvisoryResult(
            state=state,
            decision=OrchestratorDecision(rule_version=RULE_VERSION, selections=selections),
            agent_results=results,
            priority_actions=priority_actions(results),
        )
