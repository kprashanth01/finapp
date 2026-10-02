"""Allow a loan obligation without an invented individual balance.

Revision ID: 0011_optional_loan_balance
Revises: 0010_optional_loan_payment
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_optional_loan_balance"
down_revision = "0010_optional_loan_payment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_loans_amounts", "loans", type_="check")
    op.alter_column("loans", "remaining_balance", existing_type=sa.Numeric(12, 2), nullable=True)
    op.create_check_constraint("ck_loans_amounts", "loans",
                               "(remaining_balance IS NULL OR remaining_balance >= 0) AND (monthly_payment IS NULL OR monthly_payment >= 0)")


def downgrade() -> None:
    op.drop_constraint("ck_loans_amounts", "loans", type_="check")
    # This downgrade fails if unknown balances exist; it never rewrites them as zero.
    op.alter_column("loans", "remaining_balance", existing_type=sa.Numeric(12, 2), nullable=False)
    op.create_check_constraint("ck_loans_amounts", "loans",
                               "remaining_balance >= 0 AND (monthly_payment IS NULL OR monthly_payment >= 0)")
