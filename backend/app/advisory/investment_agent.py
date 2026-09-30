from app.advisory.planning_types import InvestmentFacts, PlanningAgentResult
from app.advisory.risk_agent import risk_category
from app.advisory.rules import EMERGENCY_TARGET_MONTHS, HIGH_DTI_PERCENT
from app.advisory.state import PlanningState
from app.advisory.dynamic import DynamicPlanningState, reserve_target_months
from app.advisory.types import Evidence, Finding


class InvestmentAgent:
    agent_id = 'investment'

    def analyze(self, state: PlanningState) -> PlanningAgentResult:
        if isinstance(state, DynamicPlanningState):
            return self._analyze_dynamic(state)
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

    def _analyze_dynamic(self, state: DynamicPlanningState) -> PlanningAgentResult:
        blockers, missing = [], []
        if state.monthly_income <= 0 or state.current_surplus <= 0:
            blockers.append(('no_current_surplus', 'No positive current surplus is available for investment consideration.'))
        if state.monthly_expenses <= 0:
            missing.append(('unknown_reserve', 'Positive scheduled expenses are needed to assess reserves.'))
        elif state.emergency_fund < state.monthly_expenses * reserve_target_months(state):
            blockers.append(('reserve_gap', 'The emergency reserve is below this month\'s illustrative target.'))
        if state.missed_payment:
            blockers.append(('missed_payment', 'A scheduled debt payment was missed.'))
        if state.existing_debt > 0 and state.debt_to_income_percent is None:
            missing.append(('unknown_debt', 'Positive current income is needed to assess debt burden.'))
        elif state.existing_debt > 0 and state.debt_to_income_percent >= HIGH_DTI_PERCENT:
            blockers.append(('high_debt', 'Scheduled EMI is at least 20% of current income.'))
        if state.observed_low_income or (state.recent_income_change_ratio is not None
                                         and state.recent_income_change_ratio <= -0.30):
            blockers.append(('income_instability', 'Current income is materially below recent or base income.'))
        if state.investment_horizon_years is None:
            missing.append(('missing_horizon', 'An investment horizon is needed.'))
        elif state.investment_horizon_years == 0:
            blockers.append(('zero_horizon', 'A positive investment horizon is required.'))
        status = 'deferred' if blockers else 'insufficient_information' if missing else 'ready_to_consider'
        reasons = [reason for _, reason in blockers + missing]
        return PlanningAgentResult(
            agent_id=self.agent_id, status='limited' if missing else 'ok',
            facts=InvestmentFacts(status=status,
                                  category=risk_category(state) if status == 'ready_to_consider' else None,
                                  factor_codes=[code for code, _ in blockers + missing], reasons=reasons),
            findings=[Finding(
                code='investment_prerequisites', title='Investment readiness',
                reason=' '.join(reasons) if reasons else 'Current income, reserve, debt and horizon checks passed.',
                priority=False,
                evidence=[Evidence(label='Current surplus', value=state.current_surplus, unit='currency'),
                          Evidence(label='Emergency fund coverage', value=state.emergency_fund_months, unit='months'),
                          Evidence(label='Reserve target', value=reserve_target_months(state), unit='months'),
                          Evidence(label='Outstanding debt', value=state.existing_debt, unit='currency'),
                          Evidence(label='Income volatility', value=state.income_volatility * 100, unit='%')],
                limitations=['No security selection, returns, suitability prediction, or tracked investment decision.'],
            )], limitations=[],
        )
