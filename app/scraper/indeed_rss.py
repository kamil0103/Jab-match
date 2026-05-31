import feedparser
import requests
from typing import List, Dict, Any
from app.config import Config
from app.db.database import Database

class IndeedRSS:
    def __init__(self):
        self.db = Database()

    def search(self, keywords: str, location: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        jobs = []
        query = keywords.replace(" ", "+")
        loc = location.replace(" ", "+") if location else ""
        rss_url = f"https://www.indeed.com/rss?q={query}&l={loc}"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://www.indeed.com/",
            }
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()
            feed = feedparser.parse(response.text)

            for entry in feed.entries[:max_results]:
                job = {
                    "title": entry.get("title", ""),
                    "company": "",
                    "location": "",
                    "url": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "source": "indeed",
                    "published": entry.get("published", "")
                }
                # Parse title which often has format "Title - Company - Location"
                title = job["title"]
                if " - " in title:
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        job["title"] = parts[0].strip()
                        job["company"] = parts[1].strip()
                    if len(parts) >= 3:
                        job["location"] = parts[2].strip()
                jobs.append(job)
        except Exception as e:
            print(f"Indeed RSS error: {e}")

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
