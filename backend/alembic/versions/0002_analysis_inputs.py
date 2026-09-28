"""Add monthly flow inputs for deterministic analysis.

Revision ID: 0002_analysis_inputs
Revises: 0001_users_profiles
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_analysis_inputs"
down_revision = "0001_users_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles", sa.Column("monthly_savings_contribution", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "financial_profiles", sa.Column("monthly_debt_payments", sa.Numeric(12, 2), nullable=True)
    )
    op.create_check_constraint(
        "ck_profiles_monthly_savings_contribution",
        "financial_profiles",
        "monthly_savings_contribution IS NULL OR monthly_savings_contribution >= 0",
    )
    op.create_check_constraint(
        "ck_profiles_monthly_debt_payments",
        "financial_profiles",
        "monthly_debt_payments IS NULL OR monthly_debt_payments >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_profiles_monthly_debt_payments", "financial_profiles", type_="check")
    op.drop_constraint("ck_profiles_monthly_savings_contribution", "financial_profiles", type_="check")
    op.drop_column("financial_profiles", "monthly_debt_payments")
    op.drop_column("financial_profiles", "monthly_savings_contribution")
