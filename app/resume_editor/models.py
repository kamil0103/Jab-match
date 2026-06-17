import json
from typing import Dict, Any, List, Optional
from datetime import datetime


DEFAULT_SECTION_ORDER = [
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications"
]


def build_resume_data(user_id: int, db, title: str = "My Resume", template: str = "classic") -> Dict[str, Any]:
    """Build a fresh resume data object from the user's profile and education/experience tables."""
from app.auth import get_profile
from app.ai.extractor import filter_resume_skills
from app.db.education import get_degrees, get_courses
from app.db.experience import get_work_experience, get_projects

    profile = get_profile(user_id) or {}
    degrees = get_degrees(user_id, db)
    courses = [c for c in get_courses(user_id, db) if c.get("is_major_related", 1)]
    work_exp = get_work_experience(user_id, db)
    projects = get_projects(user_id, db)
    skills_rows = filter_resume_skills(
        db.fetchall("SELECT name, category FROM skills WHERE user_id = ? ORDER BY category, name", (user_id,)),
        max_skills=100
    )
    certs_rows = db.fetchall("SELECT name, issuer, date_obtained FROM certificates WHERE user_id = ? ORDER BY date_obtained DESC", (user_id,))

    # Normalize education into editor-friendly format
    education = []
    for deg in degrees:
        education.append({
            "id": deg["id"],
            "school": deg.get("institution_name", ""),
            "degree": deg.get("degree_name", ""),
            "field": deg.get("field", ""),
            "graduation_date": deg.get("end_date", ""),
            "gpa": deg.get("gpa", ""),
            "honors": deg.get("honors", ""),
            "is_current": bool(deg.get("is_current", 0))
        })

    # Normalize experience
    experience = []
    for exp in work_exp:
        experience.append({
            "id": exp["id"],
            "title": exp.get("title", ""),
            "company": exp.get("company", ""),
            "location": exp.get("location", ""),
            "start_date": exp.get("start_date", ""),
            "end_date": exp.get("end_date", ""),
            "is_current": bool(exp.get("is_current", 0)),
            "bullets": exp.get("bullets", "")
        })

    # Normalize projects
    proj_list = []
    for proj in projects:
        proj_list.append({
            "id": proj["id"],
            "name": proj.get("name", ""),
            "description": proj.get("description", ""),
            "technologies": proj.get("technologies", ""),
            "link": proj.get("link", ""),
            "start_date": proj.get("start_date", ""),
            "end_date": proj.get("end_date", ""),
            "is_current": bool(proj.get("is_current", 0))
        })

    # Skills grouped by category
    skills_by_cat = {}
    for s in skills_rows:
        skills_by_cat.setdefault(s.get("category", "Other"), []).append(s["name"])
    skills = [{"category": cat, "skills": skills} for cat, skills in skills_by_cat.items()]

    # Certificates
    certifications = [{
        "name": c.get("name", ""),
        "organization": c.get("issuer", ""),
        "date": c.get("date_obtained", "")
    } for c in certs_rows]

    return {
        "title": title,
        "template": template,
        "section_order": DEFAULT_SECTION_ORDER.copy(),
        "profile": {
            "full_name": profile.get("full_name") or "",
            "email": profile.get("email") or "",
            "phone": profile.get("phone") or "",
            "location": profile.get("location") or "",
            "linkedin": profile.get("linkedin_url") or "",
            "portfolio": profile.get("portfolio_url") or "",
            "github": profile.get("github_url") or "",
            "summary": profile.get("summary") or ""
        },
        "experience": experience,
        "education": education,
        "skills": skills,
        "projects": proj_list,
        "certifications": certifications,
        "courses": courses
    }


def get_latest_resume_version(user_id: int, db) -> Optional[Dict[str, Any]]:
    """Load the most recent resume version for the user."""
    row = db.fetchone(
        "SELECT * FROM resume_versions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    if row and row.get("resume_data"):
        try:
            return json.loads(row["resume_data"])
        except json.JSONDecodeError:
            return None
    return None


def save_resume_version(user_id: int, job_id: Optional[int], resume_data: Dict[str, Any], db) -> int:
    """Save a resume version and return its id."""
    return db.insert(
        "INSERT INTO resume_versions (user_id, job_id, resume_data) VALUES (?, ?, ?)",
        (user_id, job_id, json.dumps(resume_data))
    )


def update_resume_data_profile(resume_data: Dict[str, Any], profile: Dict[str, str]) -> Dict[str, Any]:
    """Update the profile section of resume data from a profile dict."""
    resume_data["profile"].update({
        "full_name": profile.get("full_name") or resume_data["profile"].get("full_name", ""),
        "email": profile.get("email") or resume_data["profile"].get("email", ""),
        "phone": profile.get("phone") or resume_data["profile"].get("phone", ""),
        "location": profile.get("location") or resume_data["profile"].get("location", ""),
        "linkedin": profile.get("linkedin_url") or resume_data["profile"].get("linkedin", ""),
        "portfolio": profile.get("portfolio_url") or resume_data["profile"].get("portfolio", ""),
        "github": profile.get("github_url") or resume_data["profile"].get("github", "")
    })
    return resume_data
