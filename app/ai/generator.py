import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from app.ai.client import AIClient
from app.config import Config
from app.db.experience import render_bullets

# Jinja setup
env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "../templates")),
    autoescape=select_autoescape(["html", "xml"])
)

RESUME_GENERATION_PROMPT = """You are an expert resume writer for Computer Science graduates.

Candidate Profile:
{profile_json}

Candidate Education:
{degrees_json}

Candidate Work Experience:
{experience_json}

Candidate Projects:
{projects_json}

Candidate Courses:
{courses_json}

Candidate Skills:
{skills_json}

Candidate Certificates:
{certs_json}

Job Description:
{job_description}

Generate resume content as a JSON object with this exact structure, no extra text before or after:
{{"name": "Candidate Name", "summary": "Compelling professional summary tailored to this job", "highlighted_courses": [{{"code": "CS101", "name": "Course Name", "relevance": "Why this matters"}}], "highlighted_certs": ["AWS Certified Solutions Architect"]}}

Rules:
- Use the candidate's real name from the profile. Do NOT make up a name.
- Use the candidate's real summary from the profile if available; you may tailor it slightly for the job.
- Use only the provided work experience, projects, education, courses, skills, and certificates.
- Do NOT invent fake experience, projects, degrees, or credentials.
- The Work Experience, Projects, and Education sections should be rendered from the provided data, not from this JSON.
- If no work experience is provided, leave it off the resume. Do NOT make up jobs.
- If no projects are provided, leave them off the resume. Do NOT make up projects.
- Select the most relevant major-related courses and certificates for this job.
"""

COVER_LETTER_PROMPT = """You are an expert cover letter writer.

Candidate Profile:
{profile_json}

Candidate Education:
{degrees_json}

Candidate Work Experience:
{experience_json}

Candidate Projects:
{projects_json}

Candidate Courses:
{courses_json}

Candidate Skills:
{skills_json}

Candidate Certificates:
{certs_json}

Job Description:
{job_description}

Company: {company}
Job Title: {job_title}

Return ONLY a JSON object, no extra text:
{{"opening": "Engaging opening", "body": "Connecting coursework to job requirements", "closing": "Strong closing"}}

Rules:
- Use only the candidate's real background. Do NOT invent degrees, experience, or projects.
- The cover letter should sound like it was written by the candidate named in the profile.
"""

QNA_PROMPT = """You are a job application coach.

Candidate Profile:
{profile_json}

Candidate Education:
{degrees_json}

Candidate Work Experience:
{experience_json}

Candidate Projects:
{projects_json}

Candidate Courses:
{courses_json}

Candidate Skills:
{skills_json}

Candidate Certificates:
{certs_json}

Job Description:
{job_description}

Return ONLY a JSON array, no extra text:
[{{"question": "Tell me about yourself", "answer": "Suggested answer"}}, {{"question": "Why do you want to work here?", "answer": "Suggested answer"}}, {{"question": "What are your strengths?", "answer": "Suggested answer"}}, {{"question": "Describe a challenging project", "answer": "Suggested answer"}}, {{"question": "Where do you see yourself in 5 years?", "answer": "Suggested answer"}}]

Rules:
- Base answers only on the candidate's real profile, experience, projects, courses, skills, and certificates.
- Do NOT invent fake experience or projects.
"""

class DocumentGenerator:
    def __init__(self):
        self.client = AIClient()
        self.templates_dir = os.path.join(os.path.dirname(__file__), "../templates")

    def _get_context(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict,
                     profile: Optional[Dict] = None, degrees: Optional[List[Dict]] = None,
                     work_experience: Optional[List[Dict]] = None, projects: Optional[List[Dict]] = None) -> Dict[str, Any]:
        return {
            "profile_json": json.dumps(profile or {}, indent=2),
            "degrees_json": json.dumps(degrees or [], indent=2),
            "experience_json": json.dumps(work_experience or [], indent=2),
            "projects_json": json.dumps(projects or [], indent=2),
            "courses_json": json.dumps(courses, indent=2),
            "skills_json": json.dumps(skills, indent=2),
            "certs_json": json.dumps(certificates, indent=2),
            "job_description": job.get("description", ""),
            "company": job.get("company", ""),
            "job_title": job.get("title", "")
        }

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        obj = self._find_balanced(text, "{", "}")
        if obj:
            return obj
        arr = self._find_balanced(text, "[", "]")
        if arr:
            return arr
        return text

    def _find_balanced(self, text: str, open_char: str, close_char: str) -> str:
        start = text.find(open_char)
        if start == -1:
            return ""
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return ""

    def generate_resume(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict,
                        profile: Optional[Dict] = None, degrees: Optional[List[Dict]] = None,
                        work_experience: Optional[List[Dict]] = None, projects: Optional[List[Dict]] = None) -> tuple:
        profile = profile or {}
        degrees = degrees or []
        work_experience = work_experience or []
        projects = projects or []

        # Filter to major-related courses for the resume
        major_courses = [c for c in courses if c.get("is_major_related", 1)]

        context = self._get_context(major_courses, skills, certificates, job, profile, degrees, work_experience, projects)
        prompt = RESUME_GENERATION_PROMPT.format(**context)
        response = self.client.chat(prompt)
        data = json.loads(self._clean_json(response))

        # Use profile data for contact header; fallback to generated/placeholder only if missing
        name = profile.get("full_name") or data.get("name", "Your Name")
        safe_profile = {
            "full_name": name,
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "location": profile.get("location", ""),
            "linkedin_url": profile.get("linkedin_url", ""),
            "github_url": profile.get("github_url", ""),
            "portfolio_url": profile.get("portfolio_url", ""),
        }

        # Format work experience bullets as HTML lists for the template
        formatted_experience = []
        for exp in work_experience:
            exp_copy = dict(exp)
            exp_copy["bullets"] = render_bullets(exp.get("bullets", ""))
            formatted_experience.append(exp_copy)

        # Render HTML
        template = env.get_template("resume.html")
        html_out = template.render(
            profile=safe_profile,
            name=name,
            summary=data.get("summary", profile.get("summary", "")),
            degrees=degrees,
            work_experience=formatted_experience,
            projects=projects,
            courses=data.get("highlighted_courses", major_courses[:10]),
            skills=[s["name"] for s in skills],
            certs=data.get("highlighted_certs", [c["name"] for c in certificates])
        )

        # Save PDF with professional filename if name is available
        if profile.get("full_name"):
            safe_name = "".join(c if c.isalnum() else "_" for c in profile.get("full_name")).strip("_")
            filename = f"{safe_name}_Resume_{job['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        else:
            filename = f"resume_{job['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(Config.GENERATED_DIR, filename)
        HTML(string=html_out).write_pdf(filepath)
        return data, filepath, html_out

    def generate_cover_letter(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict,
                              profile: Optional[Dict] = None, degrees: Optional[List[Dict]] = None,
                              work_experience: Optional[List[Dict]] = None, projects: Optional[List[Dict]] = None) -> tuple:
        profile = profile or {}
        major_courses = [c for c in courses if c.get("is_major_related", 1)]
        context = self._get_context(major_courses, skills, certificates, job, profile, degrees, work_experience, projects)
        prompt = COVER_LETTER_PROMPT.format(**context)
        response = self.client.chat(prompt)
        data = json.loads(self._clean_json(response))

        template = env.get_template("cover_letter.html")
        html_out = template.render(
            date=datetime.now().strftime("%B %d, %Y"),
            company=job.get("company", ""),
            company_address="",
            opening=data.get("opening", ""),
            body=data.get("body", ""),
            closing=data.get("closing", ""),
            name=profile.get("full_name", "Your Name"),
            email=profile.get("email", "your.email@example.com"),
            phone=profile.get("phone", "(555) 123-4567"),
            linkedin_url=profile.get("linkedin_url", ""),
            github_url=profile.get("github_url", ""),
            portfolio_url=profile.get("portfolio_url", "")
        )

        filename = f"cover_letter_{job['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(Config.GENERATED_DIR, filename)
        HTML(string=html_out).write_pdf(filepath)
        return data, filepath, html_out

    def generate_qna(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict,
                     profile: Optional[Dict] = None, degrees: Optional[List[Dict]] = None,
                     work_experience: Optional[List[Dict]] = None, projects: Optional[List[Dict]] = None) -> List[Dict]:
        major_courses = [c for c in courses if c.get("is_major_related", 1)]
        context = self._get_context(major_courses, skills, certificates, job, profile, degrees, work_experience, projects)
        prompt = QNA_PROMPT.format(**context)
        response = self.client.chat(prompt)
        return json.loads(self._clean_json(response))
