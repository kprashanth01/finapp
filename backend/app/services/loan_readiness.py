"""Deterministic loan preparation from owned, saved financial facts."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from types import SimpleNamespace
from typing import Sequence

from app.advisory.agents import BudgetAgent, DebtAgent, EmergencyAgent
from app.advisory.goal_agent import GoalPlanningAgent
from app.advisory.rules import EMERGENCY_TARGET_MONTHS, HIGH_DTI_PERCENT
from app.advisory.service import financial_state
from app.loan_readiness_schemas import (
    CapacityPoint, IncomeSummary, LoanCriterion, LoanPreviewRead, LoanPreviewWrite,
    LoanScenarioWrite, ReadinessAssessment, RequirementResult,
)
from app.models import FinancialGoal, FinancialMonth, FinancialProfile, Loan, PlannedExpense, RecurringExpense, User


CENT = Decimal('0.01')
ZERO = Decimal('0')
ILLUSTRATIVE = 'Illustrative project criterion — not a lender policy.'


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _label(value: Decimal | None, suffix: str = '') -> str | None:
    return None if value is None else f'{value:,.2f}{suffix}'


def loan_emi(amount: Decimal, annual_interest_rate_percent: Decimal, tenure_months: int) -> Decimal:
    """Fixed-rate, fully amortizing principal-and-interest payment, excluding fees."""
    if amount <= 0 or tenure_months < 1 or annual_interest_rate_percent < 0:
        raise ValueError('Loan amount, interest rate, or tenure is invalid.')
    monthly_rate = annual_interest_rate_percent / Decimal('1200')
    if monthly_rate == 0:
        return _money(amount / tenure_months)
    factor = (1 + monthly_rate) ** tenure_months
    return _money(amount * monthly_rate * factor / (factor - 1))


def _capacity(label: str, income: Decimal, expenses: Decimal, existing_emi: Decimal | None,
              savings: Decimal | None, proposed_emi: Decimal | None, period: date | None = None) -> CapacityPoint:
    before = _money(income - expenses - proposed_emi) if proposed_emi is not None else None
    after = _money(before - savings) if before is not None and savings is not None else None
    return CapacityPoint(label=label, period=period, income=income,
                         total_expenses_including_existing_emi=expenses,
                         existing_emi_included=existing_emi, planned_savings=savings,
                         proposed_emi=proposed_emi, remaining_before_savings=before,
                         remaining_after_savings=after)


def _input_fingerprint(scenario: LoanScenarioWrite, user: User, profile: FinancialProfile,
                       months: Sequence[FinancialMonth], expenses: Sequence[RecurringExpense],
                       loans: Sequence[Loan], goals: Sequence[FinancialGoal],
                       plans: Sequence[PlannedExpense], as_of_date: date) -> str:
    relevant = {
        'scenario': scenario.model_dump(mode='json'), 'as_of_date': as_of_date.isoformat(),
        'user_income': str(user.monthly_income),
        'profile': {key: str(getattr(profile, key, None)) for key in (
            'monthly_expenses', 'savings', 'existing_debt', 'emergency_fund',
            'monthly_savings_contribution', 'monthly_debt_payments', 'income_pattern',
            'guaranteed_monthly_income')},
        'months': [(str(row.period), str(row.monthly_income), str(row.monthly_expenses),
                    str(row.scheduled_emi), str(row.paid_emi)) for row in months],
        'expenses': [(row.name, str(row.monthly_amount), row.category) for row in expenses],
        'loans': [(row.name, str(row.remaining_balance), str(row.monthly_payment)) for row in loans],
        'goals': [(row.name, str(row.target_amount), str(row.saved_amount), str(row.target_date),
                   row.priority, row.archived) for row in goals],
        'planned_expenses': [(row.name, str(row.estimated_amount), str(row.amount_reserved),
                              str(row.due_date), row.is_essential) for row in plans],
    }
    return hashlib.sha256(json.dumps(relevant, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _criterion_result(criterion: LoanCriterion, *, income: IncomeSummary, current_income: Decimal,
                      emi: Decimal | None, existing_emi: Decimal | None, reserve_months: Decimal | None,
                      scenario: LoanScenarioWrite, missed: int | None) -> RequirementResult:
    key, limit = criterion.kind, criterion.value
    source = (f'User-entered from {criterion.source_name.strip()}; unverified lender information.'
              if criterion.source_name and criterion.source_name.strip() else
              'User-entered criterion; source not provided and not independently verified.')
    if criterion.source_url:
        source += f' {criterion.source_url}'
    values: dict[str, tuple[Decimal | None, str, str, bool]] = {
        'minimum_history_months': (Decimal(income.observed_months), 'months', 'Record more actual months in Months.', True),
        'minimum_monthly_income': (income.minimum, 'gross monthly income in the lowest recorded month',
                                   'Keep documented income history and check the lender definition of income.', True),
        'maximum_debt_service_percent': (
            _money((existing_emi + emi) / income.minimum * 100)
            if existing_emi is not None and emi is not None and income.minimum and income.minimum > 0 else None,
            '% of lowest recorded gross income', 'Review existing debt and the proposed EMI with the lender.', False),
        'minimum_reserve_months': (reserve_months, 'months of total expenses',
                                   'Build the reserve or verify which funds the lender accepts.', True),
        'minimum_credit_score': (Decimal(scenario.credit_score) if scenario.credit_score is not None else None,
                                  'entered credit score', 'Enter a current score from your credit report.', True),
        'maximum_credit_utilization_percent': (scenario.credit_utilization_percent, '% utilization you entered',
                                                'Review the utilization shown on your credit report.', False),
        'income_documents_required': (Decimal(int(scenario.income_documents_ready))
                                      if scenario.income_documents_ready is not None else None,
                                      'income documents ready (1=yes)', 'Gather the requested income documents.', True),
        'maximum_missed_payments': (Decimal(missed) if missed is not None else None,
                                    'missed payments in the available record',
                                    'Keep required repayments current and review your payment history.', False),
    }
    value, unit, action, minimum = values[key]
    status = ('UNKNOWN' if value is None else 'MET' if (value >= limit if minimum else value <= limit) else 'NOT_MET')
    title = key.replace('_', ' ').capitalize()
    current = f'{int(value)} {unit}' if value is not None and key in ('minimum_history_months', 'minimum_credit_score',
                            'income_documents_required', 'maximum_missed_payments') else f'{_label(value)} {unit}' if value is not None else None
    required = f'{int(limit)} {unit}' if key in ('minimum_history_months', 'minimum_credit_score',
                        'income_documents_required', 'maximum_missed_payments') else f'{_label(limit)} {unit}'
    return RequirementResult(key=key, name=title, current_value=current, required_value=required,
                             status=status, priority=2 if key in ('minimum_monthly_income',
                             'maximum_debt_service_percent', 'maximum_missed_payments') else 4,
                             source_type='user_entered', source_label=source,
                             explanation=(f'Your recorded value is {current or "not provided"}; the entered criterion is '
                                          f'{required}. This comparison is based on user-provided criteria, not a lender decision.'),
                             action=None if status == 'MET' else action)


def assess_loan(user: User, profile: FinancialProfile, scenario: LoanScenarioWrite, *,
                months: Sequence[FinancialMonth] = (), expenses: Sequence[RecurringExpense] = (),
                loans: Sequence[Loan] = (), goals: Sequence[FinancialGoal] = (),
                plans: Sequence[PlannedExpense] = (), as_of_date: date,
                evaluated_at: datetime | None = None, income_next_month: Decimal | None = None) -> ReadinessAssessment:
    """Calculate current and stress capacities, then compare only declared criteria."""
    state = financial_state(user, profile, goals, as_of_date, expenses=expenses, loans=loans,
                            plans=plans, months=months)
    picture = state.picture
    recorded = sorted((row for row in months if row.period <= as_of_date.replace(day=1)),
                      key=lambda row: row.period)[-12:]
    incomes = sorted(row.monthly_income for row in recorded)
    average = _money(sum(incomes, ZERO) / len(incomes)) if incomes else None
    median_income = _money(Decimal(median(incomes))) if incomes else None
    latest_change = recorded[-1].monthly_income - recorded[-2].monthly_income if len(recorded) > 1 else None
    income = IncomeSummary(observed_months=len(recorded), first_period=recorded[0].period if recorded else None,
                           latest_period=recorded[-1].period if recorded else None,
                           average=average, median=median_income,
                           minimum=incomes[0] if incomes else None, maximum=incomes[-1] if incomes else None,
                           variability_percent=picture.income.variability_percent.value,
                           latest_change=latest_change, pattern=getattr(profile, 'income_pattern', None))
    rate_based = (loan_emi(scenario.amount, scenario.annual_interest_rate_percent, scenario.tenure_months)
                  if scenario.annual_interest_rate_percent is not None else None)
    emi = scenario.quoted_monthly_payment if scenario.quoted_monthly_payment is not None else rate_based
    emi_source = 'entered_quote' if scenario.quoted_monthly_payment is not None else 'calculated' if rate_based is not None else 'missing'
    total_repayment = _money(emi * scenario.tenure_months) if emi is not None else None
    current_income = _money(income_next_month) if income_next_month is not None else user.monthly_income
    contribution = profile.monthly_savings_contribution
    current = _capacity('Current monthly estimate' if income_next_month is None else 'Next-month income preview',
                        current_income, profile.monthly_expenses, profile.monthly_debt_payments, contribution, emi)
    typical = (_capacity('Median recorded income with current expenses', median_income, profile.monthly_expenses,
                         profile.monthly_debt_payments, contribution, emi) if median_income is not None else None)
    lowest = next((row for row in recorded if row.monthly_income == income.minimum), None)
    low = (_capacity('Lowest recorded income with current expenses', income.minimum, profile.monthly_expenses,
                     profile.monthly_debt_payments, contribution, emi, lowest.period)
           if income.minimum is not None else None)
    month_points = [_capacity('Recorded month', row.monthly_income, row.monthly_expenses, row.scheduled_emi,
                              contribution, emi, row.period) for row in recorded]
    reserve_months = picture.reserve.total_expense_coverage_months.value
    reserve_gap = picture.reserve.funding_gap.value
    results: list[RequirementResult] = []

    def add(key: str, name: str, current_value: str | None, required_value: str | None,
            status: str, priority: int, explanation: str, action: str | None) -> None:
        results.append(RequirementResult(key=key, name=name, current_value=current_value,
                                         required_value=required_value, status=status, priority=priority,
                                         source_type='illustrative_project', source_label=ILLUSTRATIVE,
                                         explanation=explanation, action=action))

    history_status = 'UNKNOWN' if not recorded else 'MET' if len(recorded) >= 3 else 'NEEDS_IMPROVEMENT'
    add('income_history', 'Income history', f'{len(recorded)} recorded months', '3 months for a useful project comparison',
        history_status, 4, 'Recorded months show actual variation; the project uses three as a useful sample, not a lender rule.',
        'Record more actual income and spending months and keep income documents.' if history_status != 'MET' else None)
    variability = income.variability_percent
    variation_status = ('UNKNOWN' if variability is None else 'NEEDS_IMPROVEMENT'
                        if variability >= Decimal('20') else 'MET')
    add('income_stability', 'Income stability', _label(variability, '% variation'),
        'Below 20% variation as an illustrative signal', variation_status, 2,
        'Variation is the standard deviation of recorded income divided by its average. '
        'The 20% comparison is an app signal, not a lender requirement or forecast.',
        'Keep income records and build a cash buffer for lower-income months.'
        if variation_status != 'MET' else None)
    if emi is None:
        capacity_status = 'UNKNOWN'
    elif current.remaining_before_savings is not None and current.remaining_before_savings < 0:
        capacity_status = 'NOT_MET'
    elif low and low.remaining_before_savings is not None and low.remaining_before_savings < 0:
        capacity_status = 'NEEDS_IMPROVEMENT'
    elif contribution is None or low is None:
        capacity_status = 'UNKNOWN'
    elif current.remaining_after_savings < 0 or low.remaining_after_savings < 0:
        capacity_status = 'NEEDS_IMPROVEMENT'
    else:
        capacity_status = 'MET'
    add('repayment_capacity', 'Repayment capacity', _label(current.remaining_after_savings
        if current.remaining_after_savings is not None else current.remaining_before_savings),
        '0.00 or more after expenses, planned savings and new EMI', capacity_status, 1,
        'Profile and Month expenses already include existing EMI. The new EMI is subtracted once. '
        'The lowest recorded income is also tested against current expenses; gross income is before tax.',
        'Check the proposed payment against take-home income and lower-income months before adding a fixed EMI.'
        if capacity_status != 'MET' else None)
    short_months = [point for point in month_points if point.remaining_before_savings is not None
                    and point.remaining_before_savings < 0]
    cash_status = ('UNKNOWN' if not month_points or emi is None else 'NEEDS_IMPROVEMENT'
                   if short_months else 'MET')
    add('cash_flow_stability', 'Cash-flow stability',
        f'{len(short_months)} of {len(month_points)} recorded months show a gross shortfall'
        if cash_status != 'UNKNOWN' else None,
        'No recorded month with a gross shortfall after the proposed EMI', cash_status, 2,
        'Each recorded month uses its own income and total spending, with existing EMI already included. '
        'The proposed EMI is then subtracted once.',
        'Review the shortfall months and build a buffer before adding a fixed payment.'
        if cash_status != 'MET' else None)
    reserve_status = 'UNKNOWN' if reserve_months is None else 'MET' if reserve_months >= EMERGENCY_TARGET_MONTHS else 'NEEDS_IMPROVEMENT'
    add('reserve', 'Emergency reserve', _label(reserve_months, ' months'),
        f'{EMERGENCY_TARGET_MONTHS:g} months of total expenses', reserve_status, 2,
        'Coverage is saved emergency funds divided by current total monthly expenses. This is the existing Advisor target.',
        'Build a cash buffer that can cover obligations during a low-income month.' if reserve_status != 'MET' else None)
    existing_emi = profile.monthly_debt_payments
    debt_pct = (_money(existing_emi / current_income * 100) if existing_emi is not None and current_income > 0 else None)
    debt_status = 'UNKNOWN' if debt_pct is None else 'NEEDS_IMPROVEMENT' if debt_pct >= HIGH_DTI_PERCENT else 'MET'
    add('existing_obligations', 'Existing debt payments', _label(debt_pct, '% of current gross income'),
        f'Below {HIGH_DTI_PERCENT:g}% under the existing project check', debt_status, 2,
        'The existing debt payment is part of Profile expenses and is not subtracted a second time.',
        'Keep required payments current; review debt burden before adding another EMI.' if debt_status != 'MET' else None)
    completed_months = [row for row in recorded if row.period < as_of_date.replace(day=1) and row.scheduled_emi > 0]
    recorded_missed = sum(1 for row in completed_months if row.paid_emi < row.scheduled_emi)
    missed = (scenario.missed_payments_last_12_months if scenario.missed_payments_last_12_months is not None
              else recorded_missed if completed_months else None)
    payment_status = 'UNKNOWN' if missed is None else 'MET' if missed == 0 else 'NEEDS_IMPROVEMENT'
    add('repayment_consistency', 'Recorded repayment consistency',
        f'{missed} reported or recorded missed months' if missed is not None else None,
        'No missed payments in available information', payment_status, 2,
        'Only user-entered missed-payment information and completed saved months are considered; no credit-bureau history is inferred.',
        'Review missed payments and keep future required payments current.' if payment_status != 'MET' else None)
    credit_known = any(value is not None for value in (scenario.credit_score, scenario.credit_history_months,
                                                       scenario.credit_utilization_percent))
    add('credit_information', 'Credit information', 'User-provided credit details' if credit_known else None,
        'Information to review with a lender', 'MET' if credit_known else 'UNKNOWN', 5,
        ('Credit details were entered by you; no score is generated or treated as an approval score.'
         if credit_known else 'Credit information not provided. No score is generated or inferred.'),
        None if credit_known else 'Add credit information from your own report if you want to compare a stated criterion.')
    docs_status = 'UNKNOWN' if scenario.income_documents_ready is None else 'MET' if scenario.income_documents_ready else 'NEEDS_IMPROVEMENT'
    add('income_documents', 'Income documentation',
        'Ready' if scenario.income_documents_ready else 'Not ready' if scenario.income_documents_ready is False else None,
        'Documents needed depend on the lender', docs_status, 5,
        'Document requirements differ; a lender must confirm the exact records it needs.',
        'Gather and confirm the requested income records.' if docs_status != 'MET' else None)
    for criterion in scenario.criteria:
        results.append(_criterion_result(criterion, income=income, current_income=current_income, emi=emi,
                                         existing_emi=existing_emi, reserve_months=reserve_months,
                                         scenario=scenario, missed=missed))

    agent_results = [BudgetAgent().analyze(state), DebtAgent().analyze(state), EmergencyAgent().analyze(state)]
    if goals:
        agent_results.append(GoalPlanningAgent().analyze(state))
    agent_findings = [dict(agent_id=result.agent_id, code=finding.code, title=finding.title,
                           reason=finding.reason, action=finding.suggested_action)
                      for result in agent_results for finding in result.findings if finding.priority]
    goal_needs = []
    if goals:
        goal_result = agent_results[-1]
        goal_needs = [dict(name=item.goal.name, priority=item.goal.priority,
                           required_monthly=str(item.required_monthly) if item.required_monthly is not None else None,
                           status=item.status) for item in goal_result.facts.requirements]
    actions = sorted((item for item in results if item.status != 'MET' and item.action),
                     key=lambda item: (item.priority, item.status == 'UNKNOWN', item.key))
    if capacity_status == 'NOT_MET':
        summary = 'The proposed EMI produces a gross monthly shortfall under your current figures. Strengthen cash flow before relying on this loan plan.'
    elif capacity_status == 'NEEDS_IMPROVEMENT':
        summary = 'The proposed EMI may fit some months, but a lower-income month or planned savings leaves too little room.'
    elif capacity_status == 'UNKNOWN':
        summary = 'More information is needed to judge the proposed payment alongside savings and lower-income months.'
    else:
        summary = 'The entered figures show room for this payment in the tested months; this is preparation, not a lender decision.'
    assumptions = [
        'All income figures are gross, before tax and irregular payment timing.',
        'Profile and recorded Month expenses already include existing EMI; the proposed EMI is the only new payment subtracted.',
        'Median and lowest recorded income are tested against current Profile expenses; recorded-month rows use their own expenses.',
        'A calculated EMI assumes equal monthly principal-and-interest payments at a fixed rate, with no fees, insurance or changing rates.',
        'The reserve does not change in a preview until the user saves an actual deposit.',
        'Historical income is observed, not a forecast; no lender approval or verified lender criterion is inferred.',
    ]
    if contribution is None:
        assumptions.append('Monthly savings contribution is missing; positive remaining amounts are upper bounds before planned savings.')
    if emi_source == 'entered_quote' and rate_based is not None and abs(emi - rate_based) > CENT:
        assumptions.append('The entered payment quote is used for capacity; it differs from the rate-based calculation. Confirm fees and terms.')
    fingerprint = _input_fingerprint(scenario, user, profile, months, expenses, loans, goals, plans, as_of_date)
    return ReadinessAssessment(scenario_id=getattr(scenario, 'id', None),
                               evaluated_at=evaluated_at or datetime.now(timezone.utc), as_of_date=as_of_date,
                               input_fingerprint=fingerprint, summary=summary, estimated_emi=emi,
                               rate_based_emi=rate_based, emi_source=emi_source,
                               total_repayment=total_repayment, income=income, current_month=current,
                               typical_month=typical, low_income_month=low, recorded_months=month_points,
                               reserve_coverage_months=reserve_months, reserve_gap=reserve_gap,
                               known_essential_expenses=picture.spending.known_essential.value,
                               known_discretionary_expenses=picture.spending.known_discretionary.value,
                               unclassified_expenses=picture.spending.unclassified_monthly.value,
                               existing_debt=profile.existing_debt, existing_monthly_emi=existing_emi,
                               requirements=results, priority_actions=actions,
                               goal_monthly_needs=goal_needs, agent_findings=agent_findings,
                               assumptions=assumptions)


def preview_loan(user: User, profile: FinancialProfile, scenario: LoanScenarioWrite,
                 change: LoanPreviewWrite, *, months: Sequence[FinancialMonth] = (),
                 expenses: Sequence[RecurringExpense] = (), loans: Sequence[Loan] = (),
                 goals: Sequence[FinancialGoal] = (), plans: Sequence[PlannedExpense] = (),
                 as_of_date: date) -> LoanPreviewRead:
    before = assess_loan(user, profile, scenario, months=months, expenses=expenses, loans=loans,
                         goals=goals, plans=plans, as_of_date=as_of_date)
    values = scenario.model_dump(exclude={'id', 'user_id', 'updated_at'})
    for key in ('amount', 'annual_interest_rate_percent', 'tenure_months'):
        if getattr(change, key) is not None:
            values[key] = getattr(change, key)
    if change.amount is not None or change.annual_interest_rate_percent is not None or change.tenure_months is not None:
        values['quoted_monthly_payment'] = None
    changed_scenario = LoanScenarioWrite.model_validate(values)
    after = assess_loan(user, profile, changed_scenario, months=months, expenses=expenses,
                        loans=loans, goals=goals, plans=plans, as_of_date=as_of_date,
                        income_next_month=change.income_next_month)
    one_time_cash = (after.current_month.remaining_before_savings + change.one_time_extra
                     if change.one_time_extra is not None and after.current_month.remaining_before_savings is not None else None)
    advice = []
    base_room = after.current_month.remaining_before_savings
    missed = next((item for item in after.requirements if item.key == 'repayment_consistency'), None)
    if missed and missed.status == 'NEEDS_IMPROVEMENT':
        advice.append('Bring existing required repayments current first; the amount overdue is not known here.')
    if change.one_time_extra is not None and base_room is not None and base_room < 0:
        advice.append(f'Cover the {_label(-base_room)} gross cash shortfall before assigning extra cash elsewhere. '
                      'Check take-home pay and unrecorded costs as well.')
    elif base_room is not None and base_room < 0:
        advice.append('Check essential costs and keep existing required EMI payments current before adding a new payment.')
    due_soon = [item for item in plans if item.is_essential and item.due_date <= as_of_date + timedelta(days=30)
                and item.estimated_amount > (item.amount_reserved or ZERO)]
    if due_soon:
        due = min(due_soon, key=lambda item: item.due_date)
        advice.append(f'Check the {_label(due.estimated_amount - (due.amount_reserved or ZERO))} still needed for '
                      f'{due.name}, an essential expense due {due.due_date}.')
    if after.reserve_gap > 0:
        if change.one_time_extra is not None and one_time_cash is not None and one_time_cash > 0:
            advice.append(f'After required bills, consider putting up to {_label(min(one_time_cash, after.reserve_gap))} '
                          f'of the available extra cash toward the {_label(after.reserve_gap)} reserve gap; '
                          'this is an option, not a saved transfer.')
        else:
            advice.append(f'Review the {_label(after.reserve_gap)} reserve gap before assigning extra cash to optional goals.')
    if after.known_discretionary_expenses > 0 and base_room is not None and base_room < 0:
        advice.append(f'You recorded {_label(after.known_discretionary_expenses)} in discretionary monthly costs; check what can actually be reduced.')
    if after.existing_debt > 0:
        advice.append('Review existing debt terms after required payments and cash buffer needs.')
    if after.goal_monthly_needs:
        advice.append('Review high-priority goal deadlines after required payments and reserve needs.')
    if not advice:
        advice.append('Confirm take-home cash, lender terms and payment timing before committing to a new EMI.')
    if change.one_time_extra is not None:
        explanation = ('One-time extra income raises this month’s illustrative cash only. It does not change recurring income, '
                       'historical months, the saved reserve, or the proposed EMI.')
    elif change.income_next_month is not None:
        explanation = ('The next-month income preview changes only the current capacity check. Recorded months, saved balances, '
                       'and lender criteria remain unchanged.')
    else:
        explanation = 'Changed loan terms affect the estimated EMI and capacity without changing saved finances.'
    return LoanPreviewRead(before=before, after=after, one_time_extra=change.one_time_extra,
                           one_time_cash_after_expenses_and_emi=_money(one_time_cash) if one_time_cash is not None else None,
                           priority_advice=advice, explanation=explanation)
