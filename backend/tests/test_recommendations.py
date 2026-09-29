from decimal import Decimal as D
import pytest
from test_planning_agents import state, goal
from app.advisory.orchestrator import RuleBasedOrchestrator
from app.advisory.registry import AgentRegistry
from app.advisory.recommendations import RecommendationEngine


def run(s):
    return RuleBasedOrchestrator().run(s, AgentRegistry.default())


def test_reserve_first_and_competing_goals():
    result = run(state([goal()],emergency_fund=D('4000')))
    plan = result.advice.monthly_plan
    assert plan.emergency_allocation == D('500')
    assert plan.goal_allocations[0].allocated_monthly == 0
    assert plan.goal_allocations[0].funding_gap == D('500')
    competing = run(state([goal(id=2,amount='4800',priority='low'),goal(amount='4800',priority='high')])).advice
    assert [a.allocated_monthly for a in competing.monthly_plan.goal_allocations] == [D(400),D(100)]
    assert competing.investment.status == 'deferred'
    assert competing.investment.category is None


@pytest.mark.parametrize('changes,hold', [
    ({'monthly_debt_payments':D(1000),'existing_debt':D(10000)},'debt'),
    ({'monthly_debt_payments':None,'existing_debt':D(10000)},'debt'),
    ({'monthly_expenses':D(0)},'expenses'),
])
def test_hold_preserves_budget(changes,hold):
    plan=run(state([goal()],**changes)).advice.monthly_plan
    assert hold in plan.hold_reason.lower()
    assert plan.unassigned == D(500)
    assert plan.goal_allocations[0].allocated_monthly == 0


@pytest.mark.parametrize('capacity', [None,D(0),D('.01'),D('500'),D('9999999999.99')])
def test_conservation_and_resolvable_evidence(capacity):
    result=run(state([goal(amount='9999999999.99',days=1),goal(id=2,amount='9999999999.99',days=1)],monthly_savings_contribution=capacity))
    plan=result.advice.monthly_plan
    if capacity is None:
        assert plan.unassigned is None and plan.emergency_allocation is None
        assert all(a.allocated_monthly is None for a in plan.goal_allocations)
    else:
        assert plan.emergency_allocation + sum(a.allocated_monthly for a in plan.goal_allocations) + plan.unassigned == capacity
        assert plan.unassigned >= 0
    valid={(r.agent_id,f.code) for r in result.agent_results for f in r.findings}
    references=[ref for action in result.advice.priority_actions for ref in action.source_refs]
    references += [ref for a in plan.goal_allocations for ref in a.source_refs]
    references += result.advice.investment.source_refs
    assert references and all((r.agent_id,r.finding_code) in valid for r in references)


def test_overdue_completed_archived_and_tie_order():
    archived=goal(id=5); archived.archived=True
    advice=run(state([goal(id=3),goal(id=2),goal(id=1,days=-1),goal(id=4,saved='7000'),archived])).advice
    assert [a.requirement.goal.id for a in advice.monthly_plan.goal_allocations] == [1,2,3,4]
    assert advice.monthly_plan.goal_allocations[0].status == 'overdue'
    assert advice.monthly_plan.goal_allocations[-1].status == 'completed'
    assert advice.investment.status == 'deferred'
    assert run(state([goal(saved='7000')])).advice.investment.status == 'ready_to_consider'


def test_exact_debt_boundary_uses_unrounded_amounts():
    assert run(state(monthly_debt_payments=D('999.99'))).advice.monthly_plan.hold_reason is None
    assert run(state(monthly_debt_payments=D('1000'))).advice.monthly_plan.hold_reason is not None


@pytest.mark.parametrize('changes,field', [({'monthly_savings_contribution':D(0)},'monthly_savings_contribution'),
                                        ({'investment_horizon_years':0},'investment_horizon_years')])
def test_zero_readiness_blocker_has_actionable_summary(changes,field):
    advice=run(state(**changes)).advice
    assert advice.summary.title != 'Your monthly plan is ready'
    assert advice.summary.next_action.field == field
