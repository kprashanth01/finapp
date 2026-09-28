from decimal import Decimal

RULE_VERSION = "rule-based-v1"
HIGH_EXPENSE_PERCENT = Decimal("80")
HIGH_DTI_PERCENT = Decimal("20")
EMERGENCY_TARGET_MONTHS = Decimal("3")
PRIORITY_ORDER = {"emergency": 0, "debt": 1, "budget": 2}
