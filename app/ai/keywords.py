from typing import List, Dict, Any
from app.ai.client import AIClient

KEYWORD_PROMPT = """You are a job search strategist for Computer Science graduates.

Given a candidate's skills, courses, and certificates, suggest the best job search keywords for finding relevant entry-level and junior positions.

Candidate Skills:
{skills_json}

Candidate Courses:
{courses_json}

Candidate Certificates:
{certs_json}

Return ONLY a valid JSON object with this exact structure, no extra text:
{{"keywords": ["software engineer", "python developer"], "job_titles": ["Software Engineer", "Junior Developer"], "linkedin_url": "https://www.linkedin.com/jobs/search/?keywords=Software%20Engineer", "indeed_url": "https://www.indeed.com/jobs?q=software+engineer"}}

- keywords: array of 3-5 search terms for job boards
- job_titles: array of specific job titles to target
- linkedin_url: a single LinkedIn search URL using the top keyword
- indeed_url: a single Indeed search URL using the top keyword
"""

class KeywordGenerator:
    def __init__(self):
        self.client = AIClient()

    def generate(self, skills: List[Dict], courses: List[Dict], certificates: List[Dict]) -> Dict[str, Any]:
        import json
        prompt = KEYWORD_PROMPT.format(
            skills_json=json.dumps(skills, indent=2),
            courses_json=json.dumps(courses, indent=2),
            certs_json=json.dumps(certificates, indent=2)
        )
        response = self.client.chat(prompt)

        # Clean JSON
        text = response.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        # Find balanced braces
        obj = self._find_balanced(text, "{", "}")
        if obj:
            text = obj

        return json.loads(text)

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

    def build_linkedin_url(self, keywords: str, location: str = "") -> str:
        kw = keywords.replace(" ", "%20")
        url = f"https://www.linkedin.com/jobs/search/?keywords={kw}"
        if location:
            url += f"&location={location.replace(' ', '%20')}"
        return url

    def build_indeed_url(self, keywords: str, location: str = "") -> str:
        kw = keywords.replace(" ", "+")
        url = f"https://www.indeed.com/jobs?q={kw}"
        if location:
            url += f"&l={location.replace(' ', '+')}"
        return url
