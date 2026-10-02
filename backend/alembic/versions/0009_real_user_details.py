"""Optional income context, recurring expenses, loans, and planned expenses.

Revision ID: 0009_real_user_details
Revises: 0008_financial_months
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_real_user_details"
down_revision = "0008_financial_months"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_profiles", sa.Column("income_pattern", sa.String(20), nullable=True))
    op.add_column("financial_profiles", sa.Column("guaranteed_monthly_income", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint("ck_profiles_income_pattern", "financial_profiles",
                               "income_pattern IS NULL OR income_pattern IN ('stable', 'variable', 'mixed')")
    op.create_check_constraint("ck_profiles_guaranteed_income", "financial_profiles",
                               "guaranteed_monthly_income IS NULL OR guaranteed_monthly_income >= 0")

    op.create_table(
        "recurring_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.CheckConstraint("monthly_amount > 0", name="ck_recurring_expense_amount"),
        sa.CheckConstraint("category IN ('essential_fixed', 'essential_variable', 'discretionary')", name="ck_recurring_expense_category"),
    )
    op.create_index("ix_recurring_expenses_user", "recurring_expenses", ["user_id"])

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("loan_type", sa.String(40), nullable=True),
        sa.Column("remaining_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("annual_interest_rate_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("payment_day", sa.Integer(), nullable=True),
        sa.Column("rate_change_date", sa.Date(), nullable=True),
        sa.Column("new_annual_interest_rate_percent", sa.Numeric(6, 2), nullable=True),
        sa.CheckConstraint("remaining_balance >= 0 AND monthly_payment >= 0", name="ck_loans_amounts"),
        sa.CheckConstraint("annual_interest_rate_percent IS NULL OR annual_interest_rate_percent >= 0", name="ck_loans_apr"),
        sa.CheckConstraint("new_annual_interest_rate_percent IS NULL OR new_annual_interest_rate_percent >= 0", name="ck_loans_new_apr"),
        sa.CheckConstraint("payment_day IS NULL OR payment_day BETWEEN 1 AND 31", name="ck_loans_payment_day"),
        sa.CheckConstraint("(rate_change_date IS NULL) = (new_annual_interest_rate_percent IS NULL)", name="ck_loans_rate_change_pair"),
    )
    op.create_index("ix_loans_user", "loans", ["user_id"])

    op.create_table(
        "planned_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("estimated_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_reserved", sa.Numeric(12, 2), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("estimated_amount > 0 AND (amount_reserved IS NULL OR (amount_reserved >= 0 AND amount_reserved <= estimated_amount))",
                           name="ck_planned_expense_amounts"),
    )
    op.create_index("ix_planned_expenses_user_due", "planned_expenses", ["user_id", "due_date"])


def downgrade() -> None:
    op.drop_index("ix_planned_expenses_user_due", table_name="planned_expenses")
    op.drop_table("planned_expenses")
    op.drop_index("ix_loans_user", table_name="loans")
    op.drop_table("loans")
    op.drop_index("ix_recurring_expenses_user", table_name="recurring_expenses")
    op.drop_table("recurring_expenses")
    op.drop_constraint("ck_profiles_guaranteed_income", "financial_profiles", type_="check")
    op.drop_constraint("ck_profiles_income_pattern", "financial_profiles", type_="check")
    op.drop_column("financial_profiles", "guaranteed_monthly_income")
    op.drop_column("financial_profiles", "income_pattern")
