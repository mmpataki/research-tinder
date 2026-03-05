"""
Scheduler service for automatic daily scraping.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session
from app.services.scraper import scrape_and_store, get_unscored_papers
from app.services.llm import score_papers, check_provider_health
from app.services.recommender import auto_archive_old_papers
from app.models.paper import UserPreference
from sqlalchemy import select

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _get_pref_val(db, key: str, default: str = "") -> str:
    result = await db.execute(
        select(UserPreference).where(UserPreference.key == key)
    )
    pref = result.scalar_one_or_none()
    return pref.value if pref else default


async def scheduled_scrape_and_score():
    """Scheduled job: scrape arXiv and score new papers."""
    logger.info("Starting scheduled scrape and score...")

    async with async_session() as db:
        # Get categories
        cats_str = await _get_pref_val(db, "arxiv_categories", ",".join(settings.ARXIV_CATEGORIES))
        categories = [c.strip() for c in cats_str.split(",") if c.strip()]

        # Scrape
        new_count = await scrape_and_store(db, categories)
        logger.info(f"Scheduled scrape: {new_count} new papers")

        # Determine provider
        provider = await _get_pref_val(db, "llm_provider", settings.LLM_PROVIDER)
        if provider == "openai":
            api_key = await _get_pref_val(db, "openai_api_key", settings.OPENAI_API_KEY)
            model = await _get_pref_val(db, "openai_model", settings.OPENAI_MODEL)
        elif provider == "gemini":
            api_key = await _get_pref_val(db, "gemini_api_key", settings.GEMINI_API_KEY)
            model = await _get_pref_val(db, "gemini_model", settings.GEMINI_MODEL)
        else:
            api_key = ""
            model = await _get_pref_val(db, "ollama_model", settings.OLLAMA_MODEL)

        if await check_provider_health(provider, api_key):
            interests = await _get_pref_val(db, "user_interests", settings.USER_INTERESTS)
            unscored = await get_unscored_papers(db)
            scored = await score_papers(
                db, unscored, interests,
                provider=provider, api_key=api_key, model_override=model,
            )
            logger.info(f"Scheduled scoring: {scored} papers scored via {provider}")
        else:
            logger.warning(f"{provider} not available, skipping scoring")

        # Auto-archive papers ranked beyond top 100
        archived = await auto_archive_old_papers(db, keep_top=100)
        if archived:
            logger.info(f"Auto-archived {archived} low-ranked papers")


def start_scheduler():
    """Start the APScheduler with the configured cron schedule."""
    scheduler.add_job(
        scheduled_scrape_and_score,
        "cron",
        hour=settings.SCRAPE_CRON_HOUR,
        minute=settings.SCRAPE_CRON_MINUTE,
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started: scraping daily at {settings.SCRAPE_CRON_HOUR:02d}:{settings.SCRAPE_CRON_MINUTE:02d}"
    )


def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown()
