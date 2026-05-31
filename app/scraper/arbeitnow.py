import requests
from typing import List, Dict, Any
from app.db.database import Database

class ArbeitnowAPI:
    """Free job board API - no API key required."""
    def __init__(self):
        self.base_url = "https://www.arbeitnow.com/api/job-board-api"
        self.db = Database()

    def search(self, keywords: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        jobs = []
        try:
            # The API returns all jobs; we filter locally
            response = requests.get(self.base_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            all_jobs = data.get("data", [])
            keyword_list = [k.lower().strip() for k in keywords.split(",") if k.strip()]

            for job in all_jobs:
                title = job.get("title", "")
                description = job.get("description", "")
                tags = [t.lower() for t in job.get("tags", [])]

                # Filter by keywords if provided
                if keyword_list:
                    match = False
                    text_to_search = (title + " " + description + " " + " ".join(tags)).lower()
                    for kw in keyword_list:
                        if kw in text_to_search:
                            match = True
                            break
                    if not match:
                        continue

                jobs.append({
                    "title": title,
                    "company": job.get("company_name", ""),
                    "location": job.get("location", ""),
                    "url": job.get("url", ""),
                    "description": description[:500] if description else "",
                    "source": "arbeitnow",
                    "remote": job.get("remote", False),
                    "tags": job.get("tags", [])
                })

            return jobs[:max_results]
        except Exception as e:
            print(f"Arbeitnow API error: {e}")
            return []

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> int:
        added = 0
        for job in jobs:
            existing = self.db.fetchone("SELECT id FROM jobs WHERE url = ?", (job.get("url"),))
            if not existing and job.get("title"):
                self.db.execute(
                    "INSERT INTO jobs (title, company, location, url, description, source) VALUES (?, ?, ?, ?, ?, ?)",
                    (job["title"], job["company"], job["location"], job["url"], job["description"], job["source"])
                )
                added += 1
        return added
