import datetime as dt
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now():
    return dt.datetime.utcnow()


class Dealership(Base):
    __tablename__ = "dealerships"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="سایپا مشایخ کد 3299")
    code: Mapped[str] = mapped_column(String(50), default="3299")

    surveys: Mapped[list["Survey"]] = relationship(back_populates="dealership")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="staff")  # admin | staff
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(30), index=True)
    national_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_plate: Mapped[str | None] = mapped_column(String(30), nullable=True)

    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # مرد/زن
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

    surveys: Mapped[list["Survey"]] = relationship(back_populates="customer")


class OfficialQuestion(Base):
    """Mirrors app.question_bank.OFFICIAL_QUESTIONS for FK integrity / auditability."""
    __tablename__ = "official_questions"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    qtype: Mapped[str] = mapped_column(String(20))
    short_label: Mapped[str] = mapped_column(String(100))


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"))
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    survey_date: Mapped[dt.date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default="direct_call")  # direct_call | company_import

    csi: Mapped[float | None] = mapped_column(Float, nullable=True)
    csat: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_low_score: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="surveys")
    dealership: Mapped["Dealership"] = relationship(back_populates="surveys")
    staff: Mapped["User | None"] = relationship(foreign_keys=[staff_id])
    answers: Mapped[list["SurveyAnswer"]] = relationship(back_populates="survey", cascade="all, delete-orphan")
    internal_followup: Mapped["InternalFollowUp | None"] = relationship(
        back_populates="survey", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("customer_id", "survey_date", "source", name="uq_survey_customer_date_source"),)


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"))
    question_code: Mapped[str] = mapped_column(ForeignKey("official_questions.code"))

    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)   # 0-10 scores
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)         # choice / free text
    value_bool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)     # yes/no
    value_datetime: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)  # Q5

    survey: Mapped["Survey"] = relationship(back_populates="answers")

    __table_args__ = (UniqueConstraint("survey_id", "question_code", name="uq_answer_survey_question"),)


class InternalFollowUp(Base):
    """Internal dealership data captured when a survey triggers a low-score flow.
    Kept strictly separate from official SurveyAnswer records."""
    __tablename__ = "internal_followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), unique=True)

    main_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_actionable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    action_taken_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    needs_followup: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    followup_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    followup_result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    followup_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    survey: Mapped["Survey"] = relationship(back_populates="internal_followup")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    problem: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(150))
    deadline: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    related_question_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    related_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    kpi_name: Mapped[str] = mapped_column(String(150))
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="در حال بررسی")
    # در حال بررسی | در حال اجرا | تکمیل شده | لغو شده

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    results: Mapped[list["ActionFollowUp"]] = relationship(back_populates="action", cascade="all, delete-orphan")


class ActionFollowUp(Base):
    __tablename__ = "action_followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id"))
    measured_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    measured_value: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

    action: Mapped["CorrectiveAction"] = relationship(back_populates="results")


class MonthlyCompanyResult(Base):
    """Official company-provided monthly results, entered/imported by management."""
    __tablename__ = "monthly_company_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    year_month: Mapped[str] = mapped_column(String(7), index=True)  # "1404-05"
    csi: Mapped[float | None] = mapped_column(Float, nullable=True)
    csat: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_code: Mapped[str | None] = mapped_column(String(10), nullable=True)  # null = overall row
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("year_month", "question_code", name="uq_company_result_month_question"),
    )
