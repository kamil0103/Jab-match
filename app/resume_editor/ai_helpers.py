from typing import Dict, Any, List, Optional
import json

from app.ai.client import AIClient


class ResumeAIHelper:
    """AI helpers for the resume editor. Uses real user data; never invents credentials."""

    def __init__(self):
        self.client = AIClient()

    def _generate(self, prompt: str) -> str:
        try:
            return self.client.chat(prompt).strip()
        except Exception:
            return ""

    def improve_summary(self, current_summary: str, target_roles: str = "", profile: Dict[str, str] = None) -> str:
        """Rewrite the profile summary to be concise and targeted."""
        prompt = (
            "You are an expert resume writer. Rewrite the following professional summary "
            "to be concise, achievement-oriented, and tailored to the target role(s). "
            "Do NOT invent companies, degrees, job titles, projects, or credentials. "
            "Use only the facts provided.\n\n"
            f"Target roles: {target_roles or 'general'}\n\n"
            f"Current summary:\n{current_summary}\n\n"
            "Return only the rewritten summary (1-3 sentences)."
        )
        improved = self._generate(prompt)
        return improved or current_summary

    def improve_bullets(self, bullets_text: str, title: str = "", company: str = "") -> str:
        """Improve a work experience bullets block using the STAR method."""
        prompt = (
            "You are an expert resume writer. Improve the following work experience bullet points "
            "to be concise, action-oriented, and quantified where possible. "
            "Use the STAR method implicitly (Situation, Task, Action, Result). "
            "Do NOT invent facts, metrics, or responsibilities that are not present or strongly implied. "
            "Return the improved bullet points only, one per line, each starting with a dash.\n\n"
            f"Role: {title or 'N/A'} at {company or 'N/A'}\n\n"
            f"Current bullets:\n{bullets_text}\n\n"
            "Improved bullets:"
        )
        improved = self._generate(prompt)
        return improved or bullets_text

    def suggest_skills(self, job_description: str, current_skills: List[str], profile_summary: str = "") -> List[str]:
        """Suggest skills to add that are present in the job description and relevant to the user's background."""
        existing = ", ".join(current_skills) if current_skills else "none"
        prompt = (
            "You are an expert career advisor. Given the job description and the candidate's current skills, "
            "suggest 5-10 relevant skills the candidate might add to their resume. "
            "Only suggest skills that are genuinely relevant to the job and reasonable given the user's background. "
            "Do NOT invent degrees, certifications, or experience. "
            "Return a JSON array of strings only.\n\n"
            f"Job description:\n{job_description}\n\n"
            f"Candidate summary:\n{profile_summary}\n\n"
            f"Current skills: {existing}\n\n"
            "Suggested skills (JSON array):"
        )
        try:
            text = self._generate(prompt)
            if text.startswith("```"):
                text = text.strip("`").strip()
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            return json.loads(text)
        except Exception:
            return []

    def tailor_resume_for_job(self, resume_data: Dict[str, Any], job_description: str) -> Dict[str, Any]:
        """Adjust summary and experience bullet emphasis for a job description."""
        summary = resume_data.get("profile", {}).get("summary", "")
        target = self.improve_summary(summary, target_roles=self._extract_title(job_description))
        resume_data["profile"]["summary"] = target

        for exp in resume_data.get("experience", []):
            improved = self.improve_bullets(exp.get("bullets", ""), exp.get("title", ""), exp.get("company", ""))
            exp["bullets"] = improved
            exp["bullet_list"] = [b.strip("-• ").strip() for b in improved.splitlines() if b.strip()]
        return resume_data

    @staticmethod
    def _extract_title(job_description: str) -> str:
        first_line = job_description.splitlines()[0] if job_description else ""
        return first_line[:120]


resume_ai = ResumeAIHelper()
