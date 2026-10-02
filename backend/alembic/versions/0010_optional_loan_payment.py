"""Keep an unreported required loan payment unknown rather than zero.

Revision ID: 0010_optional_loan_payment
Revises: 0009_real_user_details
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_optional_loan_payment"
down_revision = "0009_real_user_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_loans_amounts", "loans", type_="check")
    op.alter_column("loans", "monthly_payment", existing_type=sa.Numeric(12, 2), nullable=True)
    op.create_check_constraint("ck_loans_amounts", "loans",
                               "remaining_balance >= 0 AND (monthly_payment IS NULL OR monthly_payment >= 0)")


def downgrade() -> None:
    op.drop_constraint("ck_loans_amounts", "loans", type_="check")
    # This downgrade intentionally fails if unknown payments exist; it never rewrites them as zero.
    op.alter_column("loans", "monthly_payment", existing_type=sa.Numeric(12, 2), nullable=False)
    op.create_check_constraint("ck_loans_amounts", "loans",
                               "remaining_balance >= 0 AND monthly_payment >= 0")
