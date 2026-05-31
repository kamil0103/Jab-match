import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import Config
from app.scraper.indeed import IndeedScraper
from app.db.database import Database

class DailyScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.db = Database()
        self.running = False

    def _run_scan(self):
        print(f"[{datetime.now()}] Running scheduled Indeed scan...")
        scraper = IndeedScraper()
        # Read search keywords from a simple config file or env
        keywords = os.getenv("SCRAPER_KEYWORDS", "software engineer").split(",")
        total_added = 0
        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            try:
                jobs = scraper.search(kw, max_results=5)
                added = scraper.save_jobs(jobs)
                total_added += added
                print(f"  Keyword '{kw}': found {len(jobs)}, added {added} new")
            except Exception as e:
                print(f"  Keyword '{kw}' failed: {e}")
        print(f"[{datetime.now()}] Scan complete. Total new jobs: {total_added}")

    def start(self):
        if not Config.SCHEDULE_ENABLED or not Config.SCRAPER_ENABLED:
            print("Scheduler or scraper disabled. Not starting.")
            return

        try:
            hour, minute = Config.SCHEDULE_TIME.split(":")
        except ValueError:
            hour, minute = "09", "00"

        self.scheduler.add_job(
            self._run_scan,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_indeed_scan",
            replace_existing=True
        )
        self.scheduler.start()
        self.running = True
        print(f"Scheduler started. Daily scan at {Config.SCHEDULE_TIME}")

    def stop(self):
        if self.running:
            self.scheduler.shutdown()
            self.running = False

# Singleton
_scheduler_instance = None

def get_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DailyScheduler()
    return _scheduler_instance
