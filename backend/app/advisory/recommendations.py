"""Only promote findings actually returned by a selected agent."""

from app.advisory.rules import PRIORITY_ORDER
from app.advisory.types import AgentResult, PriorityAction
from decimal import Decimal
from app.advisory.planning_types import (
    CoordinatedAdvice, EvidenceRef, GoalAllocation, InvestmentAssessment,
    MonthlyPlan, NextAction, PlanAction, PlanSummary, PlanningAgentResult,
)
from app.advisory.state import PlanningState
from app.advisory.types import OrchestratorDecision


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


class RecommendationEngine:
    """Resolve competing findings into one conserved monthly savings budget."""

    def build(self, state: PlanningState, decision: OrchestratorDecision,
              results: list[PlanningAgentResult]) -> CoordinatedAdvice:
        by_id = {result.agent_id: result for result in results}

        def refs(agent_id, code=None):
            result = by_id[agent_id]
            return [EvidenceRef(agent_id=agent_id, finding_code=code or result.findings[0].code)]

        capacity = by_id['budget'].facts.capacity
        gap = by_id['emergency'].facts.gap
        debt = by_id.get('debt')
        hold = None
        if gap is None:
            hold = 'Add positive monthly expenses before assigning savings; reserve needs are unknown.'
        elif debt and debt.facts.review_required:
            hold = 'Review debt payments before assigning the remaining savings budget.'
        emergency = None if capacity is None else min(capacity, gap) if gap is not None else Decimal(0)
        remaining = None if capacity is None else capacity - emergency
        requirements = by_id['goal'].facts.requirements if 'goal' in by_id else []
        allocations = []
        for req in requirements:
            amount = None if capacity is None else Decimal(0)
            if req.status == 'future' and remaining is not None and hold is None:
                amount = min(req.required_monthly, req.remaining_amount, remaining)
                remaining -= amount
            funding_gap = None if req.required_monthly is None or amount is None else max(Decimal(0),req.required_monthly-amount)
            status = req.status if req.status != 'future' else 'missing_budget' if capacity is None else 'underfunded' if funding_gap > 0 else 'budget_covered'
            allocations.append(GoalAllocation(requirement=req, allocated_monthly=amount, funding_gap=funding_gap,
                                              status=status,source_refs=refs('goal',f'goal_{req.goal.id}')))
        investment = by_id['investment'].facts
        blocked_goals = [a for a in allocations if a.status in ('underfunded','overdue')]
        investment_status = 'deferred' if blocked_goals else investment.status
        reasons = list(investment.reasons)
        if blocked_goals:
            reasons.append('Resolve overdue or underfunded goals before considering investments.')
        investment_refs = refs('investment') + refs('risk') + [r for a in blocked_goals for r in a.source_refs]
        actions = []

        def action(code,title,reason,source_refs,view='profile',field=None,goal_id=None,limitations=()):
            actions.append(PlanAction(code=code,title=title,reason=reason,source_refs=source_refs,
                limitations=list(limitations), next_action=NextAction(view=view,field=field,goal_id=goal_id)))

        for agent_id,field in [('emergency','emergency_fund'),('debt','monthly_debt_payments'),('budget','monthly_expenses')]:
            if agent_id not in by_id:
                continue
            for finding in by_id[agent_id].findings:
                if finding.priority:
                    action(f'review_{agent_id}',finding.title,finding.reason,refs(agent_id,finding.code),field=field,limitations=finding.limitations)
        if gap is None:
            action('missing_expenses','Add monthly expenses',hold,refs('emergency'),field='monthly_expenses')
        if debt and debt.facts.reason_code == 'unknown_debt':
            action('missing_debt_inputs','Complete debt inputs','Debt burden cannot be assessed from the saved values.',refs('debt'),field='monthly_debt_payments' if state.monthly_debt_payments is None else 'monthly_income')
        if capacity is None:
            action('missing_contribution','Add a monthly savings budget','Enter your planned monthly savings contribution to allocate money.',refs('budget'),field='monthly_savings_contribution')
        for allocation in allocations:
            if allocation.status in ('underfunded','overdue'):
                req=allocation.requirement
                action(f'review_goal_{req.goal.id}', f'Review {req.goal.name}',
                       'The saved deadline has passed; choose a new date or update progress.' if allocation.status == 'overdue' else
                       f'The monthly plan is short by {allocation.funding_gap:,.2f} for this goal.',
                       allocation.source_refs,view='goals',goal_id=req.goal.id)
        if 'missing_horizon' in investment.factor_codes:
            action('missing_horizon','Add your investment horizon','A horizon is needed to assess investment readiness.',refs('investment'),field='investment_horizon_years')
        if state.monthly_income <= 0:
            action('income_required','Review monthly income','Positive income is required for ratio and readiness checks.',refs('investment'),field='monthly_income')
        summary = PlanSummary(
            title=actions[0].title if actions else 'Your monthly plan is ready',
            text=('Allocate the recorded savings budget once: reserve first, then goals in priority order.' if capacity is not None else
                  'Add your monthly savings contribution to see a funded plan.'),
            next_action=actions[0].next_action if actions else NextAction(view='goals'))
        return CoordinatedAdvice(summary=summary,
            monthly_plan=MonthlyPlan(capacity=capacity,emergency_allocation=emergency,goal_allocations=allocations,
                                     unassigned=remaining,hold_reason=hold),
            investment=InvestmentAssessment(status=investment_status,category=investment.category if investment_status == 'ready_to_consider' else None,
                                            reasons=reasons,source_refs=investment_refs),priority_actions=actions)
