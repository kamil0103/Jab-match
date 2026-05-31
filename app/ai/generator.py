import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from app.ai.client import AIClient
from app.config import Config

# Jinja setup
env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "../templates")),
    autoescape=select_autoescape(["html", "xml"])
)

RESUME_GENERATION_PROMPT = """You are an expert resume writer for Computer Science graduates.

Given a candidate's courses, skills, certificates, and a target job description, generate a tailored resume content.

Candidate Courses:
{courses_json}

Candidate Skills:
{skills_json}

Candidate Certificates:
{certs_json}

Job Description:
{job_description}

Generate resume content as a JSON object with this exact structure, no extra text before or after:
{{"name": "Candidate Name", "summary": "Compelling professional summary tailored to this job", "university": "University Name", "degree": "Degree", "gpa": "GPA", "experience": ["Relevant project description"], "highlighted_courses": [{{"code": "CS101", "name": "Course Name", "relevance": "Why this matters"}}], "highlighted_certs": ["AWS Certified Solutions Architect"]}}
"""

COVER_LETTER_PROMPT = """You are an expert cover letter writer.

Write a compelling cover letter connecting the candidate's background to the job.

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
"""

QNA_PROMPT = """You are a job application coach.

Given a candidate's background and a job description, generate suggested answers to common application questions.

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
"""

class DocumentGenerator:
    def __init__(self):
        self.client = AIClient()
        self.templates_dir = os.path.join(os.path.dirname(__file__), "../templates")

    def _get_context(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict) -> Dict[str, Any]:
        return {
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

    def generate_resume(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict) -> tuple:
        context = self._get_context(courses, skills, certificates, job)
        prompt = RESUME_GENERATION_PROMPT.format(**context)
        response = self.client.chat(prompt)
        data = json.loads(self._clean_json(response))

        # Render HTML
        template = env.get_template("resume.html")
        html_out = template.render(
            name=data.get("name", "Your Name"),
            summary=data.get("summary", ""),
            university=data.get("university", ""),
            degree=data.get("degree", ""),
            gpa=data.get("gpa", ""),
            courses=data.get("highlighted_courses", courses[:10]),
            skills=[s["name"] for s in skills],
            certs=data.get("highlighted_certs", [c["name"] for c in certificates]),
            experience=data.get("experience", [])
        )

        # Save PDF
        filename = f"resume_{job['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(Config.GENERATED_DIR, filename)
        HTML(string=html_out).write_pdf(filepath)
        return data, filepath, html_out

    def generate_cover_letter(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict) -> tuple:
        context = self._get_context(courses, skills, certificates, job)
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
            name="Your Name",
            email="your.email@example.com",
            phone="(555) 123-4567"
        )

        filename = f"cover_letter_{job['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(Config.GENERATED_DIR, filename)
        HTML(string=html_out).write_pdf(filepath)
        return data, filepath, html_out

    def generate_qna(self, courses: List[Dict], skills: List[Dict], certificates: List[Dict], job: Dict) -> List[Dict]:
        context = self._get_context(courses, skills, certificates, job)
        prompt = QNA_PROMPT.format(**context)
        response = self.client.chat(prompt)
        return json.loads(self._clean_json(response))
