import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    SCHEDULE_ENABLED = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"
    SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")
    SCRAPER_ENABLED = os.getenv("SCRAPER_ENABLED", "false").lower() == "true"
    SCRAPER_DELAY = int(os.getenv("SCRAPER_DELAY", "20"))
    DB_PATH = os.getenv("DB_PATH", "/app/data/jobmatcher.db")
    UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/data/uploads")
    GENERATED_DIR = os.getenv("GENERATED_DIR", "/app/data/generated")

    @classmethod
    def ensure_dirs(cls):
        for d in [cls.UPLOADS_DIR, cls.GENERATED_DIR]:
            os.makedirs(d, exist_ok=True)

    @classmethod
    def ai_available(cls):
        return bool(cls.GEMINI_API_KEY) or bool(cls.OPENAI_API_KEY)
