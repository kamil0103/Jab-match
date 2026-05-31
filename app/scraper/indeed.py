import time
import random
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from app.config import Config
from app.db.database import Database

class IndeedScraper:
    def __init__(self, delay: int = None, db_path: str = None):
        self.delay = delay or Config.SCRAPER_DELAY
        self.db = Database(db_path)

    def search(self, query: str, location: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            Stealth().use_sync(page)

            try:
                # Build Indeed search URL
                url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}"
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(random.uniform(3, 6))

                # Accept cookies if present (various selectors)
                for btn_text in ["Accept", "Agree", "I understand", "Continue"]:
                    try:
                        btn = page.locator(f"button:has-text('{btn_text}')").first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            time.sleep(2)
                            break
                    except Exception:
                        pass

                # Extract job cards
                cards = page.locator("[data-testid='slider_container']").all()
                if not cards:
                    # Fallback selectors
                    cards = page.locator(".job_seen_beacon, [data-jk], .slider_container").all()

                for i, card in enumerate(cards[:max_results]):
                    try:
                        title_el = card.locator("h2 a").first
                        title = title_el.inner_text(timeout=3000).strip() if title_el.count() > 0 else ""
                        link = title_el.get_attribute("href") if title_el.count() > 0 else ""
                        if link and link.startswith("/"):
                            link = f"https://www.indeed.com{link}"

                        company_el = card.locator("[data-testid='company-name'], .companyName, [class*='company']").first
                        company = company_el.inner_text(timeout=3000).strip() if company_el.count() > 0 else ""

                        location_el = card.locator("[data-testid='job-location'], [class*='location']").first
                        loc = location_el.inner_text(timeout=3000).strip() if location_el.count() > 0 else ""

                        summary_el = card.locator(".job-snippet, [class*='snippet']").first
                        summary = summary_el.inner_text(timeout=3000).strip() if summary_el.count() > 0 else ""

                        if title:
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": loc,
                                "url": link,
                                "description": summary,
                                "source": "indeed"
                            })
                    except Exception:
                        continue

                    # Slow down between cards
                    time.sleep(random.uniform(self.delay * 0.8, self.delay * 1.2))

                # Pagination (optional, very slow)
                # For now we only scrape first page to keep it safe

            except Exception as e:
                print(f"Indeed scraper error: {e}")
            finally:
                browser.close()

        return jobs

    def save_jobs(self, jobs: List[Dict[str, Any]]):
        added = 0
        for job in jobs:
            # Check if already exists by URL
            existing = self.db.fetchone("SELECT id FROM jobs WHERE url = ?", (job.get("url"),))
            if not existing and job.get("title"):
                self.db.execute(
                    "INSERT INTO jobs (title, company, location, url, description, source) VALUES (?, ?, ?, ?, ?, ?)",
                    (job["title"], job["company"], job["location"], job["url"], job["description"], job["source"])
                )
                added += 1
        return added
