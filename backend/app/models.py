from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("age IS NULL OR age BETWEEN 0 AND 120", name="ck_users_age"),
        CheckConstraint("monthly_income >= 0", name="ck_users_monthly_income"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    age: Mapped[int | None]
    occupation: Mapped[str | None] = mapped_column(String(100))
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    legacy_claim_digest: Mapped[str | None] = mapped_column(String(64))
    legacy_claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["FinancialProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    analysis_sessions: Mapped[list["AnalysisSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list["FinancialGoal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    financial_months: Mapped[list["FinancialMonth"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recurring_expenses: Mapped[list["RecurringExpense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    loans: Mapped[list["Loan"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    planned_expenses: Mapped[list["PlannedExpense"]] = relationship(back_populates="user", cascade="all, delete-orphan")


Index("uq_users_email_lower", func.lower(User.email), unique=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="auth_sessions")


class AuthFailure(Base):
    __tablename__ = "auth_failures"
    __table_args__ = (Index("ix_auth_failures_lookup", "email_digest", "ip_digest", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email_digest: Mapped[str] = mapped_column(String(64))
    ip_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profiles_user_id"),
        CheckConstraint("monthly_expenses >= 0", name="ck_profiles_monthly_expenses"),
        CheckConstraint("savings >= 0", name="ck_profiles_savings"),
        CheckConstraint("existing_debt >= 0", name="ck_profiles_existing_debt"),
        CheckConstraint("emergency_fund >= 0", name="ck_profiles_emergency_fund"),
        CheckConstraint(
            "monthly_savings_contribution IS NULL OR monthly_savings_contribution >= 0",
            name="ck_profiles_monthly_savings_contribution",
        ),
        CheckConstraint(
            "monthly_debt_payments IS NULL OR monthly_debt_payments >= 0",
            name="ck_profiles_monthly_debt_payments",
        ),
        CheckConstraint(
            "monthly_debt_payments IS NULL OR monthly_debt_payments <= monthly_expenses",
            name="ck_profiles_debt_payments_within_expenses",
        ),
        CheckConstraint(
            "risk_tolerance IN ('conservative', 'moderate', 'aggressive')",
            name="ck_profiles_risk_tolerance",
        ),
        CheckConstraint(
            "investment_horizon_years IS NULL OR investment_horizon_years BETWEEN 0 AND 80",
            name="ck_profiles_horizon",
        ),
        CheckConstraint(
            "income_pattern IS NULL OR income_pattern IN ('stable', 'variable', 'mixed')",
            name="ck_profiles_income_pattern",
        ),
        CheckConstraint(
            "guaranteed_monthly_income IS NULL OR guaranteed_monthly_income >= 0",
            name="ck_profiles_guaranteed_income",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    savings: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    existing_debt: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    emergency_fund: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monthly_savings_contribution: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    monthly_debt_payments: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    risk_tolerance: Mapped[str] = mapped_column(String(20))
    financial_goal: Mapped[str | None] = mapped_column(String(200))
    investment_horizon_years: Mapped[int | None]
    income_pattern: Mapped[str | None] = mapped_column(String(20))
    guaranteed_monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="profile")


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"
    __table_args__ = (
        CheckConstraint("monthly_amount > 0", name="ck_recurring_expense_amount"),
        CheckConstraint("category IN ('essential_fixed', 'essential_variable', 'discretionary')", name="ck_recurring_expense_category"),
        Index("ix_recurring_expenses_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(20))
    user: Mapped[User] = relationship(back_populates="recurring_expenses")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("(remaining_balance IS NULL OR remaining_balance >= 0) AND (monthly_payment IS NULL OR monthly_payment >= 0)", name="ck_loans_amounts"),
        CheckConstraint("annual_interest_rate_percent IS NULL OR annual_interest_rate_percent >= 0", name="ck_loans_apr"),
        CheckConstraint("new_annual_interest_rate_percent IS NULL OR new_annual_interest_rate_percent >= 0", name="ck_loans_new_apr"),
        CheckConstraint("payment_day IS NULL OR payment_day BETWEEN 1 AND 31", name="ck_loans_payment_day"),
        CheckConstraint("(rate_change_date IS NULL) = (new_annual_interest_rate_percent IS NULL)", name="ck_loans_rate_change_pair"),
        Index("ix_loans_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    loan_type: Mapped[str | None] = mapped_column(String(40))
    remaining_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    annual_interest_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    payment_day: Mapped[int | None]
    rate_change_date: Mapped[date | None] = mapped_column(Date)
    new_annual_interest_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    user: Mapped[User] = relationship(back_populates="loans")


class PlannedExpense(Base):
    __tablename__ = "planned_expenses"
    __table_args__ = (
        CheckConstraint("estimated_amount > 0 AND (amount_reserved IS NULL OR (amount_reserved >= 0 AND amount_reserved <= estimated_amount))", name="ck_planned_expense_amounts"),
        Index("ix_planned_expenses_user_due", "user_id", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_reserved: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    due_date: Mapped[date] = mapped_column(Date)
    is_essential: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    user: Mapped[User] = relationship(back_populates="planned_expenses")


class FinancialMonth(Base):
    """An account owner's entered month, separate from the editable current profile."""

    __tablename__ = "financial_months"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_financial_month_user_period"),
        Index("ix_financial_month_user_period", "user_id", "period"),
        CheckConstraint("monthly_income >= 0 AND monthly_expenses >= 0 AND fixed_expenses >= 0", name="ck_month_nonnegative_flow"),
        CheckConstraint("scheduled_emi >= 0 AND paid_emi >= 0 AND paid_emi <= scheduled_emi", name="ck_month_emi"),
        CheckConstraint("fixed_expenses + scheduled_emi <= monthly_expenses", name="ck_month_expense_parts"),
        CheckConstraint("savings >= 0 AND emergency_fund >= 0 AND emergency_fund <= savings", name="ck_month_reserve"),
        CheckConstraint("outstanding_debt >= 0 AND unfunded_expenses >= 0", name="ck_month_debt_unfunded"),
        CheckConstraint("risk_tolerance IN ('conservative', 'moderate', 'aggressive')", name="ck_month_risk"),
        CheckConstraint("investment_horizon_years BETWEEN 0 AND 80", name="ck_month_horizon"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    period: Mapped[date] = mapped_column(Date)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fixed_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    scheduled_emi: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_emi: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    savings: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    emergency_fund: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    outstanding_debt: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unfunded_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    risk_tolerance: Mapped[str] = mapped_column(String(20))
    investment_horizon_years: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="financial_months")


class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_goals_target"),
        CheckConstraint("saved_amount >= 0", name="ck_goals_saved"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_goals_priority"),
        Index("ix_goals_user_archived", "user_id", "archived"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    saved_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    target_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(10))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user: Mapped[User] = relationship(back_populates="goals")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    __table_args__ = (Index("ix_analysis_sessions_user_id_id", "user_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(30))
    rule_version: Mapped[str] = mapped_column(String(40))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    result_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="analysis_sessions")


class Experiment(Base):
    """One immutable, synthetic research report; separate from account history."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    evaluation_version: Mapped[str] = mapped_column(String(80))
    scenario_version: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(80))
    cohort_sha256: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    runs: Mapped[list["ExperimentRun"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")


class ExperimentRun(Base):
    """A method on a cohort or scenario segment, pooled or at one seed."""

    __tablename__ = "experiment_runs"
    __table_args__ = (
        UniqueConstraint("experiment_id", "run_key", name="uq_experiment_runs_key"),
        CheckConstraint("case_count > 0", name="ck_experiment_runs_case_count"),
        CheckConstraint("sample_count >= case_count", name="ck_experiment_runs_sample_count"),
        CheckConstraint("scope IN ('aggregate', 'seed')", name="ck_experiment_runs_scope"),
        Index("ix_experiment_runs_method_scenario", "method", "scenario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    run_key: Mapped[str] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(String(40))
    scenario: Mapped[str] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int | None]
    case_count: Mapped[int]
    sample_count: Mapped[int]
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="runs")
    metrics: Mapped[list["ExperimentMetric"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ExperimentMetric(Base):
    """A measured scalar, with absent measurements omitted instead of zeroed."""

    __tablename__ = "experiment_metrics"
    __table_args__ = (
        UniqueConstraint("run_id", "name", name="uq_experiment_metrics_run_name"),
        Index("ix_experiment_metrics_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("experiment_runs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6))

    run: Mapped[ExperimentRun] = relationship(back_populates="metrics")
