from decimal import Decimal

RULE_VERSION = "rule-based-v1"
HIGH_EXPENSE_PERCENT = Decimal("80")
HIGH_DTI_PERCENT = Decimal("20")
EMERGENCY_TARGET_MONTHS = Decimal("3")
PRIORITY_ORDER = {"emergency": 0, "debt": 1, "budget": 2}
PLANNING_MONTH_DAYS = 30
SHORT_HORIZON_YEARS = 3
LONG_HORIZON_YEARS = 7
GOAL_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
