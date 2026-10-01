"""Account-owned monthly financial history.

Revision ID: 0008_financial_months
Revises: 0007_research_evaluation
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_financial_months"
down_revision = "0007_research_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_months",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthly_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("fixed_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("scheduled_emi", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_emi", sa.Numeric(12, 2), nullable=False),
        sa.Column("savings", sa.Numeric(12, 2), nullable=False),
        sa.Column("emergency_fund", sa.Numeric(12, 2), nullable=False),
        sa.Column("outstanding_debt", sa.Numeric(12, 2), nullable=False),
        sa.Column("unfunded_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("risk_tolerance", sa.String(20), nullable=False),
        sa.Column("investment_horizon_years", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "period", name="uq_financial_month_user_period"),
        sa.CheckConstraint("monthly_income >= 0 AND monthly_expenses >= 0 AND fixed_expenses >= 0", name="ck_month_nonnegative_flow"),
        sa.CheckConstraint("scheduled_emi >= 0 AND paid_emi >= 0 AND paid_emi <= scheduled_emi", name="ck_month_emi"),
        sa.CheckConstraint("fixed_expenses + scheduled_emi <= monthly_expenses", name="ck_month_expense_parts"),
        sa.CheckConstraint("savings >= 0 AND emergency_fund >= 0 AND emergency_fund <= savings", name="ck_month_reserve"),
        sa.CheckConstraint("outstanding_debt >= 0 AND unfunded_expenses >= 0", name="ck_month_debt_unfunded"),
        sa.CheckConstraint("risk_tolerance IN ('conservative', 'moderate', 'aggressive')", name="ck_month_risk"),
        sa.CheckConstraint("investment_horizon_years BETWEEN 0 AND 80", name="ck_month_horizon"),
    )
    op.create_index("ix_financial_month_user_period", "financial_months", ["user_id", "period"])


def downgrade() -> None:
    op.drop_index("ix_financial_month_user_period", table_name="financial_months")
    op.drop_table("financial_months")
