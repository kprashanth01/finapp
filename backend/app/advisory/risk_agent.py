from app.advisory.planning_types import PlanningAgentResult, RiskFacts
from app.advisory.rules import SHORT_HORIZON_YEARS, LONG_HORIZON_YEARS, HIGH_DTI_PERCENT, EMERGENCY_TARGET_MONTHS
from app.advisory.state import PlanningState
from app.advisory.types import Finding


def risk_category(state: PlanningState):
    horizon = state.investment_horizon_years
    if horizon is None:
        return None
    categories = ['conservative', 'moderate', 'aggressive']
    cap = 0 if horizon < SHORT_HORIZON_YEARS else 1 if horizon < LONG_HORIZON_YEARS else 2
    return categories[min(categories.index(state.risk_tolerance), cap)]


class RiskAssessmentAgent:
    agent_id = 'risk'

    def analyze(self, state: PlanningState) -> PlanningAgentResult:
        category = risk_category(state)
        factors = []
        if state.investment_horizon_years is None:
            factors.append('missing_horizon')
        elif category != state.risk_tolerance:
            factors.append('horizon_caps_preference')
        if state.monthly_expenses <= 0:
            factors.append('unknown_reserve')
        elif state.emergency_fund < state.monthly_expenses * EMERGENCY_TARGET_MONTHS:
            factors.append('reserve_gap')
        if state.monthly_savings_contribution is None:
            factors.append('missing_contribution')
        elif state.monthly_savings_contribution == 0:
            factors.append('zero_contribution')
        if state.existing_debt > 0 and state.debt_to_income_percent is None:
            factors.append('unknown_debt')
        elif state.monthly_income > 0 and (state.monthly_debt_payments or 0) * 100 / state.monthly_income >= HIGH_DTI_PERCENT:
            factors.append('high_debt')
        reason = ('Add an investment horizon to assess the stated preference.' if category is None else
                  f'Your {state.risk_tolerance} preference is capped at {category} for the saved horizon.')
        return PlanningAgentResult(agent_id=self.agent_id, status='limited' if category is None else 'ok',
            facts=RiskFacts(category=category,factor_codes=factors),
            findings=[Finding(code='risk_capacity', title='Risk preference and horizon',reason=reason,priority=False,
                              evidence=[], limitations=['Illustrative category; financial readiness is checked separately.'])],limitations=[])
