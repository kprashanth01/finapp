"""Add credentials, claim metadata, and revocable browser sessions.

Revision ID: 0006_private_accounts
Revises: 0005_financial_goals
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_private_accounts"
down_revision = "0005_financial_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("legacy_claim_digest", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("legacy_claim_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_sessions_user", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_digest", "auth_sessions", ["token_digest"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_token_digest", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_column("users", "legacy_claim_expires_at")
    op.drop_column("users", "legacy_claim_digest")
    op.drop_column("users", "password_hash")
