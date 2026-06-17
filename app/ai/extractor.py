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
- Institution types: high_school, community_college, university, certificate_organization, other.
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

SKILL_EXTRACTION_PROMPT = """You are a technical skills extractor for Computer Science graduates.

Given the following courses and their descriptions, extract a comprehensive list of technical skills, tools, languages, frameworks, and concepts.

Return ONLY a valid JSON array of skills (no markdown, no explanations, no extra text before or after):
[{{"name": "Python", "category": "Programming Language", "proficiency": "Intermediate", "source": "CS101 - Introduction to Computer Science"}}]

Categories to use: Programming Language, Framework, Tool, Concept, Database, Cloud, DevOps, Data Science, Machine Learning, Web Development, Mobile Development, Security, Algorithm, Theory, Soft Skill

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
            return json.loads(json_str)
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
