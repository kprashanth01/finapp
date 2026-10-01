from decimal import Decimal as D

from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.registry import AgentRegistry
from app.advisory.types import Finding
from test_planning_agents import goal, state


def run(**changes):
    profile = state([goal()], emergency_fund=D('4000'), existing_debt=D('10000'),
                    monthly_debt_payments=D('1000'), **changes)
    return RuleBasedOrchestrator().run(profile, AgentRegistry.default())


def test_all_six_saved_profile_agents_explain_impact_and_a_bounded_next_step():
    result = run()
    assert {item.agent_id for item in result.agent_results} == {
        'budget', 'debt', 'emergency', 'goal', 'risk', 'investment'
    }
    for agent in result.agent_results:
        assert agent.findings
        for finding in agent.findings:
            assert finding.impact and finding.impact.strip()
            assert finding.suggested_action and finding.suggested_action.strip()
    reserve = next(item for item in result.agent_results if item.agent_id == 'emergency')
    assert 'reserve' in reserve.findings[0].suggested_action.lower()
    debt = next(item for item in result.agent_results if item.agent_id == 'debt')
    assert 'required' in debt.findings[0].suggested_action.lower()
    for agent_id in ('risk', 'investment'):
        agent = next(item for item in result.agent_results if item.agent_id == agent_id)
        assert agent.findings[0].evidence


def test_missing_savings_contribution_requests_input_without_inventing_an_allocation():
    result = run(monthly_savings_contribution=None)
    budget = next(item for item in result.agent_results if item.agent_id == 'budget')
    assert 'contribution' in budget.findings[0].suggested_action.lower()
    assert result.advice.monthly_plan.capacity is None
    assert result.advice.monthly_plan.emergency_allocation is None


def test_older_findings_without_guidance_remain_readable():
    finding = Finding.model_validate({
        'code': 'old', 'title': 'Earlier finding', 'reason': 'Saved observation.',
        'priority': True, 'evidence': [], 'limitations': [],
    })
    assert finding.impact is None
    assert finding.suggested_action is None
