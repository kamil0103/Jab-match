import requests
from typing import List, Dict, Any
from app.db.database import Database

class MuseAPI:
    """The Muse job board API - free, no API key required."""
    def __init__(self, db_path: str = None):
        self.base_url = "https://www.themuse.com/api/public/jobs"
        self.db = Database(db_path)

    def search(self, keywords: str = "", location: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        jobs = []
        try:
            params = {
                "page": 1,
                "descending": "true"
            }
            if keywords:
                params["keyword"] = keywords
            if location:
                params["location"] = location

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for job in data.get("results", [])[:max_results]:
                locations = job.get("locations", [])
                loc_str = ", ".join([l.get("name", "") for l in locations[:2]]) if locations else ""

                jobs.append({
                    "title": job.get("name", ""),
                    "company": job.get("company", {}).get("name", ""),
                    "location": loc_str,
                    "url": job.get("refs", {}).get("landing_page", ""),
                    "description": job.get("contents", "")[:500] if job.get("contents") else "",
                    "source": "themuse",
                    "published": job.get("publication_date", "")
                })
        except Exception as e:
            print(f"The Muse API error: {e}")

        return jobs

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
