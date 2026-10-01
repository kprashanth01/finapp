"""Store versioned synthetic research experiments and measured metrics.

Revision ID: 0007_research_evaluation
Revises: 0006_private_accounts
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_research_evaluation"
down_revision = "0006_private_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluation_version", sa.String(80), nullable=False),
        sa.Column("scenario_version", sa.String(80), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("cohort_sha256", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_key", sa.String(120), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("scenario", sa.String(80), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("experiment_id", "run_key", name="uq_experiment_runs_key"),
        sa.CheckConstraint("case_count > 0", name="ck_experiment_runs_case_count"),
        sa.CheckConstraint("sample_count >= case_count", name="ck_experiment_runs_sample_count"),
        sa.CheckConstraint("scope IN ('aggregate', 'seed')", name="ck_experiment_runs_scope"),
    )
    op.create_index("ix_experiment_runs_method_scenario", "experiment_runs", ["method", "scenario"])
    op.create_table(
        "experiment_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.UniqueConstraint("run_id", "name", name="uq_experiment_metrics_run_name"),
    )
    op.create_index("ix_experiment_metrics_name", "experiment_metrics", ["name"])


def downgrade() -> None:
    op.drop_index("ix_experiment_metrics_name", table_name="experiment_metrics")
    op.drop_table("experiment_metrics")
    op.drop_index("ix_experiment_runs_method_scenario", table_name="experiment_runs")
    op.drop_table("experiment_runs")
    op.drop_table("experiments")
