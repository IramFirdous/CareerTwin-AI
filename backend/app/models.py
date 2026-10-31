from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer)
    branch: Mapped[str] = mapped_column(String(80))
    college: Mapped[str] = mapped_column(String(160))
    aptitude_score: Mapped[float] = mapped_column(Float)
    english_score: Mapped[float] = mapped_column(Float)
    technical_score: Mapped[float] = mapped_column(Float)
    mock_interviews: Mapped[int] = mapped_column(Integer)
    mock_interview_avg: Mapped[float] = mapped_column(Float)
    attendance_pct: Mapped[float] = mapped_column(Float)
    applications_count: Mapped[int] = mapped_column(Integer)
    internships: Mapped[int] = mapped_column(Integer)
    cgpa: Mapped[float] = mapped_column(Float)
    projects_count: Mapped[int] = mapped_column(Integer)
    certifications_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications: Mapped[list["JobApplication"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    plans: Mapped[list["WeeklyPlan"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    logs: Mapped[list["AgentLog"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    progress: Mapped[list["ProgressEvent"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    company: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="applied")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="applications")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    probability: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(40))
    scenario_label: Mapped[str] = mapped_column(String(80), default="baseline")
    factors_json: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="predictions")


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    title: Mapped[str] = mapped_column(String(200))
    content_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending_approval")
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped[Student] = relationship(back_populates="plans")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    phase: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tool_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="logs")


class ProgressEvent(Base):
    __tablename__ = "progress_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    field: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str] = mapped_column(String(80))
    new_value: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="progress")
