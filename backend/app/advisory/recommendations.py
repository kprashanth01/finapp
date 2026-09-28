"""Only promote findings actually returned by a selected agent."""

from app.advisory.rules import PRIORITY_ORDER
from app.advisory.types import AgentResult, PriorityAction


def priority_actions(results: list[AgentResult]) -> list[PriorityAction]:
    actions = [
        PriorityAction(
            code=f"review_{result.agent_id}",
            title=finding.title,
            reason=finding.reason,
            agent_id=result.agent_id,
            finding_code=finding.code,
            evidence=finding.evidence,
            limitations=finding.limitations,
        )
        for result in results
        for finding in result.findings
        if finding.priority
    ]
    return sorted(actions, key=lambda action: PRIORITY_ORDER[action.agent_id])
