"""Keep monthly debt payments within total expenses.

Revision ID: 0003_debt_payment_limit
Revises: 0002_analysis_inputs
"""

from alembic import op


revision = "0003_debt_payment_limit"
down_revision = "0002_analysis_inputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_profiles_debt_payments_within_expenses",
        "financial_profiles",
        "monthly_debt_payments IS NULL OR monthly_debt_payments <= monthly_expenses",
    )


def downgrade() -> None:
    op.drop_constraint("ck_profiles_debt_payments_within_expenses", "financial_profiles", type_="check")
