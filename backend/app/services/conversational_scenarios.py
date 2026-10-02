"""Conservative parsing of a few spoken changes into validated event previews."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Sequence

from app.advisory.chat import ChatTurn
from app.models import RecurringExpense
from app.services.event_scenario import EventScenarioWrite, MAX_MONEY


_AMOUNT = re.compile(r'(?<![\w.])(?:[₹$€£]\s*)?(\d[\d,]*(?:\.\d{1,2})?)\s*([kK])?(?![\w.])')
_FOLLOW_UP = re.compile(r'^(?:to|by)\s+(?:[₹$€£]\s*)?\d', re.I)
_GROUPED_AMOUNT = re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3})(?:\.\d{1,2})?')


@dataclass(frozen=True)
class ParsedScenario:
    recognized: bool
    event: EventScenarioWrite | None = None
    question: str = ''
    need: str | None = None


def _amounts(question: str) -> list[tuple[Decimal, int]]:
    values = []
    for match in _AMOUNT.finditer(question):
        if ',' in match.group(1) and not _GROUPED_AMOUNT.fullmatch(match.group(1)):
            continue
        try:
            value = Decimal(match.group(1).replace(',', ''))
            if match.group(2):
                value *= 1000
            values.append((value, match.start()))
        except InvalidOperation:
            continue
    return values


def _invalid_grouped_amount(question: str) -> bool:
    return any(',' in match.group(1) and not _GROUPED_AMOUNT.fullmatch(match.group(1))
               for match in _AMOUNT.finditer(question))


def _positive_amount(question: str) -> tuple[Decimal | None, int | None, str | None]:
    values = _amounts(question)
    if not values:
        return None, None, 'Enter one positive amount in your profile currency to preview this change.'
    if len(values) != 1:
        return None, None, 'Ask about one changed amount at a time.'
    amount, offset = values[0]
    if amount <= 0 or amount > MAX_MONEY:
        return None, None, 'Enter one positive amount within the supported money range.'
    return amount, offset, None


def _named_expense(question: str, expenses: Sequence[RecurringExpense]):
    matches = [item for item in expenses if item.category == 'discretionary' and re.search(
        rf'(?<!\w){re.escape(item.name)}(?!\w)', question, re.I)]
    return matches[0] if len(matches) == 1 else None, len(matches)


def parse_scenario(question: str, history: list[ChatTurn], monthly_income: Decimal,
                   expenses: Sequence[RecurringExpense]) -> ParsedScenario:
    text = question.strip()
    if history and _FOLLOW_UP.match(text):
        text = f'{history[-1].question} {text}'
    lower = text.lower()
    one_time = bool(re.search(r'\b(extra|bonus|windfall|received|receive|got|get)\b', lower)) and bool(
        re.search(r'\b(money|cash|paid|payment|income|extra|bonus|windfall)\b|[₹$€£]', lower))
    subscription = bool(re.search(r'\b(stop|cancel|reduce|cut)\b', lower)) and bool(
        re.search(r'\b(subscription|streaming|recurring)\b', lower) or _named_expense(text, expenses)[1])
    income = bool(re.search(r'\b(income|earn|earning|earnings|salary|make|paycheck)\b', lower)) and bool(
        re.search(r'\b(what if|if|next month|fall|falls|drop|drops|lower|decrease|increase|rise|rises|earn|make)\b', lower))
    if sum((one_time, subscription, income and not one_time)) > 1:
        return ParsedScenario(True, question=text, need='Ask about one financial change at a time.')
    if (one_time or subscription or income) and _invalid_grouped_amount(text):
        return ParsedScenario(True, question=text, need='Check the amount: use digits without commas or standard comma grouping.')
    if (one_time or subscription) and re.search(r'\b(next month|later month|future month)\b', lower):
        return ParsedScenario(True, question=text, need='This preview starts in the current planning month and cannot place the change in a future month. Ask about a current change instead.')

    if subscription:
        selected, count = _named_expense(text, expenses)
        if count > 1:
            return ParsedScenario(True, question=text, need='Name one saved discretionary expense to change.')
        if selected is None:
            return ParsedScenario(True, question=text, need='Add or name a saved discretionary subscription in Profile first.')
        stopping = bool(re.search(r'\b(stop|cancel)\b', lower))
        amounts = _amounts(text)
        if stopping:
            if amounts and (len(amounts) != 1 or amounts[0][0] != selected.monthly_amount):
                return ParsedScenario(True, question=text, need='The stated amount differs from the saved monthly cost. Confirm the saved expense or ask about a reduction by a specific amount.')
            amount = selected.monthly_amount
        else:
            amount, _, need = _positive_amount(text)
            if need:
                return ParsedScenario(True, question=text, need=need)
        if amount <= 0 or amount > selected.monthly_amount:
            return ParsedScenario(True, question=text, need='The reduction must be positive and no more than the saved monthly cost.')
        return ParsedScenario(True, EventScenarioWrite(kind='subscription_reduction', amount=amount,
                                                       expense_id=selected.id), text)

    if one_time:
        if re.search(r'\b(per month|each month|monthly|every month)\b', lower):
            return ParsedScenario(True, question=text, need='Is this extra money one-time, or an increase in monthly income? Ask about one of those changes.')
        amount, _, need = _positive_amount(text)
        if need:
            return ParsedScenario(True, question=text, need=need)
        return ParsedScenario(True, EventScenarioWrite(kind='one_time_income', amount=amount), text)

    if income:
        amount, offset, need = _positive_amount(text)
        if need:
            return ParsedScenario(True, question=text, need=need)
        prefix = lower[max(0, offset - 35):offset].strip()
        if re.search(r'\bby\s*(?:[₹$€£]\s*)?$', prefix):
            decreasing = bool(re.search(r'\b(fall|falls|drop|drops|lower|decrease|less|lose|lost)\b', lower))
            increasing = bool(re.search(r'\b(increase|rise|rises|higher|more)\b', lower))
            if decreasing == increasing:
                return ParsedScenario(True, question=text, need='Say whether monthly income rises or falls by that amount.')
            direction = 'income_decrease' if decreasing else 'income_increase'
            delta = amount
        elif re.search(r'\b(to|at|of|be|earn|make)\s*(?:[₹$€£]\s*)?$', prefix):
            delta = abs(amount - monthly_income)
            direction = 'income_increase' if amount > monthly_income else 'income_decrease'
        else:
            return ParsedScenario(True, question=text, need='Say whether income changes to this amount or by this amount.')
        if delta == 0:
            return ParsedScenario(True, question=text, need='That matches your saved monthly income, so there is no change to preview.')
        if direction == 'income_decrease' and delta > monthly_income:
            return ParsedScenario(True, question=text, need='A decrease cannot take monthly income below zero; enter a smaller change or a new total.')
        if direction == 'income_increase' and monthly_income + delta > MAX_MONEY:
            return ParsedScenario(True, question=text, need='The changed income exceeds the supported money range.')
        return ParsedScenario(True, EventScenarioWrite(kind=direction, amount=delta), text)

    return ParsedScenario(False)
