"""Plain-language answers drawn from one structured loan assessment."""

import re
from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Sequence

from app.loan_readiness_schemas import (LoanChatAnswer, LoanPreviewWrite, LoanScenarioWrite,
                                         ReadinessAssessment, RequirementResult)
from app.models import FinancialGoal, FinancialMonth, FinancialProfile, Loan, PlannedExpense, RecurringExpense, User
from app.services.loan_readiness import preview_loan


_NUMBER = re.compile(r'(?:₹|Rs\.?\s*)?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)', re.I)


def is_loan_question(question: str) -> bool:
    return bool(re.search(r'\b(loan readiness|ready for (?:this|a|the) loan|apply(?:ing)? for (?:a|the|this) loan|'
                          r'new loan|proposed loan|this emi|new emi|lender requirement|loan requirement|'
                          r'ready to borrow|readiness)\b', question.lower()))


def _amount(question: str) -> Decimal | None:
    match = _NUMBER.search(question)
    return Decimal(match.group(1).replace(',', '')) if match else None


def _money(value: Decimal | None) -> str:
    return 'unknown' if value is None else f'{value:,.2f}'


def _facts(assessment: ReadinessAssessment, *keys: str) -> list[RequirementResult]:
    return [item for item in assessment.requirements if item.key in keys]


def answer_loan_question(question: str, assessment: ReadinessAssessment, scenario: LoanScenarioWrite, *,
                         user: User, profile: FinancialProfile, months: Sequence[FinancialMonth] = (),
                         expenses: Sequence[RecurringExpense] = (), loans: Sequence[Loan] = (),
                         goals: Sequence[FinancialGoal] = (), plans: Sequence[PlannedExpense] = (),
                         as_of_date: date) -> LoanChatAnswer:
    lower = question.lower()
    amount = _amount(question)
    asks_income_change = bool(
        (re.search(r'\b(income|earn|earning|salary|pay)\b', lower)
         and re.search(r'\b(what if|if|next month|drops?|falls?|los[es]|extra|increase|decrease|only)\b', lower))
        or (re.search(r'\b(received|receive|got|bonus|windfall)\b', lower)
            and re.search(r'\b(extra|bonus|windfall)\b', lower)))
    if asks_income_change:
        if amount is None:
            return LoanChatAnswer(answer='What income amount or percentage should I test for next month?',
                                  evidence=_facts(assessment, 'repayment_capacity'), assessment=assessment)
        preview_values = {}
        if re.search(r'\b(extra|bonus|received|receive|got|one.time|windfall)\b', lower) and not re.search(r'\b(drops?|falls?|los[es])\b', lower):
            preview_values['one_time_extra'] = amount
        elif '%' in lower and re.search(r'\b(drop|fall|lose|loss|decrease)\b', lower):
            preview_values['income_next_month'] = max(Decimal('0'), user.monthly_income * (1 - amount / 100))
        elif '%' in lower and re.search(r'\b(increase|rise|gain|more)\b', lower):
            preview_values['income_next_month'] = user.monthly_income * (1 + amount / 100)
        elif re.search(r'\b(by|less|lower by)\b', lower) and re.search(r'\b(drop|fall|lose|decrease|lower)\b', lower):
            preview_values['income_next_month'] = max(Decimal('0'), user.monthly_income - amount)
        elif re.search(r'\b(by|more)\b', lower) and re.search(r'\b(increase|rise|earn|make)\b', lower):
            preview_values['income_next_month'] = user.monthly_income + amount
        else:
            preview_values['income_next_month'] = amount
        preview = preview_loan(user, profile, scenario, LoanPreviewWrite.model_validate(preview_values),
                               months=months, expenses=expenses, loans=loans, goals=goals, plans=plans,
                               as_of_date=as_of_date)
        after = preview.after
        if preview.one_time_extra is not None:
            answer = (f'The {_money(preview.one_time_extra)} extra is one-time cash. This month’s gross room after '
                      f'current expenses and the proposed {_money(after.estimated_emi)} EMI would be '
                      f'{_money(preview.one_time_cash_after_expenses_and_emi)} before planned savings. '
                      'Your recurring loan readiness and saved reserve do not change until you update them.')
        else:
            answer = (f'At {_money(after.current_month.income)} gross income next month, the proposed EMI remains '
                      f'{_money(after.estimated_emi)}. Gross room after current expenses and that EMI would be '
                      f'{_money(after.current_month.remaining_before_savings)} before planned savings. '
                      f'{after.summary}')
        if preview.priority_advice:
            answer += ' Priorities: ' + ' '.join(f'{index}. {item}' for index, item in
                                               enumerate(preview.priority_advice[:3], start=1))
        return LoanChatAnswer(answer=answer, evidence=_facts(after, 'repayment_capacity', 'reserve'),
                              assessment=after, preview=preview)

    if re.search(r'\b(changed?|different|since last|since previous)\b', lower):
        changes = assessment.changes_since_previous
        answer = ('Since the prior saved evaluation: ' + '; '.join(changes) + '.' if changes else
                  'No change is recorded since the previous evaluation, or this is the first evaluation. '
                  'The page recalculates when you open it or update the proposed loan.')
        return LoanChatAnswer(answer=answer, evidence=[], assessment=assessment)

    if re.search(r'\b(how long|how many months)\b', lower):
        contribution = profile.monthly_savings_contribution
        if contribution is not None and contribution > 0 and assessment.reserve_gap > 0:
            months_needed = int((assessment.reserve_gap / contribution).to_integral_value(rounding=ROUND_CEILING))
            answer = (f'If the full {_money(contribution)} entered monthly savings contribution went to your '
                      f'{_money(assessment.reserve_gap)} reserve gap, it would take about {months_needed} months. '
                      'That is an illustration, not the current goal allocation or a lender requirement.')
        else:
            answer = ('A timeline needs a positive monthly amount you can reliably set aside and a chosen area '
                      'to strengthen. Enter a realistic savings contribution in Profile first.')
        return LoanChatAnswer(answer=answer, evidence=_facts(assessment, 'reserve'), assessment=assessment)

    if re.search(r'\b(credit|score|utilization)\b', lower):
        fact = _facts(assessment, 'credit_information')
        answer = ('Credit information not provided. The app does not create a credit score or infer lender approval.'
                  if fact and fact[0].status == 'UNKNOWN' else
                  'The credit details shown were entered by you. Compare them only with a criterion whose source you have checked.')
        return LoanChatAnswer(answer=answer, evidence=fact, assessment=assessment)

    if re.search(r'\b(emergency|reserve|buffer)\b', lower):
        answer = (f'Your saved emergency reserve covers {_money(assessment.reserve_coverage_months)} months '
                  f'of total expenses. The gap to the app’s illustrative three-month target is '
                  f'{_money(assessment.reserve_gap)}. A buffer matters when income varies but this target is not a lender rule.')
        return LoanChatAnswer(answer=answer, evidence=_facts(assessment, 'reserve'), assessment=assessment)

    if re.search(r'\b(emi|afford|payment|capacity|cash.flow)\b', lower):
        low = assessment.low_income_month
        answer = (f'The proposed EMI is {_money(assessment.estimated_emi)}. Current gross room after expenses and '
                  f'that EMI is {_money(assessment.current_month.remaining_before_savings)} before planned savings. '
                  + (f'At the lowest recorded income, the same current expense level leaves '
                     f'{_money(low.remaining_before_savings)}.' if low else
                     'Record income months to test a lower-income period.'))
        if profile.monthly_savings_contribution is None:
            answer += ' Your planned savings contribution is not supplied, so positive room is an upper bound.'
        return LoanChatAnswer(answer=answer, evidence=_facts(assessment, 'repayment_capacity'), assessment=assessment)

    if re.search(r'\b(debt|existing loan|obligations)\b', lower):
        answer = (f'Existing required monthly debt payments are {_money(assessment.existing_monthly_emi)} '
                  'and are already included in Profile expenses. The proposed EMI is a separate new payment. '
                  'Keep existing required payments current before adding a fixed obligation.')
        return LoanChatAnswer(answer=answer, evidence=_facts(assessment, 'existing_obligations', 'repayment_consistency'),
                              assessment=assessment)

    if re.search(r'\b(requirement|criteria|failing|not met|lender)\b', lower):
        user_rules = [item for item in assessment.requirements if item.source_type == 'user_entered']
        unmet = [item for item in user_rules if item.status in ('NOT_MET', 'NEEDS_IMPROVEMENT')]
        if not user_rules:
            answer = ('No lender criteria are configured for this scenario. The displayed checks are illustrative '
                      'project criteria, not lender policies. Enter a requirement with its source to compare it.')
        elif unmet:
            answer = ('Based on the criteria you entered, these requirements are not currently met: ' +
                      '; '.join(f'{item.name} ({item.current_value or "unknown"} versus {item.required_value})'
                                for item in unmet[:4]) + '. Confirm the source and current lender policy.')
        else:
            answer = ('No entered requirement is currently marked not met. Unknown fields still need evidence, '
                      'and this comparison does not establish lender eligibility.')
        return LoanChatAnswer(answer=answer, evidence=unmet or user_rules[:4], assessment=assessment)

    actions = assessment.priority_actions[:3]
    answer = assessment.summary
    if assessment.estimated_emi is not None:
        answer += f' The proposed monthly EMI is {_money(assessment.estimated_emi)}.'
    if actions:
        answer += ' Strengthen: ' + '; '.join(item.action for item in actions if item.action) + '.'
    answer += ' Only user-entered criteria are compared as possible lender requirements; approval is not predicted.'
    return LoanChatAnswer(answer=answer, evidence=actions, assessment=assessment)
