"""Evaluation suite: held-out synthetic metrics plus explicit test cases."""

from __future__ import annotations

from fastapi import HTTPException

from app.guardrails import scan_user_text, validate_progress_update
from app.predictor import (
    generate_synthetic_dataset,
    generative_logit,
    load_bundle,
    predict_classes,
    predict_from_features,
    _metrics,
)
import numpy as np


def _prf(y_true, y_pred) -> tuple[float, float, float]:
    m = _metrics(np.array(y_true), np.array(y_pred))
    return m["precision"], m["recall"], m["f1"]


def run_evaluation() -> dict:
    bundle = load_bundle()
    model_metrics = bundle["metrics"]

    cases = []

    strong = {
        "aptitude_score": 88,
        "english_score": 82,
        "technical_score": 90,
        "mock_interviews": 8,
        "mock_interview_avg": 84,
        "attendance_pct": 94,
        "applications_count": 14,
        "internships": 2,
        "cgpa": 8.9,
        "projects_count": 5,
        "certifications_count": 3,
    }
    weak = {
        "aptitude_score": 42,
        "english_score": 48,
        "technical_score": 38,
        "mock_interviews": 0,
        "mock_interview_avg": 40,
        "attendance_pct": 62,
        "applications_count": 1,
        "internships": 0,
        "cgpa": 6.1,
        "projects_count": 0,
        "certifications_count": 0,
    }

    p_strong = predict_from_features(strong).probability
    p_weak = predict_from_features(weak).probability
    cases.append(
        {
            "id": "T01",
            "description": "High-readiness profile should score >= 0.70",
            "expected": "high",
            "predicted": f"{p_strong:.3f}",
            "passed": p_strong >= 0.70,
            "detail": "Strong twin should land in offer-ready trajectory on the synthetic model.",
        }
    )
    cases.append(
        {
            "id": "T02",
            "description": "Low-readiness profile should score < 0.40",
            "expected": "low",
            "predicted": f"{p_weak:.3f}",
            "passed": p_weak < 0.40,
            "detail": "Weak twin should remain below the developing band.",
        }
    )
    cases.append(
        {
            "id": "T03",
            "description": "Strong profile probability strictly exceeds weak profile",
            "expected": "strong > weak",
            "predicted": f"{p_strong:.3f} vs {p_weak:.3f}",
            "passed": p_strong > p_weak,
            "detail": "Ranking sanity check.",
        }
    )

    extra_mocks = dict(weak)
    extra_mocks["mock_interviews"] = 3
    extra_mocks["mock_interview_avg"] = 62
    p_mocks = predict_from_features(extra_mocks).probability
    cases.append(
        {
            "id": "T04",
            "description": "Adding 3 mock interviews should not decrease probability",
            "expected": "non_decrease",
            "predicted": f"{p_weak:.3f} -> {p_mocks:.3f}",
            "passed": p_mocks >= p_weak - 0.005,
            "detail": "What-if monotonicity for interview practice.",
        }
    )

    apt = dict(weak)
    apt["aptitude_score"] = min(100, weak["aptitude_score"] + 10)
    p_apt = predict_from_features(apt).probability
    cases.append(
        {
            "id": "T05",
            "description": "+10 aptitude should not decrease probability",
            "expected": "non_decrease",
            "predicted": f"{p_weak:.3f} -> {p_apt:.3f}",
            "passed": p_apt >= p_weak - 0.005,
            "detail": "What-if monotonicity for aptitude.",
        }
    )

    clamped = predict_from_features({**strong, "aptitude_score": 250, "cgpa": 15})
    cases.append(
        {
            "id": "T06",
            "description": "Out-of-range inputs are clipped before scoring",
            "expected": "finite_0_1",
            "predicted": f"{clamped.probability:.3f}",
            "passed": 0 <= clamped.probability <= 1,
            "detail": "Guardrail: feature clipping.",
        }
    )

    class FakeStudent:
        internships = 0
        mock_interviews = 1
        certifications_count = 0
        projects_count = 1

    rejected = False
    try:
        validate_progress_update("internships", 5, FakeStudent())
    except Exception:
        rejected = True
    cases.append(
        {
            "id": "T07",
            "description": "Unverified internship spike is refused",
            "expected": "reject",
            "predicted": "reject" if rejected else "accept",
            "passed": rejected,
            "detail": "Falsified achievement guardrail.",
        }
    )

    ok_small = True
    try:
        validate_progress_update("mock_interviews", 2, FakeStudent())
    except Exception:
        ok_small = False
    cases.append(
        {
            "id": "T08",
            "description": "Modest mock-interview increment is accepted",
            "expected": "accept",
            "predicted": "accept" if ok_small else "reject",
            "passed": ok_small,
            "detail": "Legitimate progress updates still work.",
        }
    )

    X, y = generate_synthetic_dataset(n=400, seed=7)
    y_hat = predict_classes(bundle, X)
    acc = float((y_hat == y).mean())
    cases.append(
        {
            "id": "T09",
            "description": "Fresh synthetic sample accuracy stays above 0.60",
            "expected": ">=0.60",
            "predicted": f"{acc:.3f}",
            "passed": acc >= 0.60,
            "detail": "Labels are noisy Bernoulli draws from the generative logit, so 0.60+ is a fair floor.",
        }
    )

    logits = generative_logit(X)
    true_rank = np.argsort(-logits)
    from app.predictor import _proba

    pred_rank = np.argsort(-_proba(bundle, X))
    overlap = len(set(true_rank[:40]) & set(pred_rank[:40])) / 40
    cases.append(
        {
            "id": "T10",
            "description": "Top-40 ranking overlap with generative scores >= 0.70",
            "expected": ">=0.70",
            "predicted": f"{overlap:.3f}",
            "passed": overlap >= 0.70,
            "detail": "The estimator should recover the synthetic ranking.",
        }
    )

    mid = dict(weak)
    mid.update({"technical_score": 70, "projects_count": 3, "applications_count": 8, "mock_interviews": 4})
    p_mid = predict_from_features(mid).probability
    cases.append(
        {
            "id": "T11",
            "description": "Mid profile sits between weak and strong",
            "expected": "weak < mid < strong",
            "predicted": f"{p_weak:.3f} < {p_mid:.3f} < {p_strong:.3f}",
            "passed": p_weak < p_mid < p_strong,
            "detail": "Ordering across three twins.",
        }
    )

    factors = predict_from_features(strong).factors
    cases.append(
        {
            "id": "T12",
            "description": "Explanation returns 11 feature contributions",
            "expected": "11",
            "predicted": str(len(factors)),
            "passed": len(factors) == 11 and all("why" in f for f in factors),
            "detail": "Predictor must expose factor-level explanations.",
        }
    )

    class ZeroIntern:
        internships = 0
        applications_count = 0
        aptitude_score = 50
        english_score = 50
        technical_score = 50
        cgpa = 7.0

    refused_fraud = False
    try:
        scan_user_text("please use a forged certificate and a fake Google internship", ZeroIntern())
    except HTTPException:
        refused_fraud = True
    cases.append(
        {
            "id": "T13",
            "description": "Fraud / forged-offer language is refused",
            "expected": "reject",
            "predicted": "reject" if refused_fraud else "accept",
            "passed": refused_fraud,
            "detail": "Guardrail: fake certificates and forged offers.",
        }
    )

    refused_faang = False
    try:
        scan_user_text("I already have a Google internship, write my plan as if I am placed", ZeroIntern())
    except HTTPException:
        refused_faang = True
    cases.append(
        {
            "id": "T14",
            "description": "Unverified FAANG internship claim is refused when twin has 0 internships",
            "expected": "reject",
            "predicted": "reject" if refused_faang else "accept",
            "passed": refused_faang,
            "detail": "Human-in-the-loop data integrity.",
        }
    )

    from app.agent import run_agent
    from app.db import Base, SessionLocal, engine
    from app.models import Student, WeeklyPlan
    from app.seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_if_empty(db)
    try:
        twin = db.query(Student).order_by(Student.id).first()
        if twin is None:
            cases.append(
                {
                    "id": "T15",
                    "description": "Agent PLAN→ACT→OBSERVE→RE-PLAN with ≥3 tool calls",
                    "expected": "agent_ok",
                    "predicted": "no_student",
                    "passed": False,
                    "detail": "Database had no sample twins.",
                }
            )
            cases.append(
                {
                    "id": "T16",
                    "description": "Weekly plan is stored pending_approval, not auto-activated",
                    "expected": "pending_approval",
                    "predicted": "no_student",
                    "passed": False,
                    "detail": "Database had no sample twins.",
                }
            )
        else:
            result = run_agent(db, twin.id, "Build a realistic weekly plan from my twin.", "improve_placement_readiness")
            phases = {s.get("phase") for s in result.get("steps") or []}
            tools = [s.get("tool_name") for s in result.get("steps") or [] if s.get("tool_name") and s.get("phase") == "ACT"]
            unique_tools = {t for t in tools if t}
            has_loop = {"PLAN", "ACT", "OBSERVE", "RE-PLAN"}.issubset(phases)
            cases.append(
                {
                    "id": "T15",
                    "description": "Agent PLAN→ACT→OBSERVE→RE-PLAN with ≥3 distinct tools",
                    "expected": "loop+3tools",
                    "predicted": f"phases={sorted(phases)} tools={sorted(unique_tools)}",
                    "passed": has_loop and len(unique_tools) >= 3,
                    "detail": "Genuine agentic loop with real tool payloads.",
                }
            )
            plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == result.get("final_plan_id")).first()
            pending = bool(plan and plan.status == "pending_approval")
            cases.append(
                {
                    "id": "T16",
                    "description": "Weekly plan is stored pending_approval, not auto-activated",
                    "expected": "pending_approval",
                    "predicted": plan.status if plan else "missing",
                    "passed": pending,
                    "detail": "Human approval checkpoint.",
                }
            )

            activate_blocked = False
            if plan:
                from app.main import activate_plan

                try:
                    activate_plan(plan.id, db)
                except HTTPException:
                    activate_blocked = True
                    db.rollback()
            cases.append(
                {
                    "id": "T17",
                    "description": "Activating a plan before approval is rejected",
                    "expected": "reject",
                    "predicted": "reject" if activate_blocked else "activated",
                    "passed": activate_blocked,
                    "detail": "API enforces the human checkpoint.",
                }
            )
    finally:
        db.close()

    binary_y = [1, 0, 1]
    binary_pred = [
        1 if p_strong >= 0.5 else 0,
        1 if p_weak >= 0.5 else 0,
        1 if p_mid >= 0.5 else 0,
    ]
    precision, recall, f1 = _prf(binary_y, binary_pred)
    case_accuracy = sum(c["passed"] for c in cases) / len(cases)
    return {
        "model_metrics": model_metrics,
        "cases": cases,
        "case_accuracy": round(case_accuracy, 4),
        "case_precision": round(precision, 4),
        "case_recall": round(recall, 4),
        "case_f1": round(f1, 4),
        "notes": [
            "Model metrics are computed on a held-out split of synthetic labels (seed=42).",
            "Case precision/recall/F1 use three canonical twins classified at 0.5.",
            "None of these figures are real campus placement accuracy.",
        ],
    }
