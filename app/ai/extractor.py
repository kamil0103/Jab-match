import json
import re
from typing import List, Dict, Any
from app.ai.client import AIClient

COURSE_EXTRACTION_PROMPT = """You are an expert academic transcript parser. Given the raw text extracted from an academic transcript, extract the institution, degree, and all courses listed. The user will upload transcripts from each school separately, so do NOT combine them or create transfer credit summaries.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanations, no extra text before or after):
{{
  "institutions": [
    {{"name": "University Name", "location": "City, State", "institution_type": "university"}}
  ],
  "degrees": [
    {{"institution_name": "University Name", "degree_name": "Bachelor of Science in Computer Science", "degree_type": "bachelors", "field": "Computer Science", "start_date": "2020-08", "end_date": "2024-05", "gpa": "3.8", "honors": "Cum Laude", "is_current": false}}
  ],
  "courses": [
    {{"code": "CS101", "name": "Introduction to Computer Science", "grade": "A", "credits": 3.0, "term": "Fall 2020", "institution_name": "University Name", "degree_name": "Bachelor of Science in Computer Science", "description": "Brief description if available, otherwise infer from course name"}}
  ]
}}

Rules:
- Extract the institution and degree from THIS transcript only.
- Institution types: high_school, community_college, university, transfer, certificate_organization, other.
- Degree types: high_school_diploma, associates, bachelors, masters, doctorate, certificate, other.
- Each course must reference the institution_name and degree_name it belongs to.
- For courses without a degree (e.g., high school classes), set degree_name to null.
- Do NOT create transfer_credits summaries. The user uploads each transcript separately.
- If a field is missing, use null or best inference.
- grade should be the letter grade (A, B+, etc.).
- credits should be a number.
- term is the semester/term (e.g., "Fall 2020", "Spring 2021").
- description can be inferred from the course name if not explicitly stated.
- Output ONLY the JSON object, nothing else.

Transcript text:
{text}
"""

SKILL_EXTRACTION_PROMPT = """You are a technical skills extractor for Computer Science graduates building a resume.

Given the following courses and their descriptions, extract up to 25 relevant technical, professional, and job-market skills that should appear on a resume.

Return ONLY a valid JSON array of skills (no markdown, no explanations, no extra text before or after):
[{{"name": "Python", "category": "Programming Language", "proficiency": "Intermediate", "source": "CS101 - Introduction to Computer Science"}}]

Allowed categories: Programming Language, Framework, Library, Tool, Database, Cloud, DevOps, Data Science, Machine Learning, Web Development, Mobile Development, Security, Operating System, Protocol, Artificial Intelligence

Rules:
- Focus on concrete tools, languages, frameworks, platforms, databases, and applied technical abilities.
- DO NOT include math topics (Algebra, Calculus, Trigonometry, Statistics, etc.), general academic skills, soft skills, or theoretical concepts that are not practical job skills.
- DO NOT include course titles verbatim unless they represent a widely recognized technology or skill.
- Prefer well-known industry terms.
- Limit to the most relevant and important skills.

Proficiency levels: Beginner, Intermediate, Advanced, Expert (infer from course name, grade, and level)

Courses:
{courses_json}
"""

class TranscriptExtractor:
    def __init__(self):
        self.client = AIClient()

    def extract_courses(self, transcript_text: str) -> Dict[str, Any]:
        prompt = COURSE_EXTRACTION_PROMPT.format(text=transcript_text)
        response = self.client.chat(prompt)
        json_str = self._extract_json(response)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse AI response as JSON: {e}. Raw response: {response[:500]}")

    def extract_skills(self, courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        courses_json = json.dumps(courses, indent=2)
        prompt = SKILL_EXTRACTION_PROMPT.format(courses_json=courses_json)
        response = self.client.chat(prompt)
        json_str = self._extract_json(response)
        try:
            skills = json.loads(json_str)
            return filter_resume_skills(skills)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse AI response as JSON: {e}. Raw response: {response[:500]}")

    def enhance_with_syllabi(self, courses: List[Dict[str, Any]], syllabi_texts: List[str]) -> List[Dict[str, Any]]:
        prompt = f"""Given these courses and additional syllabus details, enhance the course descriptions and infer skills.

Courses: {json.dumps(courses, indent=2)}

Syllabus texts: {json.dumps(syllabi_texts, indent=2)}

Return ONLY a valid JSON array of enhanced courses with a new field 'enhanced_skills' listing skills inferred from the syllabus. No extra text before or after.
"""
        response = self.client.chat(prompt)
        json_str = self._extract_json(response)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse AI response as JSON: {e}. Raw response: {response[:500]}")

    def _extract_json(self, text: str) -> str:
        text = text.strip()

        # 1. Try markdown code blocks
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

        # 2. Try to find a JSON object by balanced braces
        obj = self._find_balanced(text, "{", "}")
        if obj:
            return obj

        # 3. Try to find a JSON array by balanced brackets
        arr = self._find_balanced(text, "[", "]")
        if arr:
            return arr

        # 4. Fallback: return stripped text
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


# Skills that should not appear on a resume
_EXCLUDED_SKILL_KEYWORDS = {
    "algebra", "trigonometry", "calculus", "geometry", "statistics", "probability",
    "mathematical", "mathematics", "discrete math", "linear algebra", "pre-calculus",
    "critical reading", "written communication", "oral communication", "public speaking",
    "presentation skills", "career development", "professional development",
    "critical thinking", "argumentation", "logic", "set theory", "graph theory",
    "combinatorics", "proof techniques", "formal languages", "automata", "turing machines",
    "computability", "logic gates", "karnaugh maps", "boolean algebra", "state machines",
    "circuit design", "memory hierarchy", "cpu organization", "hardware description",
    "digital logic", "computer architecture", "assembly language", "low-level programming"
}

_ALLOWED_SKILL_CATEGORIES = {
    "programming language", "framework", "library", "tool", "database", "cloud",
    "devops", "data science", "machine learning", "web development", "mobile development",
    "security", "operating system", "protocol", "artificial intelligence", "version control"
}


def filter_resume_skills(skills, max_skills=30):
    """Keep only job-relevant technical/professional skills for resumes."""
    filtered = []
    for s in skills:
        name = (s.get("name") or "").lower()
        cat = (s.get("category") or "").lower()
        if not name:
            continue
        if cat and cat not in _ALLOWED_SKILL_CATEGORIES:
            continue
        if any(kw in name for kw in _EXCLUDED_SKILL_KEYWORDS):
            continue
        filtered.append(s)
    return filtered[:max_skills]
