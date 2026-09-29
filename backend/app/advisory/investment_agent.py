from app.advisory.planning_types import InvestmentFacts, PlanningAgentResult
from app.advisory.risk_agent import risk_category
from app.advisory.rules import EMERGENCY_TARGET_MONTHS, HIGH_DTI_PERCENT
from app.advisory.state import PlanningState
from app.advisory.types import Finding


class InvestmentAgent:
    agent_id = 'investment'

    def analyze(self, state: PlanningState) -> PlanningAgentResult:
        blockers, missing = [], []
        if state.monthly_income <= 0:
            blockers.append(('zero_income','Positive monthly income is required.'))
        if state.monthly_savings_contribution is None:
            missing.append(('missing_contribution','Add your monthly savings contribution.'))
        elif state.monthly_savings_contribution <= 0:
            blockers.append(('zero_contribution','No monthly savings budget is available.'))
        if state.monthly_expenses <= 0:
            missing.append(('unknown_reserve','Add positive monthly expenses to assess the emergency reserve.'))
        elif state.emergency_fund < state.monthly_expenses * EMERGENCY_TARGET_MONTHS:
            blockers.append(('reserve_gap','The emergency reserve is below three months of expenses.'))
        debt_present = state.existing_debt > 0 or (state.monthly_debt_payments or 0) > 0
        if debt_present and state.debt_to_income_percent is None:
            missing.append(('unknown_debt','Add debt payments and positive income to assess debt burden.'))
        elif debt_present and state.monthly_debt_payments * 100 / state.monthly_income >= HIGH_DTI_PERCENT:
            blockers.append(('high_debt','Review debt payments at or above 20% of gross income.'))
        if state.investment_horizon_years is None:
            missing.append(('missing_horizon','Add an investment horizon.'))
        elif state.investment_horizon_years == 0:
            blockers.append(('zero_horizon','A positive investment horizon is required.'))
        status = 'deferred' if blockers else 'insufficient_information' if missing else 'ready_to_consider'
        reasons = [reason for _,reason in blockers+missing]
        return PlanningAgentResult(agent_id=self.agent_id,status='limited' if missing else 'ok',
            facts=InvestmentFacts(status=status,category=risk_category(state) if status == 'ready_to_consider' else None,
                                  factor_codes=[code for code,_ in blockers+missing],reasons=reasons),
            findings=[Finding(code='investment_prerequisites',title='Investment readiness',
                reason=' '.join(reasons) if reasons else 'Profile prerequisites met; the coordinator also checks goal funding.',
                priority=False,evidence=[],limitations=['No asset selection, returns, or suitability prediction.'])],limitations=[])
