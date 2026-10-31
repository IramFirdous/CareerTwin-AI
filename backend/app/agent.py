"""PLAN → ACT → OBSERVE → RE-PLAN career agent with real tool calls."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.guardrails import require_student, scan_user_text, validate_progress_update
from app.models import AgentLog, Prediction, Student, WeeklyPlan
from app.predictor import predict_from_features, student_to_features

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_profile",
            "description": "Load the student's digital twin: scores, attendance, applications, internships.",
            "parameters": {
                "type": "object",
                "properties": {"student_id": {"type": "integer"}},
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_placement_prediction",
            "description": "Run the synthetic placement estimator and persist the result.",
            "parameters": {
                "type": "object",
                "properties": {"student_id": {"type": "integer"}},
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_what_if",
            "description": "Counterfactual placement estimate after hypothetical skill or activity changes. Does not mutate the twin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "integer"},
                    "extra_mock_interviews": {"type": "integer"},
                    "aptitude_delta": {"type": "number"},
                    "english_delta": {"type": "number"},
                    "technical_delta": {"type": "number"},
                    "extra_applications": {"type": "integer"},
                    "extra_projects": {"type": "integer"},
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_weekly_plan",
            "description": "Store a weekly plan as pending_approval. Never auto-activate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "string"},
                                "focus": {"type": "string"},
                                "tasks": {"type": "array", "items": {"type": "string"}},
                                "minutes": {"type": "integer"},
                            },
                        },
                    },
                },
                "required": ["student_id", "title", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_student_progress",
            "description": "Apply a modest verified progress update to the digital twin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "integer"},
                    "field": {"type": "string"},
                    "value": {"type": "number"},
                    "note": {"type": "string"},
                },
                "required": ["student_id", "field", "value"],
            },
        },
    },
]


def _log(db: Session, student_id: int | None, run_id: str, phase: str, message: str, **kwargs):
    row = AgentLog(
        student_id=student_id,
        run_id=run_id,
        phase=phase,
        message=message,
        tool_name=kwargs.get("tool_name"),
        tool_input=json.dumps(kwargs.get("tool_input")) if kwargs.get("tool_input") is not None else None,
        tool_output=json.dumps(kwargs.get("tool_output")) if kwargs.get("tool_output") is not None else None,
    )
    db.add(row)
    db.commit()
    return {
        "phase": phase,
        "message": message,
        "tool_name": kwargs.get("tool_name"),
        "tool_input": kwargs.get("tool_input"),
        "tool_output": kwargs.get("tool_output"),
    }


def serialize_student(student: Student) -> dict:
    return {
        "id": student.id,
        "name": student.name,
        "year": student.year,
        "branch": student.branch,
        "college": student.college,
        "aptitude_score": student.aptitude_score,
        "english_score": student.english_score,
        "technical_score": student.technical_score,
        "mock_interviews": student.mock_interviews,
        "mock_interview_avg": student.mock_interview_avg,
        "attendance_pct": student.attendance_pct,
        "applications_count": student.applications_count,
        "internships": student.internships,
        "cgpa": student.cgpa,
        "projects_count": student.projects_count,
        "certifications_count": student.certifications_count,
        "applications": [
            {"company": a.company, "role": a.role, "status": a.status} for a in student.applications
        ],
    }


def tool_get_student_profile(db: Session, student_id: int) -> dict:
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    return serialize_student(student)


def tool_run_placement_prediction(db: Session, student_id: int) -> dict:
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    result = predict_from_features(student_to_features(student))
    row = Prediction(
        student_id=student.id,
        probability=result.probability,
        band=result.band,
        scenario_label="agent_baseline",
        factors_json=json.dumps(result.factors),
        limitations=result.limitations,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "prediction_id": row.id,
        "probability": result.probability,
        "band": result.band,
        "is_estimate": True,
        "model_version": result.model_version,
        "top_factors": result.factors[:5],
        "limitations": result.limitations,
    }


def tool_simulate_what_if(db: Session, student_id: int, **deltas) -> dict:
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    base = student_to_features(student)
    baseline = predict_from_features(base)
    sim = dict(base)
    sim["mock_interviews"] += int(deltas.get("extra_mock_interviews") or 0)
    sim["aptitude_score"] += float(deltas.get("aptitude_delta") or 0)
    sim["english_score"] += float(deltas.get("english_delta") or 0)
    sim["technical_score"] += float(deltas.get("technical_delta") or 0)
    sim["attendance_pct"] += float(deltas.get("attendance_delta") or 0)
    sim["applications_count"] += int(deltas.get("extra_applications") or 0)
    sim["projects_count"] += int(deltas.get("extra_projects") or 0)
    sim["internships"] += int(deltas.get("extra_internships") or 0)
    sim["cgpa"] += float(deltas.get("cgpa_delta") or 0)
    simulated = predict_from_features(sim)
    return {
        "baseline_probability": baseline.probability,
        "simulated_probability": simulated.probability,
        "delta_probability": round(simulated.probability - baseline.probability, 4),
        "baseline_band": baseline.band,
        "simulated_band": simulated.band,
        "is_estimate": True,
        "note": "Counterfactual only — the digital twin was not mutated.",
    }


def tool_save_weekly_plan(db: Session, student_id: int, title: str, days: list, rationale: str = "") -> dict:
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    if not days or len(days) < 3:
        raise ValueError("A weekly plan must include at least 3 days of work.")
    plan = WeeklyPlan(
        student_id=student.id,
        title=title[:200],
        content_json=json.dumps({"days": days}),
        status="pending_approval",
        rationale=rationale or "Generated by CareerTwin agent. Requires student approval before activation.",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {
        "plan_id": plan.id,
        "status": plan.status,
        "title": plan.title,
        "note": "Saved as pending_approval. The student must approve before it can be activated.",
    }


def tool_update_student_progress(db: Session, student_id: int, field: str, value: float, note: str = "") -> dict:
    from app.models import ProgressEvent

    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    field, numeric = validate_progress_update(field, value, student)
    old = getattr(student, field)
    if field in {"mock_interviews", "applications_count", "internships", "projects_count", "certifications_count"}:
        setattr(student, field, int(numeric))
    else:
        setattr(student, field, numeric)
    student.updated_at = datetime.utcnow()
    db.add(
        ProgressEvent(
            student_id=student.id,
            field=field,
            old_value=str(old),
            new_value=str(numeric),
            note=note,
        )
    )
    db.commit()
    return {"field": field, "old_value": old, "new_value": numeric, "note": note}


TOOL_IMPL: dict[str, Callable] = {
    "get_student_profile": lambda db, **kw: tool_get_student_profile(db, int(kw["student_id"])),
    "run_placement_prediction": lambda db, **kw: tool_run_placement_prediction(db, int(kw["student_id"])),
    "simulate_what_if": lambda db, **kw: tool_simulate_what_if(db, **kw),
    "save_weekly_plan": lambda db, **kw: tool_save_weekly_plan(
        db,
        int(kw["student_id"]),
        kw.get("title", "Weekly plan"),
        kw.get("days", []),
        kw.get("rationale", ""),
    ),
    "update_student_progress": lambda db, **kw: tool_update_student_progress(
        db, int(kw["student_id"]), kw["field"], kw["value"], kw.get("note", "")
    ),
}


def execute_tool(db: Session, name: str, arguments: dict) -> dict:
    if name not in TOOL_IMPL:
        return {"error": f"Unknown tool {name}"}
    try:
        return {"ok": True, "result": TOOL_IMPL[name](db, **arguments)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _heuristic_plan(profile: dict, prediction: dict) -> dict:
    holds = [f for f in prediction.get("top_factors", []) if f.get("direction") == "holds back"]
    names = {f["feature"] for f in holds[:3]}
    days = []
    catalog = [
        ("Monday", "Aptitude drills", ["30 timed quantitative questions", "Review wrong answers with formulas"], 50),
        ("Tuesday", "Data structures", ["Implement 2 array/hash problems", "Write complexity notes"], 55),
        ("Wednesday", "English + communication", ["Record a 3-minute intro", "Revise 15 grammar items"], 40),
        ("Thursday", "Mock interview", ["One peer or recorded mock", "Score yourself on STAR stories"], 60),
        ("Friday", "Project polish", ["Ship one README improvement", "Add a demo GIF or test"], 50),
        ("Saturday", "Applications", ["Apply to 3 roles that match current skills", "Track each in the twin"], 45),
        ("Sunday", "Review", ["Re-run predictor", "Note one metric that moved"], 30),
    ]
    if "mock_interviews" in names:
        catalog[3] = (
            "Thursday",
            "Interview reps",
            ["Complete 1 additional mock interview", "Rewrite 2 behavioral answers"],
            70,
        )
    if "technical_score" in names:
        catalog[1] = (
            "Tuesday",
            "Core CS recovery",
            ["1 easy + 1 medium DSA problem", "Revise OOP or DBMS flashcards"],
            65,
        )
    if "applications_count" in names:
        catalog[5] = (
            "Saturday",
            "Pipeline building",
            ["Submit 5 tailored applications", "Ask one alumni for a referral conversation"],
            60,
        )
    for day, focus, tasks, minutes in catalog:
        days.append({"day": day, "focus": focus, "tasks": tasks, "minutes": minutes})
    title = f"7-day placement sprint for {profile.get('name', 'student')}"
    rationale = (
        f"Estimate {prediction.get('probability', 0):.0%} ({prediction.get('band')}). "
        "Plan targets the weakest synthetic factors. Student approval is required before activation."
    )
    return {"title": title, "days": days, "rationale": rationale}


def _llm_available() -> bool:
    return bool(settings.openai_api_key.strip())


def _chat(messages: list[dict], tools: list | None = None) -> dict:
    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    with httpx.Client(timeout=45.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]


def run_agent(db: Session, student_id: int, user_message: str, goal: str) -> dict:
    run_id = uuid.uuid4().hex[:12]
    steps: list[dict] = []
    student = require_student(db.query(Student).filter(Student.id == student_id).first())
    scan = scan_user_text(user_message, student)
    warnings = list(scan.get("warnings") or [])

    plan_text = (
        "PLAN: 1) Load digital twin with get_student_profile. "
        "2) Score with run_placement_prediction. "
        "3) Simulate a modest what-if (+3 mocks, +10 aptitude). "
        "4) OBSERVE which factors and which scenario lift the estimate. "
        "5) RE-PLAN a 7-day schedule from those observations. "
        "6) Persist with save_weekly_plan as pending_approval (never auto-activate)."
    )
    steps.append(_log(db, student_id, run_id, "PLAN", plan_text))

    final_plan_id = None
    mode = "llm_tools" if _llm_available() else "deterministic_fallback"

    if not _llm_available():
        warnings.append(
            "OPENAI_API_KEY is not set. Using the labelled deterministic agent fallback. Tools still run for real."
        )
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "ACT",
                "Calling get_student_profile",
                tool_name="get_student_profile",
                tool_input={"student_id": student_id},
            )
        )
        profile_res = execute_tool(db, "get_student_profile", {"student_id": student_id})
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "OBSERVE",
                "Received digital twin snapshot.",
                tool_name="get_student_profile",
                tool_input={"student_id": student_id},
                tool_output=profile_res,
            )
        )

        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "ACT",
                "Calling run_placement_prediction",
                tool_name="run_placement_prediction",
                tool_input={"student_id": student_id},
            )
        )
        pred_res = execute_tool(db, "run_placement_prediction", {"student_id": student_id})
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "OBSERVE",
                "Received synthetic placement estimate and factor list.",
                tool_name="run_placement_prediction",
                tool_input={"student_id": student_id},
                tool_output=pred_res,
            )
        )

        profile = profile_res.get("result") or {}
        prediction = pred_res.get("result") or {}

        what_args = {
            "student_id": student_id,
            "extra_mock_interviews": 3,
            "aptitude_delta": 10,
            "extra_applications": 4,
        }
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "ACT",
                "Calling simulate_what_if",
                tool_name="simulate_what_if",
                tool_input=what_args,
            )
        )
        what_res = execute_tool(db, "simulate_what_if", what_args)
        lift = (what_res.get("result") or {}).get("delta_probability")
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "OBSERVE",
                f"What-if lift {lift}. Weakest factors will drive the weekly plan.",
                tool_name="simulate_what_if",
                tool_input=what_args,
                tool_output=what_res,
            )
        )

        replan = (
            f"RE-PLAN: Baseline estimate {prediction.get('probability')}. "
            f"Counterfactual lift {lift}. Build a 7-day plan that attacks the weakest factors, "
            "keep claims conservative, and save only as pending_approval."
        )
        steps.append(_log(db, student_id, run_id, "RE-PLAN", replan))

        draft = _heuristic_plan(profile, prediction)
        save_args = {"student_id": student_id, **draft}
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "ACT",
                "Calling save_weekly_plan",
                tool_name="save_weekly_plan",
                tool_input=save_args,
            )
        )
        save_res = execute_tool(db, "save_weekly_plan", save_args)
        steps.append(
            _log(
                db,
                student_id,
                run_id,
                "OBSERVE",
                "Weekly plan stored. Waiting for human approval.",
                tool_name="save_weekly_plan",
                tool_input=save_args,
                tool_output=save_res,
            )
        )
        if save_res.get("ok"):
            final_plan_id = save_res["result"]["plan_id"]
        final_message = (
            f"[Deterministic fallback] {draft['rationale']} Plan #{final_plan_id} is pending your approval."
        )
        steps.append(_log(db, student_id, run_id, "DONE", final_message))
        return {
            "run_id": run_id,
            "mode": mode,
            "steps": steps,
            "final_plan_id": final_plan_id,
            "final_message": final_message,
            "warnings": warnings,
        }

    system = (
        "You are CareerTwin, a campus placement coach. Follow PLAN → ACT → OBSERVE → RE-PLAN. "
        "You must call tools; do not invent profile numbers. "
        "Never claim a plan is active. save_weekly_plan always stores pending_approval. "
        "Estimates come from a synthetic model — say so. Refuse fake internships or forged certificates. "
        "After observing prediction factors, call simulate_what_if, then re-plan and save a 7-day plan."
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Student id={student_id}. Goal={goal}. Request={user_message}. "
                "Load the twin, predict, then save a weekly plan."
            ),
        },
    ]

    try:
        for _ in range(6):
            assistant = _chat(messages, TOOL_SPECS)
            messages.append(assistant)
            tool_calls = assistant.get("tool_calls") or []
            if not tool_calls:
                content = assistant.get("content") or ""
                steps.append(_log(db, student_id, run_id, "RE-PLAN", content[:2000] or "Model returned no tool calls."))
                break
            for call in tool_calls:
                fn = call["function"]["name"]
                raw_args = call["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
                args.setdefault("student_id", student_id)
                steps.append(
                    _log(
                        db,
                        student_id,
                        run_id,
                        "ACT",
                        f"LLM requested {fn}",
                        tool_name=fn,
                        tool_input=args,
                    )
                )
                result = execute_tool(db, fn, args)
                steps.append(
                    _log(
                        db,
                        student_id,
                        run_id,
                        "OBSERVE",
                        f"Tool {fn} returned.",
                        tool_name=fn,
                        tool_input=args,
                        tool_output=result,
                    )
                )
                if fn == "save_weekly_plan" and result.get("ok"):
                    final_plan_id = result["result"].get("plan_id")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result),
                    }
                )
        if final_plan_id is None:
            steps.append(_log(db, student_id, run_id, "RE-PLAN", "Model did not save a plan; storing a conservative draft."))
            profile = tool_get_student_profile(db, student_id)
            pred = tool_run_placement_prediction(db, student_id)
            draft = _heuristic_plan(profile, pred)
            save_res = execute_tool(db, "save_weekly_plan", {"student_id": student_id, **draft})
            steps.append(
                _log(
                    db,
                    student_id,
                    run_id,
                    "ACT",
                    "Fallback save_weekly_plan",
                    tool_name="save_weekly_plan",
                    tool_input=draft,
                    tool_output=save_res,
                )
            )
            if save_res.get("ok"):
                final_plan_id = save_res["result"]["plan_id"]
        final_message = (
            f"Agent finished in LLM tool-calling mode. Weekly plan #{final_plan_id} is pending approval."
        )
        steps.append(_log(db, student_id, run_id, "DONE", final_message))
    except Exception as exc:
        warnings.append(f"LLM call failed ({exc}). Switching to deterministic fallback.")
        return run_agent_fallback_only(db, student_id, user_message, goal, run_id, steps, warnings)

    return {
        "run_id": run_id,
        "mode": mode,
        "steps": steps,
        "final_plan_id": final_plan_id,
        "final_message": final_message,
        "warnings": warnings,
    }


def run_agent_fallback_only(db, student_id, user_message, goal, run_id, steps, warnings):
    """Used when an LLM request errors mid-run; still completes with real tools."""
    profile_res = execute_tool(db, "get_student_profile", {"student_id": student_id})
    pred_res = execute_tool(db, "run_placement_prediction", {"student_id": student_id})
    execute_tool(
        db,
        "simulate_what_if",
        {"student_id": student_id, "extra_mock_interviews": 3, "aptitude_delta": 10},
    )
    draft = _heuristic_plan(profile_res.get("result") or {}, pred_res.get("result") or {})
    save_res = execute_tool(db, "save_weekly_plan", {"student_id": student_id, **draft})
    plan_id = save_res.get("result", {}).get("plan_id") if save_res.get("ok") else None
    steps.append(
        _log(
            db,
            student_id,
            run_id,
            "ACT",
            "Deterministic recovery after LLM error.",
            tool_name="save_weekly_plan",
            tool_output=save_res,
        )
    )
    final_message = f"[Fallback after LLM error] Plan #{plan_id} pending approval."
    steps.append(_log(db, student_id, run_id, "DONE", final_message))
    return {
        "run_id": run_id,
        "mode": "deterministic_fallback",
        "steps": steps,
        "final_plan_id": plan_id,
        "final_message": final_message,
        "warnings": warnings,
    }
