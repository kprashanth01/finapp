from decimal import Decimal, ROUND_CEILING
from app.advisory.planning_types import GoalFacts, GoalRequirement, PlanningAgentResult
from app.advisory.rules import GOAL_PRIORITY_ORDER, PLANNING_MONTH_DAYS
from app.advisory.state import PlanningState
from app.advisory.dynamic import DynamicPlanningState, reserve_target_months
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
            reason = ('Target reached.' if status == 'completed' else
                      'Revise this overdue target date.' if status == 'overdue' else
                      f'Remaining balance spread over approximately {months} months.')
            priority = status == 'overdue'
            evidence = [Evidence(label='Remaining target', value=remaining, unit='currency'),
                        Evidence(label='Required each month', value=required, unit='currency')]
            limitations = ['Uses 30-day months, no interest or investment growth.']
            if isinstance(state, DynamicPlanningState):
                evidence.append(Evidence(label='Current surplus', value=state.current_surplus, unit='currency'))
                evidence.append(Evidence(label='Income volatility', value=state.income_volatility * 100, unit='%'))
                reserve_gap = (state.monthly_expenses > 0 and
                               state.emergency_fund < reserve_target_months(state) * state.monthly_expenses)
                debt_pressure = state.missed_payment or state.net_cash_flow < 0 and state.existing_debt > 0
                if status == 'future' and (required > state.current_surplus or reserve_gap or debt_pressure):
                    priority = True
                    reason += ' Current surplus or competing reserve and debt needs may prevent this monthly amount.'
                limitations.append('Current surplus is a one-month estimate, not a committed goal contribution.')
            findings.append(Finding(code=f'goal_{goal.id}', title=goal.name,
                reason=reason, priority=priority, evidence=evidence, limitations=limitations))
        return PlanningAgentResult(agent_id=self.agent_id,status='ok',findings=findings,limitations=[],facts=GoalFacts(requirements=requirements))
