import re
from typing import Dict, Any, List


class ATSChecker:
    """Simple ATS compliance checker based on heuristics and keyword matching."""

    def __init__(self, resume_data: Dict[str, Any], job_description: str = ""):
        self.resume_data = resume_data
        self.job_description = job_description

    def _section_present(self, key: str) -> bool:
        return bool(self.resume_data.get(key))

    def _flatten_text(self) -> str:
        parts = []
        p = self.resume_data.get("profile", {})
        parts.append(p.get("full_name") or "")
        parts.append(p.get("summary") or "")
        for exp in self.resume_data.get("experience", []):
            parts.append(exp.get("title") or "")
            parts.append(exp.get("bullets") or "")
        for edu in self.resume_data.get("education", []):
            parts.append(edu.get("degree") or "")
            parts.append(edu.get("school") or "")
        for skill_group in self.resume_data.get("skills", []):
            parts.extend(skill_group.get("skills", []))
        return " ".join(str(x) for x in parts).lower()

    def _job_keywords(self) -> List[str]:
        text = self.job_description.lower()
        # simple extraction of capitalized terms and important nouns
        words = re.findall(r"\b[a-z]{3,}\b", text)
        from collections import Counter
        counts = Counter(words)
        stop = {
            "and", "the", "for", "with", "are", "you", "will", "this", "that", "have", "from",
            "they", "we", "our", "all", "any", "can", "may", "not", "but", "was", "been",
            "their", "has", "had", "what", "when", "where", "how", "who", "which", "than",
            "must", "should", "would", "could", "about", "into", "over", "such", "other"
        }
        keywords = [w for w, c in counts.most_common(30) if w not in stop and c <= 10 and len(w) > 3]
        return keywords[:12]

    def check(self) -> Dict[str, Any]:
        issues = []
        score = 100

        profile = self.resume_data.get("profile", {})
        if not profile.get("full_name"):
            issues.append("Missing full name.")
            score -= 10
        if not profile.get("email"):
            issues.append("Missing email contact.")
            score -= 5
        if not profile.get("summary"):
            issues.append("Professional summary is empty.")
            score -= 5
        elif len(profile.get("summary", "")) < 40:
            issues.append("Professional summary is too short; aim for at least 2-3 sentences.")
            score -= 3

        if not self._section_present("experience"):
            issues.append("Work experience section is empty.")
            score -= 15
        else:
            for exp in self.resume_data.get("experience", []):
                if not exp.get("bullets", "").strip():
                    issues.append(f"Experience entry '{exp.get('title', 'Unnamed')}' has no bullet points.")
                    score -= 5

        if not self._section_present("education"):
            issues.append("Education section is empty.")
            score -= 10

        if not self._section_present("skills"):
            issues.append("Skills section is empty.")
            score -= 5

        resume_text = self._flatten_text()
        missing_keywords = []
        for kw in self._job_keywords():
            if kw not in resume_text:
                missing_keywords.append(kw)
        if missing_keywords:
            issues.append(f"Consider adding job-relevant keywords: {', '.join(missing_keywords[:5])}.")
            score -= min(len(missing_keywords) * 2, 10)

        score = max(0, min(100, score))
        return {"score": score, "issues": issues, "missing_keywords": missing_keywords}

