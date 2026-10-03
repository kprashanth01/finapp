"""Save proposed loans and changed readiness assessments.

Revision ID: 0012_loan_readiness
Revises: 0011_optional_loan_balance
"""

import sqlalchemy as sa
from alembic import op

revision = '0012_loan_readiness'
down_revision = '0011_optional_loan_balance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'loan_scenarios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('loan_type', sa.String(60), nullable=False),
        sa.Column('lender_name', sa.String(100)),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('annual_interest_rate_percent', sa.Numeric(6, 2)),
        sa.Column('tenure_months', sa.Integer(), nullable=False),
        sa.Column('quoted_monthly_payment', sa.Numeric(12, 2)),
        sa.Column('credit_score', sa.Integer()),
        sa.Column('credit_history_months', sa.Integer()),
        sa.Column('credit_utilization_percent', sa.Numeric(6, 2)),
        sa.Column('income_documents_ready', sa.Boolean()),
        sa.Column('missed_payments_last_12_months', sa.Integer()),
        sa.Column('criteria', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('amount > 0 AND tenure_months BETWEEN 1 AND 480', name='ck_loan_scenario_terms'),
    )
    op.create_index('ix_loan_scenarios_user', 'loan_scenarios', ['user_id'])
    op.create_table(
        'loan_readiness_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scenario_id', sa.Integer(), sa.ForeignKey('loan_scenarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('input_fingerprint', sa.String(64), nullable=False),
        sa.Column('result_payload', sa.JSON(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_loan_readiness_snapshots_scenario_id_id', 'loan_readiness_snapshots', ['scenario_id', 'id'])


def downgrade() -> None:
    op.drop_index('ix_loan_readiness_snapshots_scenario_id_id', table_name='loan_readiness_snapshots')
    op.drop_table('loan_readiness_snapshots')
    op.drop_index('ix_loan_scenarios_user', table_name='loan_scenarios')
    op.drop_table('loan_scenarios')
