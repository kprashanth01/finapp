from decimal import Decimal

from app.advisory.planning_types import PlanningAgentResult, RiskFacts
from app.advisory.rules import SHORT_HORIZON_YEARS, LONG_HORIZON_YEARS, HIGH_DTI_PERCENT, EMERGENCY_TARGET_MONTHS
from app.advisory.state import PlanningState
from app.advisory.dynamic import DynamicPlanningState, HIGH_INCOME_VOLATILITY, reserve_target_months
from app.advisory.types import Evidence, Finding


def risk_category(state: PlanningState):
    horizon = state.investment_horizon_years
    if horizon is None:
        return None
    categories = ['conservative', 'moderate', 'aggressive']
    cap = 0 if horizon < SHORT_HORIZON_YEARS else 1 if horizon < LONG_HORIZON_YEARS else 2
    if isinstance(state, DynamicPlanningState):
        unstable = state.observed_low_income or state.missed_payment or state.net_cash_flow < 0
        thin_reserve = (state.monthly_expenses > 0 and
                        state.emergency_fund < reserve_target_months(state) * state.monthly_expenses)
        if unstable or state.income_volatility >= HIGH_INCOME_VOLATILITY and thin_reserve:
            cap = 0
    return categories[min(categories.index(state.risk_tolerance), cap)]


class RiskAssessmentAgent:
    agent_id = 'risk'

    def analyze(self, state: PlanningState) -> PlanningAgentResult:
        if isinstance(state, DynamicPlanningState):
            return self._analyze_dynamic(state)
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

    def _analyze_dynamic(self, state: DynamicPlanningState) -> PlanningAgentResult:
        category = risk_category(state)
        factors = []
        if state.investment_horizon_years is None:
            factors.append('missing_horizon')
        elif state.investment_horizon_years < SHORT_HORIZON_YEARS:
            factors.append('short_horizon')
        if state.existing_debt > 0 and state.debt_to_income_percent is None:
            factors.append('unknown_debt')
        elif state.debt_to_income_percent is not None and state.debt_to_income_percent >= HIGH_DTI_PERCENT:
            factors.append('high_debt')
        if state.monthly_expenses <= 0:
            factors.append('unknown_reserve')
        elif state.emergency_fund < state.monthly_expenses * reserve_target_months(state):
            factors.append('reserve_gap')
        if state.current_surplus <= 0:
            factors.append('no_current_surplus')
        if (state.observed_low_income or state.missed_payment or state.net_cash_flow < 0
                or state.income_volatility >= HIGH_INCOME_VOLATILITY):
            factors.append('income_instability')
        if category is not None and category != state.risk_tolerance:
            factors.append('preference_capped')
        reason = ('Add an investment horizon to assess the stated preference.' if category is None else
                  f'The illustrative current risk category is {category}; stated preference is {state.risk_tolerance}.')
        return PlanningAgentResult(
            agent_id=self.agent_id, status='limited' if category is None else 'ok',
            facts=RiskFacts(category=category, factor_codes=factors),
            findings=[Finding(
                code='risk_capacity', title='Risk preference and current capacity',
                reason=reason, priority=False,
                evidence=[Evidence(label='Current surplus', value=state.current_surplus, unit='currency'),
                          Evidence(label='Emergency fund coverage', value=state.emergency_fund_months, unit='months'),
                          Evidence(label='Outstanding debt', value=state.existing_debt, unit='currency'),
                          Evidence(label='Income volatility', value=state.income_volatility * Decimal(100), unit='%'),
                          Evidence(label='Investment horizon', value=(Decimal(state.investment_horizon_years)
                                   if state.investment_horizon_years is not None else None), unit='years')],
                limitations=['Illustrative category based on current month; it is not an investment suitability assessment.'],
            )], limitations=[],
        )
