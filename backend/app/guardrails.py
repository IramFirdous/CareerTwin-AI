from __future__ import annotations

import re

from fastapi import HTTPException

ALLOWED_PROGRESS_FIELDS = {
    "aptitude_score",
    "english_score",
    "technical_score",
    "mock_interviews",
    "mock_interview_avg",
    "attendance_pct",
    "applications_count",
    "internships",
    "cgpa",
    "projects_count",
    "certifications_count",
}

CLAIM_PATTERNS = [
    (re.compile(r"\b(google|meta|amazon|microsoft|apple|netflix|openai)\s+(internship|offer|sde)\b", re.I), "named_faang_claim"),
    (re.compile(r"\b(i already have|already placed|already got an offer)\b", re.I), "already_placed_claim"),
    (re.compile(r"\b(fake|forged|bought)\s+(certificate|internship|offer)\b", re.I), "fraud_language"),
]


def require_student(student):
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found. Load a sample profile or create one first.")
    return student


def missing_fields(student) -> list[str]:
    missing = []
    checks = {
        "aptitude_score": student.aptitude_score,
        "english_score": student.english_score,
        "technical_score": student.technical_score,
        "cgpa": student.cgpa,
    }
    for name, value in checks.items():
        if value is None:
            missing.append(name)
    return missing


def validate_progress_update(field: str, value: float, student) -> tuple[str, float]:
    if field not in ALLOWED_PROGRESS_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported field '{field}'. Allowed: {sorted(ALLOWED_PROGRESS_FIELDS)}",
        )
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Progress values must be numeric.") from exc

    bounds = {
        "cgpa": (0, 10),
        "mock_interviews": (0, 30),
        "applications_count": (0, 80),
        "internships": (0, 6),
        "projects_count": (0, 20),
        "certifications_count": (0, 20),
    }
    lo, hi = bounds.get(field, (0, 100))
    if numeric < lo or numeric > hi:
        raise HTTPException(
            status_code=400,
            detail=f"{field} must be between {lo} and {hi}. Received {numeric}.",
        )

    current = float(getattr(student, field))
    if field in {"internships", "certifications_count", "projects_count", "mock_interviews"}:
        if numeric > current + 2:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Rejected unverified jump in {field} from {current} to {numeric}. "
                    "CareerTwin does not accept large unverified achievement spikes. "
                    "Update by at most +2 after real work, or use the sample progress controls."
                ),
            )
    return field, numeric


def scan_user_text(text: str, student) -> dict:
    """Refuse falsified achievements and flag missing context."""
    blocked = []
    warnings = []
    for pattern, code in CLAIM_PATTERNS:
        if pattern.search(text or ""):
            blocked.append(code)

    if student and "named_faang_claim" in blocked and student.internships < 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "Guardrail: this profile has 0 internships on record. "
                "CareerTwin will not treat unverified FAANG internship/offer claims as facts. "
                "Log internships in the digital twin first, then ask again."
            ),
        )
    if "fraud_language" in blocked:
        raise HTTPException(
            status_code=422,
            detail="Guardrail: requests involving forged certificates or fake offers are refused.",
        )
    if student:
        miss = missing_fields(student)
        if miss:
            warnings.append(f"Incomplete twin fields: {', '.join(miss)}")
        if student.applications_count == 0:
            warnings.append("No job applications logged yet; estimates for offer timing will be weak.")
    return {"blocked": blocked, "warnings": warnings}
