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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="profile")


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
