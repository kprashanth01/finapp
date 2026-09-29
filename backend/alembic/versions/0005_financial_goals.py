"""Add structured financial goals.

Revision ID: 0005_financial_goals
Revises: 0004_analysis_sessions
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_financial_goals"
down_revision = "0004_analysis_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("saved_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("target_amount > 0", name="ck_goals_target"),
        sa.CheckConstraint("saved_amount >= 0", name="ck_goals_saved"),
        sa.CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_goals_priority"),
    )
    op.create_index("ix_goals_user_archived", "financial_goals", ["user_id", "archived"])


def downgrade() -> None:
    op.drop_index("ix_goals_user_archived", table_name="financial_goals")
    op.drop_table("financial_goals")
