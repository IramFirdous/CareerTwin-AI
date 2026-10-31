from sqlalchemy.orm import Session

from app.models import JobApplication, Student


SAMPLE_STUDENTS = [
    {
        "name": "Aanya Sharma",
        "email": "aanya.sharma@campus.edu",
        "year": 4,
        "branch": "Computer Science",
        "college": "Northridge Institute of Technology",
        "aptitude_score": 81,
        "english_score": 76,
        "technical_score": 84,
        "mock_interviews": 5,
        "mock_interview_avg": 72,
        "attendance_pct": 91,
        "applications_count": 9,
        "internships": 1,
        "cgpa": 8.4,
        "projects_count": 4,
        "certifications_count": 2,
        "applications": [
            ("Nimbus Analytics", "SDE Intern", "interview"),
            ("HarborPay", "Backend Engineer", "applied"),
            ("PixelForge", "Full Stack", "rejected"),
        ],
    },
    {
        "name": "Rohan Iyer",
        "email": "rohan.iyer@campus.edu",
        "year": 4,
        "branch": "Information Technology",
        "college": "Northridge Institute of Technology",
        "aptitude_score": 54,
        "english_score": 61,
        "technical_score": 49,
        "mock_interviews": 1,
        "mock_interview_avg": 48,
        "attendance_pct": 74,
        "applications_count": 3,
        "internships": 0,
        "cgpa": 7.1,
        "projects_count": 1,
        "certifications_count": 1,
        "applications": [
            ("LocalSoft", "Graduate Engineer", "applied"),
            ("CivicTech", "QA Trainee", "applied"),
        ],
    },
    {
        "name": "Meera Kapoor",
        "email": "meera.kapoor@campus.edu",
        "year": 3,
        "branch": "Electronics",
        "college": "Lakeside College of Engineering",
        "aptitude_score": 69,
        "english_score": 80,
        "technical_score": 63,
        "mock_interviews": 3,
        "mock_interview_avg": 66,
        "attendance_pct": 88,
        "applications_count": 5,
        "internships": 1,
        "cgpa": 8.0,
        "projects_count": 3,
        "certifications_count": 2,
        "applications": [
            ("SignalWorks", "Embedded Intern", "offer"),
            ("Orbit Labs", "Firmware", "applied"),
        ],
    },
    {
        "name": "Dev Patel",
        "email": "dev.patel@campus.edu",
        "year": 4,
        "branch": "Computer Science",
        "college": "Lakeside College of Engineering",
        "aptitude_score": 44,
        "english_score": 52,
        "technical_score": 41,
        "mock_interviews": 0,
        "mock_interview_avg": 40,
        "attendance_pct": 61,
        "applications_count": 1,
        "internships": 0,
        "cgpa": 6.4,
        "projects_count": 0,
        "certifications_count": 0,
        "applications": [
            ("Campus Drive A", "Trainee", "applied"),
        ],
    },
    {
        "name": "Sara Khan",
        "email": "sara.khan@campus.edu",
        "year": 4,
        "branch": "Data Science",
        "college": "Northridge Institute of Technology",
        "aptitude_score": 90,
        "english_score": 86,
        "technical_score": 88,
        "mock_interviews": 7,
        "mock_interview_avg": 81,
        "attendance_pct": 96,
        "applications_count": 16,
        "internships": 2,
        "cgpa": 9.1,
        "projects_count": 6,
        "certifications_count": 4,
        "applications": [
            ("Helix ML", "ML Engineer", "interview"),
            ("Northwind Data", "Analyst", "offer"),
            ("Vector Bank", "Data Scientist", "applied"),
        ],
    },
]


def seed_if_empty(db: Session) -> None:
    if db.query(Student).count() > 0:
        return
    for raw in SAMPLE_STUDENTS:
        row = dict(raw)
        apps = row.pop("applications")
        student = Student(**row)
        db.add(student)
        db.flush()
        for company, role, status in apps:
            db.add(JobApplication(student_id=student.id, company=company, role=role, status=status))
    db.commit()
