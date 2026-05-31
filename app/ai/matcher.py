import json
import re
from typing import List, Dict, Any
from app.ai.client import AIClient

MATCHING_PROMPT = """You are a job matching expert for Computer Science graduates.

Given a candidate's skills, courses, certificates, and a job description, analyze the fit.

Candidate Skills:
{skills_json}

Candidate Courses:
{courses_json}

Candidate Certificates:
{certs_json}

Job Description:
{job_description}

Return ONLY a valid JSON object with this exact structure, no extra text before or after:
{{"match_score": 85, "summary": "Brief summary", "matching_skills": ["Python"], "missing_skills": ["Kubernetes"], "relevant_courses": ["CS101"], "relevant_certs": ["AWS Certified"], "suggested_improvements": "Focus on cloud skills"}}

match_score should be 0-100 based on skill overlap and relevance.
"""

class JobMatcher:
    def __init__(self):
        self.client = AIClient()

    def match(self, skills: List[Dict[str, Any]], courses: List[Dict[str, Any]], certificates: List[Dict[str, Any]], job_description: str) -> Dict[str, Any]:
        prompt = MATCHING_PROMPT.format(
            skills_json=json.dumps(skills, indent=2),
            courses_json=json.dumps(courses, indent=2),
            certs_json=json.dumps(certificates, indent=2),
            job_description=job_description
        )
        response = self.client.chat(prompt)
        json_str = self._clean_json(response)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse AI response as JSON: {e}. Raw: {response[:500]}")

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
        # Balanced braces
        obj = self._find_balanced(text, "{", "}")
        if obj:
            return obj
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
