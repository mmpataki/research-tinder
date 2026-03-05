import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./research_tinder.db")

    # LLM provider: "ollama", "openai", "gemini"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Google Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ArXiv
    ARXIV_CATEGORIES: list = os.getenv("ARXIV_CATEGORIES", "cs.AI,cs.LG").split(",")
    SCRAPE_CRON_HOUR: int = int(os.getenv("SCRAPE_CRON_HOUR", "8"))
    SCRAPE_CRON_MINUTE: int = int(os.getenv("SCRAPE_CRON_MINUTE", "0"))
    USER_INTERESTS: str = os.getenv(
        "USER_INTERESTS",
        "I am interested in machine learning and artificial intelligence research."
    )

    # Google Scholar
    SCHOLAR_PROFILE_URLS: str = os.getenv("SCHOLAR_PROFILE_URLS", "")

    # Raindrop.io
    RAINDROP_TOKEN: str = os.getenv("RAINDROP_TOKEN", "")
    RAINDROP_COLLECTION_ID: int = int(os.getenv("RAINDROP_COLLECTION_ID", "-1"))

    # ACM SIGs (Semantic Scholar venue names, comma-separated)
    # e.g. "CHI,SIGKDD,CSCW,SIGMOD,SIGCOMM"
    ACM_SIG_NAMES: str = os.getenv("ACM_SIG_NAMES", "")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
