"""Create users and financial profiles.

Revision ID: 0001_users_profiles
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_users_profiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("occupation", sa.String(length=100), nullable=True),
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("age IS NULL OR age BETWEEN 0 AND 120", name="ck_users_age"),
        sa.CheckConstraint("monthly_income >= 0", name="ck_users_monthly_income"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monthly_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("savings", sa.Numeric(12, 2), nullable=False),
        sa.Column("existing_debt", sa.Numeric(12, 2), nullable=False),
        sa.Column("emergency_fund", sa.Numeric(12, 2), nullable=False),
        sa.Column("risk_tolerance", sa.String(length=20), nullable=False),
        sa.Column("financial_goal", sa.String(length=200), nullable=True),
        sa.Column("investment_horizon_years", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_expenses >= 0", name="ck_profiles_monthly_expenses"),
        sa.CheckConstraint("savings >= 0", name="ck_profiles_savings"),
        sa.CheckConstraint("existing_debt >= 0", name="ck_profiles_existing_debt"),
        sa.CheckConstraint("emergency_fund >= 0", name="ck_profiles_emergency_fund"),
        sa.CheckConstraint(
            "risk_tolerance IN ('conservative', 'moderate', 'aggressive')",
            name="ck_profiles_risk_tolerance",
        ),
        sa.CheckConstraint(
            "investment_horizon_years IS NULL OR investment_horizon_years BETWEEN 0 AND 80",
            name="ck_profiles_horizon",
        ),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )


def downgrade() -> None:
    op.drop_table("financial_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
