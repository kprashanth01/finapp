from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.advisory.state import build_planning_state
from app.advisory.goal_agent import GoalPlanningAgent
from app.advisory.risk_agent import RiskAssessmentAgent
from app.advisory.investment_agent import InvestmentAgent
from app.services.financial_analysis import FinancialAnalysisService

TODAY = date(2026, 9, 29)


def goal(id=1, amount='6000', saved='0', days=360, priority='medium'):
    return SimpleNamespace(id=id, name=f'Goal {id}', target_amount=D(amount), saved_amount=D(saved),
                           target_date=TODAY + timedelta(days=days), priority=priority, archived=False)


def state(goals=(), as_of=TODAY, **changes):
    user = SimpleNamespace(monthly_income=D(changes.pop('income', '5000')))
    data = dict(monthly_expenses=D('3000'), savings=D('8000'), existing_debt=D('0'),
                emergency_fund=D('9000'), monthly_savings_contribution=D('500'),
                monthly_debt_payments=D('0'), risk_tolerance='aggressive',
                investment_horizon_years=7, financial_goal=None)
    data.update(changes)
    profile = SimpleNamespace(**data)
    return build_planning_state(user, profile, FinancialAnalysisService.analyze(user, profile), goals, as_of)


@pytest.mark.parametrize('amount,saved,days,status,months,required', [
    ('6000','0',360,'future',12,'500.00'), ('1','0',90,'future',3,'0.34'),
    ('6000','0',0,'overdue',None,None), ('6000','6000',-1,'completed',None,'0'),
    ('6000','7000',-1,'completed',None,'0'), ('6000','0',1,'future',1,'6000'),
    ('6000','0',30,'future',1,'6000'), ('6000','0',31,'future',2,'3000'),
])
def test_goal_requirements(amount, saved, days, status, months, required):
    result = GoalPlanningAgent().analyze(state([goal(amount=amount,saved=saved,days=days)]))
    req = result.facts.requirements[0]
    assert (req.status, req.approximate_months) == (status, months)
    assert req.required_monthly == (D(required) if required is not None else None)


@pytest.mark.parametrize('horizon,category', [(None,None),(0,'conservative'),(2,'conservative'),(3,'moderate'),(6,'moderate'),(7,'aggressive')])
def test_horizon_caps(horizon, category):
    assert RiskAssessmentAgent().analyze(state(investment_horizon_years=horizon)).facts.category == category


@pytest.mark.parametrize('changes,status', [({},'ready_to_consider'),
    ({'monthly_savings_contribution':None},'insufficient_information'),
    ({'monthly_savings_contribution':D(0)},'deferred'),
    ({'investment_horizon_years':None},'insufficient_information'),
    ({'investment_horizon_years':0},'deferred'),
    ({'existing_debt':D(100), 'monthly_debt_payments':None},'insufficient_information'),
    ({'emergency_fund':D(0), 'investment_horizon_years':None},'deferred')])
def test_investment_prerequisites(changes,status):
    assert InvestmentAgent().analyze(state(**changes)).facts.status == status


def test_fingerprint_and_immutable_snapshot():
    a,b = goal(),goal(id=2,amount='9999999999.99',days=1)
    first = state([a,b])
    assert first.fingerprint() == state([b,a],as_of=TODAY+timedelta(days=1)).fingerprint()
    a.target_amount = D('6000.00')
    assert first.fingerprint() == state([a,b]).fingerprint()
    a.saved_amount = D('1')
    assert first.fingerprint() != state([a,b]).fingerprint()
    assert first.goals[0].saved_amount == 0
    with pytest.raises(ValidationError):
        first.goals[0].name = 'Mutated'
    with pytest.raises(ValidationError):
        first.as_of_date = TODAY
    huge = GoalPlanningAgent().analyze(state([b,goal(id=3,amount='9999999999.99',days=1)]))
    assert sum(r.required_monthly for r in huge.facts.requirements) == D('19999999999.98')
