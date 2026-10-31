import json
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agent import run_agent, serialize_student, tool_update_student_progress
from app.config import settings
from app.db import Base, engine, get_db
from app.evaluation import run_evaluation
from app.guardrails import require_student, scan_user_text
from app.models import AgentLog, JobApplication, Prediction, ProgressEvent, Student, WeeklyPlan
from app.predictor import FEATURE_ORDER, load_bundle, predict_from_features, student_to_features
from app.schemas import (
    AgentRunRequest,
    ApplicationCreate,
    ProgressUpdate,
    StudentCreate,
    StudentUpdate,
    WhatIfRequest,
)
from app.seed import seed_if_empty

app = FastAPI(
    title="CareerTwin AI",
    description="Student digital twin and counterfactual career coach. Placement numbers are synthetic estimates.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    load_bundle()
    db = next(get_db())
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "ok": False})


def prediction_payload(student_id: int, result, scenario: str, row: Prediction | None = None) -> dict:
    return {
        "id": row.id if row else None,
        "student_id": student_id,
        "probability": result.probability,
        "band": result.band,
        "scenario_label": scenario,
        "factors": result.factors,
        "limitations": result.limitations,
        "is_estimate": True,
        "model_version": result.model_version,
        "created_at": row.created_at if row else datetime.utcnow(),
    }


def persist_prediction(db: Session, student: Student, result, scenario: str) -> Prediction:
    row = Prediction(
        student_id=student.id,
        probability=result.probability,
        band=result.band,
        scenario_label=scenario,
        factors_json=json.dumps(result.factors),
        limitations=result.limitations,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def plan_to_dict(plan: WeeklyPlan) -> dict:
    try:
        content = json.loads(plan.content_json)
    except json.JSONDecodeError:
        content = {"raw": plan.content_json}
    return {
        "id": plan.id,
        "student_id": plan.student_id,
        "title": plan.title,
        "content": content,
        "status": plan.status,
        "rationale": plan.rationale,
        "created_at": plan.created_at,
        "approved_at": plan.approved_at,
        "activated_at": plan.activated_at,
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_configured": bool(settings.openai_api_key.strip()),
        "model": "synthetic-logit-v1",
        "disclaimer": "Placement probabilities are synthetic estimates, not real-world validated rates.",
    }


@app.get("/api/students")
def list_students(db: Session = Depends(get_db)):
    students = db.query(Student).order_by(Student.id).all()
    return [serialize_student(s) | {"email": s.email, "updated_at": s.updated_at, "created_at": s.created_at} for s in students]


@app.get("/api/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    latest = (
        db.query(Prediction)
        .filter(Prediction.student_id == student_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    return {
        **serialize_student(student),
        "email": student.email,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        "latest_probability": latest.probability if latest else None,
        "latest_band": latest.band if latest else None,
    }


@app.post("/api/students")
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A student with this email already exists.")
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return serialize_student(student)


@app.patch("/api/students/{student_id}")
def patch_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(student, key, value)
    student.updated_at = datetime.utcnow()
    db.commit()
    return serialize_student(student)


@app.post("/api/students/{student_id}/progress")
def update_progress(student_id: int, payload: ProgressUpdate, db: Session = Depends(get_db)):
    return tool_update_student_progress(db, student_id, payload.field, payload.value, payload.note)


@app.get("/api/students/{student_id}/progress")
def list_progress(student_id: int, db: Session = Depends(get_db)):
    require_student(db.query(Student).filter(Student.id == student_id).first())
    rows = (
        db.query(ProgressEvent)
        .filter(ProgressEvent.student_id == student_id)
        .order_by(ProgressEvent.created_at.desc())
        .limit(40)
        .all()
    )
    return [
        {
            "id": r.id,
            "field": r.field,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "note": r.note,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.get("/api/students/{student_id}/applications")
def list_applications(student_id: int, db: Session = Depends(get_db)):
    require_student(db.query(Student).filter(Student.id == student_id).first())
    rows = (
        db.query(JobApplication)
        .filter(JobApplication.student_id == student_id)
        .order_by(JobApplication.created_at.desc())
        .all()
    )
    return [
        {"id": r.id, "company": r.company, "role": r.role, "status": r.status, "created_at": r.created_at}
        for r in rows
    ]


@app.post("/api/students/{student_id}/applications")
def add_application(student_id: int, body: ApplicationCreate, db: Session = Depends(get_db)):
    require_student(db.query(Student).filter(Student.id == student_id).first())
    company = (body.company or "").strip()
    role = (body.role or "").strip()
    if not company or not role:
        raise HTTPException(status_code=400, detail="Company and role are required.")
    app_row = JobApplication(
        student_id=student_id,
        company=company,
        role=role,
        status=body.status or "applied",
    )
    student = db.query(Student).filter(Student.id == student_id).first()
    student.applications_count = (student.applications_count or 0) + 1
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return {"id": app_row.id, "company": company, "role": role, "status": app_row.status, "applications_count": student.applications_count}


@app.post("/api/students/{student_id}/predict")
def predict(student_id: int, db: Session = Depends(get_db)):
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    result = predict_from_features(student_to_features(student))
    row = persist_prediction(db, student, result, "baseline")
    return prediction_payload(student.id, result, "baseline", row)


@app.get("/api/students/{student_id}/predictions")
def list_predictions(student_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Prediction)
        .filter(Prediction.student_id == student_id)
        .order_by(Prediction.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": r.id,
            "probability": r.probability,
            "band": r.band,
            "scenario_label": r.scenario_label,
            "factors": json.loads(r.factors_json),
            "limitations": r.limitations,
            "is_estimate": True,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.post("/api/students/{student_id}/what-if")
def what_if(student_id: int, body: WhatIfRequest, db: Session = Depends(get_db)):
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    base_features = student_to_features(student)
    baseline = predict_from_features(base_features)
    persist_prediction(db, student, baseline, "baseline")

    sim = dict(base_features)
    sim["mock_interviews"] += body.extra_mock_interviews
    sim["aptitude_score"] += body.aptitude_delta
    sim["english_score"] += body.english_delta
    sim["technical_score"] += body.technical_delta
    sim["attendance_pct"] += body.attendance_delta
    sim["applications_count"] += body.extra_applications
    sim["projects_count"] += body.extra_projects
    sim["internships"] += body.extra_internships
    sim["cgpa"] += body.cgpa_delta
    simulated = predict_from_features(sim)
    sim_row = persist_prediction(db, student, simulated, "what_if")

    summary = []
    mapping = [
        (body.extra_mock_interviews, "mock interviews"),
        (body.aptitude_delta, "aptitude"),
        (body.english_delta, "English"),
        (body.technical_delta, "technical score"),
        (body.attendance_delta, "attendance"),
        (body.extra_applications, "applications"),
        (body.extra_projects, "projects"),
        (body.extra_internships, "internships"),
        (body.cgpa_delta, "CGPA"),
    ]
    for value, label in mapping:
        if value:
            summary.append(f"{label}: {value:+}")
    if not summary:
        summary.append("No deltas applied — simulated equals baseline.")

    return {
        "baseline": prediction_payload(student.id, baseline, "baseline"),
        "simulated": prediction_payload(student.id, simulated, "what_if", sim_row),
        "delta_probability": round(simulated.probability - baseline.probability, 4),
        "change_summary": summary,
    }


@app.post("/api/students/{student_id}/agent")
def agent_run(student_id: int, body: AgentRunRequest, db: Session = Depends(get_db)):
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    scan_user_text(body.message, student)
    return run_agent(db, student_id, body.message, body.goal)


@app.get("/api/students/{student_id}/agent-logs")
def agent_logs(student_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(AgentLog)
        .filter(AgentLog.student_id == student_id)
        .order_by(AgentLog.created_at.desc())
        .limit(80)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "run_id": r.run_id,
                "phase": r.phase,
                "message": r.message,
                "tool_name": r.tool_name,
                "tool_input": json.loads(r.tool_input) if r.tool_input else None,
                "tool_output": json.loads(r.tool_output) if r.tool_output else None,
                "created_at": r.created_at,
            }
        )
    return out


@app.get("/api/students/{student_id}/plans")
def list_plans(student_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.student_id == student_id)
        .order_by(WeeklyPlan.created_at.desc())
        .all()
    )
    return [plan_to_dict(p) for p in rows]


@app.post("/api/plans/{plan_id}/approve")
def approve_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if plan.status not in {"pending_approval", "rejected"}:
        raise HTTPException(status_code=400, detail=f"Cannot approve a plan in status '{plan.status}'.")
    plan.status = "approved"
    plan.approved_at = datetime.utcnow()
    db.commit()
    return plan_to_dict(plan)


@app.post("/api/plans/{plan_id}/reject")
def reject_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if plan.status == "active":
        raise HTTPException(status_code=400, detail="An active plan cannot be rejected. Create a new draft instead.")
    plan.status = "rejected"
    db.commit()
    return plan_to_dict(plan)


@app.post("/api/plans/{plan_id}/activate")
def activate_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if plan.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Human approval is required before a weekly plan can be activated.",
        )
    others = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.student_id == plan.student_id, WeeklyPlan.status == "active")
        .all()
    )
    for other in others:
        other.status = "approved"
    plan.status = "active"
    plan.activated_at = datetime.utcnow()
    db.commit()
    return plan_to_dict(plan)


@app.get("/api/evaluation")
def evaluation():
    return run_evaluation()


@app.get("/api/model")
def model_info():
    bundle = load_bundle()
    return {
        "version": "synthetic-logit-v1",
        "features": FEATURE_ORDER,
        "metrics": bundle["metrics"],
        "limitations": predict_from_features({k: 50 if k != "cgpa" else 7 for k in FEATURE_ORDER}).limitations,
    }
