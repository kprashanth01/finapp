"""Loan preparation uses observed months and never invents lender policies."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.loan_readiness_schemas import LoanCriterion, LoanPreviewWrite, LoanScenarioWrite
from app.services.loan_readiness import assess_loan, loan_emi, preview_loan
from app.services.loan_readiness_chat import answer_loan_question


def case():
    user = SimpleNamespace(monthly_income=Decimal('27000'))
    profile = SimpleNamespace(
        monthly_expenses=Decimal('21000'), savings=Decimal('25000'),
        existing_debt=Decimal('60000'), emergency_fund=Decimal('25000'),
        monthly_savings_contribution=None, monthly_debt_payments=Decimal('3000'),
        guaranteed_monthly_income=None, income_pattern='variable',
        risk_tolerance='moderate', investment_horizon_years=5, financial_goal=None,
    )
    incomes = ['40000', '18000', '32000', '12000', '27000']
    months = [SimpleNamespace(period=date(2026, at, 1), monthly_income=Decimal(amount),
                              monthly_expenses=Decimal('21000'), fixed_expenses=Decimal('17000'),
                              scheduled_emi=Decimal('3000'), paid_emi=Decimal('3000'))
              for at, amount in zip(range(5, 10), incomes)]
    expenses = [SimpleNamespace(name=name, monthly_amount=Decimal(amount), category=category)
                for name, amount, category in [
                    ('Rent', '8000', 'essential_fixed'), ('Food', '5000', 'essential_variable'),
                    ('Subscriptions', '1000', 'discretionary'),
                    ('Other essentials', '4000', 'essential_variable'),
                ]]
    scenario = LoanScenarioWrite(name='Work vehicle', loan_type='vehicle', amount='200000',
                                 annual_interest_rate_percent='12', tenure_months=24)
    return user, profile, months, expenses, scenario


def assess(**changes):
    user, profile, months, expenses, scenario = case()
    scenario = scenario.model_copy(update=changes)
    return assess_loan(user, profile, scenario, months=months, expenses=expenses,
                       as_of_date=date(2026, 10, 3))


def test_emi_and_variable_income_capacity_use_actual_low_month():
    result = assess()
    assert loan_emi(Decimal('200000'), Decimal('12'), 24) == Decimal('9414.69')
    assert result.estimated_emi == Decimal('9414.69')
    assert result.income.average == Decimal('25800.00')
    assert result.income.median == Decimal('27000.00')
    assert result.income.minimum == Decimal('12000')
    assert result.income.maximum == Decimal('40000')
    assert result.low_income_month.remaining_before_savings == Decimal('-18414.69')
    assert result.low_income_month.remaining_after_savings is None
    assert result.recorded_months[0].remaining_before_savings == Decimal('9585.31')
    assert result.reserve_coverage_months == Decimal('1.19')
    assert any(item.key == 'repayment_capacity' and item.status == 'NOT_MET'
               for item in result.requirements)
    assert any(item.key == 'reserve' and item.status == 'NEEDS_IMPROVEMENT'
               for item in result.priority_actions)
    assert any(item.key == 'income_stability' and item.status == 'NEEDS_IMPROVEMENT'
               for item in result.requirements)
    assert any(item.key == 'cash_flow_stability' and item.status == 'NEEDS_IMPROVEMENT'
               for item in result.requirements)
    assert not any(item.source_type == 'user_entered' for item in result.requirements)


def test_missing_rate_and_credit_are_unknown_not_zero_or_fake_approval():
    result = assess(annual_interest_rate_percent=None)
    assert result.estimated_emi is None
    assert result.current_month.remaining_before_savings is None
    assert any(item.key == 'repayment_capacity' and item.status == 'UNKNOWN'
               for item in result.requirements)
    assert any(item.key == 'credit_information' and item.status == 'UNKNOWN'
               for item in result.requirements)
    assert 'approval' not in result.summary.lower()


def test_user_entered_criteria_keep_source_and_missing_credit_unknown():
    criteria = [LoanCriterion(kind='minimum_history_months', value=6,
                              source_name='Offer sheet provided by user'),
                LoanCriterion(kind='minimum_credit_score', value=700,
                              source_name='Offer sheet provided by user')]
    result = assess(criteria=criteria)
    history = next(item for item in result.requirements if item.key == 'minimum_history_months')
    credit = next(item for item in result.requirements if item.key == 'minimum_credit_score')
    assert history.status == 'NOT_MET'
    assert history.current_value == '5 months'
    assert history.source_type == 'user_entered'
    assert 'Offer sheet provided by user' in history.source_label
    assert 'unverified' in history.source_label.lower()
    assert credit.status == 'UNKNOWN'
    assert credit.current_value is None


def test_income_and_one_time_previews_do_not_rewrite_history_or_reserve():
    user, profile, months, expenses, scenario = case()
    lower = preview_loan(user, profile, scenario, LoanPreviewWrite(income_next_month='12000'),
                         months=months, expenses=expenses, as_of_date=date(2026, 10, 3))
    assert lower.after.current_month.remaining_before_savings == Decimal('-18414.69')
    assert lower.after.income.observed_months == 5
    assert lower.after.reserve_coverage_months == lower.before.reserve_coverage_months
    assert user.monthly_income == Decimal('27000')
    extra = preview_loan(user, profile, scenario, LoanPreviewWrite(one_time_extra='20000'),
                         months=months, expenses=expenses, as_of_date=date(2026, 10, 3))
    assert extra.one_time_cash_after_expenses_and_emi == Decimal('16585.31')
    assert extra.after.current_month.income == extra.before.current_month.income
    assert extra.priority_advice


def test_chat_understands_a_one_time_payment_without_the_word_income():
    user, profile, months, expenses, scenario = case()
    assessment = assess_loan(user, profile, scenario, months=months, expenses=expenses,
                             as_of_date=date(2026, 10, 3))
    reply = answer_loan_question('I received ₹20,000 extra this month. What should I do?',
                                 assessment, scenario, user=user, profile=profile,
                                 months=months, expenses=expenses, as_of_date=date(2026, 10, 3))
    assert reply.preview.one_time_extra == Decimal('20000')
    assert '16,585.31' in reply.answer
    assert '3,414.69 gross cash shortfall' in reply.answer
    assert 'reserve gap' in reply.answer
    assert reply.assessment.reserve_coverage_months == assessment.reserve_coverage_months
