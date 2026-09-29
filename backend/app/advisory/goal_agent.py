from decimal import Decimal, ROUND_CEILING
from app.advisory.planning_types import GoalFacts, GoalRequirement, PlanningAgentResult
from app.advisory.rules import GOAL_PRIORITY_ORDER, PLANNING_MONTH_DAYS
from app.advisory.state import PlanningState
from app.advisory.types import Evidence, Finding


class GoalPlanningAgent:
    agent_id = 'goal'

    def analyze(self, state: PlanningState) -> PlanningAgentResult:
        requirements, findings = [], []
        for goal in sorted(state.goals, key=lambda g: (GOAL_PRIORITY_ORDER[g.priority], g.target_date, g.id)):
            remaining = max(Decimal(0), goal.target_amount - goal.saved_amount)
            days = (goal.target_date - state.as_of_date).days
            status = 'completed' if remaining == 0 else 'overdue' if days <= 0 else 'future'
            months = (days + PLANNING_MONTH_DAYS - 1) // PLANNING_MONTH_DAYS if status == 'future' else None
            required = (remaining / months).quantize(Decimal('.01'), rounding=ROUND_CEILING) if months else Decimal(0) if status == 'completed' else None
            requirements.append(GoalRequirement(goal=goal, remaining_amount=remaining, approximate_months=months,
                                                required_monthly=required, status=status))
            findings.append(Finding(code=f'goal_{goal.id}', title=goal.name,
                reason='Target reached.' if status == 'completed' else 'Revise this overdue target date.' if status == 'overdue' else f'Remaining balance spread over approximately {months} months.',
                priority=status == 'overdue', evidence=[Evidence(label='Remaining target',value=remaining,unit='currency'),
                Evidence(label='Required each month',value=required,unit='currency')],
                limitations=['Uses 30-day months, no interest or investment growth.']))
        return PlanningAgentResult(agent_id=self.agent_id,status='ok',findings=findings,limitations=[],facts=GoalFacts(requirements=requirements))
