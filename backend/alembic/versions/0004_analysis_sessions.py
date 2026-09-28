"""Persist immutable advisory sessions.

Revision ID: 0004_analysis_sessions
Revises: 0003_debt_payment_limit
"""

import sqlalchemy as sa
from alembic import op


revision = "0004_analysis_sessions"
down_revision = "0003_debt_payment_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("rule_version", sa.String(length=40), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analysis_sessions_user_id_id", "analysis_sessions", ["user_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_sessions_user_id_id", table_name="analysis_sessions")
    op.drop_table("analysis_sessions")
