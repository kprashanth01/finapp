from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["FinancialProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profiles_user_id"),
        CheckConstraint("monthly_expenses >= 0", name="ck_profiles_monthly_expenses"),
        CheckConstraint("savings >= 0", name="ck_profiles_savings"),
        CheckConstraint("existing_debt >= 0", name="ck_profiles_existing_debt"),
        CheckConstraint("emergency_fund >= 0", name="ck_profiles_emergency_fund"),
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
    risk_tolerance: Mapped[str] = mapped_column(String(20))
    financial_goal: Mapped[str | None] = mapped_column(String(200))
    investment_horizon_years: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="profile")
