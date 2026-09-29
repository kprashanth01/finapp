from typing import Protocol
from app.advisory.recommendations import RecommendationEngine
from app.advisory.explain import build_explanation
from app.advisory.registry import AgentRegistry
from app.advisory.rules import RULE_VERSION
from app.advisory.state import PlanningState
from app.advisory.planning_types import AdvisoryResultV2
from app.advisory.types import AgentSelection, OrchestratorDecision
from app.rl.selection import action_for


class Orchestrator(Protocol):
    def run(self, state: PlanningState, registry: AgentRegistry) -> AdvisoryResultV2: ...


class RuleBasedOrchestrator:
    def run(self, state: PlanningState, registry: AgentRegistry) -> AdvisoryResultV2:
        debt_relevant = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
        selections = [
            AgentSelection(agent_id='budget', selected=True, reason='Assess monthly ratios and the savings budget.'),
            AgentSelection(agent_id='debt', selected=debt_relevant,
                reason='Saved debt balance or payment is present.' if debt_relevant else 'No outstanding debt or positive payment is recorded.'),
            AgentSelection(agent_id='emergency', selected=True, reason='Assess reserve coverage before allocating savings.'),
            AgentSelection(agent_id='goal', selected=bool(state.goals), reason='Evaluate active goals.' if state.goals else 'No active goals recorded.'),
            AgentSelection(agent_id='risk', selected=True, reason='Compare stated preference with the investment horizon.'),
            AgentSelection(agent_id='investment', selected=True, reason='Check readiness prerequisites.'),
        ]
        decision = OrchestratorDecision(rule_version=RULE_VERSION, selections=selections)
        results = [registry.get(s.agent_id).analyze(state) for s in selections if s.selected]
        advice = RecommendationEngine().build(state,decision,results)
        action = action_for(item.agent_id for item in selections if item.selected)
        return AdvisoryResultV2(state=state,decision=decision,agent_results=results,
                                advice=advice,
                                explanation=build_explanation(state, decision, action, results, advice))
