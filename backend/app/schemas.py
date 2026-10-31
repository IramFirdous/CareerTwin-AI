from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    name: str
    email: str
    year: int = 4
    branch: str
    college: str
    aptitude_score: float = Field(ge=0, le=100)
    english_score: float = Field(ge=0, le=100)
    technical_score: float = Field(ge=0, le=100)
    mock_interviews: int = Field(ge=0, le=30)
    mock_interview_avg: float = Field(ge=0, le=100)
    attendance_pct: float = Field(ge=0, le=100)
    applications_count: int = Field(ge=0, le=80)
    internships: int = Field(ge=0, le=6)
    cgpa: float = Field(ge=0, le=10)
    projects_count: int = Field(ge=0, le=20)
    certifications_count: int = Field(ge=0, le=20)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    aptitude_score: float | None = None
    english_score: float | None = None
    technical_score: float | None = None
    mock_interviews: int | None = None
    mock_interview_avg: float | None = None
    attendance_pct: float | None = None
    applications_count: int | None = None
    internships: int | None = None
    cgpa: float | None = None
    projects_count: int | None = None
    certifications_count: int | None = None


class ApplicationOut(BaseModel):
    id: int
    company: str
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentOut(StudentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    applications: list[ApplicationOut] = []

    class Config:
        from_attributes = True


class Factor(BaseModel):
    feature: str
    label: str
    value: float
    contribution: float
    direction: str
    why: str


class PredictionOut(BaseModel):
    id: int | None = None
    student_id: int
    probability: float
    band: str
    scenario_label: str
    factors: list[Factor]
    limitations: str
    is_estimate: bool = True
    model_version: str
    created_at: datetime | None = None


class WhatIfRequest(BaseModel):
    extra_mock_interviews: int = 0
    aptitude_delta: float = 0
    english_delta: float = 0
    technical_delta: float = 0
    attendance_delta: float = 0
    extra_applications: int = 0
    extra_projects: int = 0
    extra_internships: int = 0
    cgpa_delta: float = 0


class WhatIfResponse(BaseModel):
    baseline: PredictionOut
    simulated: PredictionOut
    delta_probability: float
    change_summary: list[str]


class ApplicationCreate(BaseModel):
    company: str
    role: str
    status: str = "applied"


class ProgressUpdate(BaseModel):
    field: str
    value: float
    note: str = ""


class AgentRunRequest(BaseModel):
    message: str = "Build a personalized weekly placement plan."
    goal: str = "improve_placement_readiness"


class AgentStep(BaseModel):
    phase: str
    message: str
    tool_name: str | None = None
    tool_input: Any | None = None
    tool_output: Any | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    mode: str
    steps: list[AgentStep]
    final_plan_id: int | None = None
    final_message: str
    warnings: list[str] = []


class EvalCase(BaseModel):
    id: str
    description: str
    expected: str
    predicted: str
    passed: bool
    detail: str = ""


class EvalReport(BaseModel):
    model_metrics: dict
    cases: list[EvalCase]
    case_accuracy: float
    case_precision: float | None
    case_recall: float | None
    case_f1: float | None
    notes: list[str]
