"""
API routes for settings and system management.
Background tasks keep the API responsive during long operations.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.config import settings
from app.database import get_db, async_session
from app.models.paper import UserPreference
from app.services.scraper import scrape_and_store, get_unscored_papers
from app.services.llm import score_papers, check_provider_health, check_ollama_health
from app.services.tasks import task_manager
from app.services.scholar import scrape_scholar_and_store
from app.services.acm import scrape_acm_and_store
from app.services.raindrop import (
    save_to_raindrop,
    get_raindrop_collections,
    test_raindrop_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    arxiv_categories: Optional[str] = None
    user_interests: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    scrape_cron_hour: Optional[int] = None
    scrape_cron_minute: Optional[int] = None
    llm_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    scholar_profile_urls: Optional[str] = None
    raindrop_token: Optional[str] = None
    raindrop_collection_id: Optional[int] = None
    acm_sig_names: Optional[str] = None


# ---- helpers to read prefs ----

async def _get_pref(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(
        select(UserPreference).where(UserPreference.key == key)
    )
    pref = result.scalar_one_or_none()
    return pref.value if pref else default


async def _get_llm_params(db: AsyncSession) -> dict:
    """Return provider, api_key, model_override from saved prefs / env."""
    provider = await _get_pref(db, "llm_provider", settings.LLM_PROVIDER)
    if provider == "openai":
        api_key = await _get_pref(db, "openai_api_key", settings.OPENAI_API_KEY)
        model = await _get_pref(db, "openai_model", settings.OPENAI_MODEL)
    elif provider == "gemini":
        api_key = await _get_pref(db, "gemini_api_key", settings.GEMINI_API_KEY)
        model = await _get_pref(db, "gemini_model", settings.GEMINI_MODEL)
    else:
        api_key = ""
        model = await _get_pref(db, "ollama_model", settings.OLLAMA_MODEL)
    return {"provider": provider, "api_key": api_key, "model_override": model}


# ---- CRUD for settings ----

@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference))
    prefs = {p.key: p.value for p in result.scalars().all()}

    return {
        "arxiv_categories": prefs.get("arxiv_categories", ",".join(settings.ARXIV_CATEGORIES)),
        "user_interests": prefs.get("user_interests", settings.USER_INTERESTS),
        "ollama_model": prefs.get("ollama_model", settings.OLLAMA_MODEL),
        "ollama_base_url": prefs.get("ollama_base_url", settings.OLLAMA_BASE_URL),
        "scrape_cron_hour": int(prefs.get("scrape_cron_hour", settings.SCRAPE_CRON_HOUR)),
        "scrape_cron_minute": int(prefs.get("scrape_cron_minute", settings.SCRAPE_CRON_MINUTE)),
        "llm_provider": prefs.get("llm_provider", settings.LLM_PROVIDER),
        "openai_api_key": prefs.get("openai_api_key", settings.OPENAI_API_KEY),
        "openai_model": prefs.get("openai_model", settings.OPENAI_MODEL),
        "gemini_api_key": prefs.get("gemini_api_key", settings.GEMINI_API_KEY),
        "gemini_model": prefs.get("gemini_model", settings.GEMINI_MODEL),
        "scholar_profile_urls": prefs.get("scholar_profile_urls", settings.SCHOLAR_PROFILE_URLS),
        "raindrop_token": prefs.get("raindrop_token", settings.RAINDROP_TOKEN),
        "raindrop_collection_id": int(prefs.get("raindrop_collection_id", settings.RAINDROP_COLLECTION_ID)),
        "acm_sig_names": prefs.get("acm_sig_names", settings.ACM_SIG_NAMES),
    }


@router.put("/")
async def update_settings(updates: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}

    for key, value in update_dict.items():
        result = await db.execute(
            select(UserPreference).where(UserPreference.key == key)
        )
        pref = result.scalar_one_or_none()
        if pref:
            pref.value = str(value)
        else:
            pref = UserPreference(key=key, value=str(value))
            db.add(pref)

    await db.commit()
    return {"message": "Settings updated", "updated": list(update_dict.keys())}


# ---- Health ----

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    params = await _get_llm_params(db)
    healthy = await check_provider_health(params["provider"], params["api_key"])
    model = params["model_override"]
    return {
        "provider": params["provider"],
        "status": "connected" if healthy else "disconnected",
        "model": model,
        # legacy keys the frontend currently reads
        "ollama": "connected" if (params["provider"] == "ollama" and healthy) else "N/A",
        "ollama_model": model if params["provider"] == "ollama" else "",
    }


# ---- Background task status ----

@router.get("/task-status")
async def get_task_status():
    return task_manager.get_status()


# ---- Scrape ----

@router.post("/scrape")
async def trigger_scrape(db: AsyncSession = Depends(get_db)):
    cats_str = await _get_pref(db, "arxiv_categories", ",".join(settings.ARXIV_CATEGORIES))
    categories = [c.strip() for c in cats_str.split(",") if c.strip()]

    try:
        new_count = await scrape_and_store(db, categories)
        return {"message": f"Scrape complete. {new_count} new papers added."}
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")


# ---- Score (background) ----

@router.post("/score")
async def trigger_scoring(db: AsyncSession = Depends(get_db)):
    params = await _get_llm_params(db)
    healthy = await check_provider_health(params["provider"], params["api_key"])
    if not healthy:
        raise HTTPException(
            status_code=503,
            detail=f"{params['provider']} is not available. Check config.",
        )

    interests = await _get_pref(db, "user_interests", settings.USER_INTERESTS)
    unscored = await get_unscored_papers(db)
    if not unscored:
        return {"message": "No unscored papers to process."}

    if task_manager.is_running:
        return {"message": "A task is already running. Check status."}

    # Capture values for background closure
    _interests = interests
    _params = dict(params)
    _count = len(unscored)

    async def _bg_score():
        async with async_session() as sess:
            papers = await get_unscored_papers(sess)
            scored = await score_papers(
                sess, papers, _interests,
                provider=_params["provider"],
                api_key=_params["api_key"],
                model_override=_params["model_override"],
            )
            return f"Scored {scored}/{len(papers)} papers."

    task_manager.start(_bg_score(), description=f"Scoring {_count} papers via {params['provider']}...")
    return {"message": f"Scoring {_count} papers in background...", "task": task_manager.get_status()}


# ---- Scrape + Score (background) ----

@router.post("/scrape-and-score")
async def trigger_scrape_and_score(db: AsyncSession = Depends(get_db)):
    cats_str = await _get_pref(db, "arxiv_categories", ",".join(settings.ARXIV_CATEGORIES))
    categories = [c.strip() for c in cats_str.split(",") if c.strip()]
    interests = await _get_pref(db, "user_interests", settings.USER_INTERESTS)
    params = await _get_llm_params(db)

    if task_manager.is_running:
        return {"message": "A task is already running. Check status."}

    _interests = interests
    _params = dict(params)
    _categories = list(categories)

    async def _bg_scrape_score():
        async with async_session() as sess:
            new_count = await scrape_and_store(sess, _categories)
            healthy = await check_provider_health(_params["provider"], _params["api_key"])
            if not healthy:
                return f"Scraped {new_count} papers. {_params['provider']} not reachable — score later."

            unscored = await get_unscored_papers(sess)
            scored = await score_papers(
                sess, unscored, _interests,
                provider=_params["provider"],
                api_key=_params["api_key"],
                model_override=_params["model_override"],
            )
            return f"Scraped {new_count} new papers, scored {scored}."

    task_manager.start(_bg_scrape_score(), description="Fetching & scoring papers...")
    return {"message": "Scraping & scoring in background...", "task": task_manager.get_status()}


# ---- ACM SIG scrape (background) ----

@router.post("/acm-scrape")
async def trigger_acm_scrape(db: AsyncSession = Depends(get_db)):
    sigs_str = await _get_pref(db, "acm_sig_names", settings.ACM_SIG_NAMES)
    sig_names = [s.strip() for s in sigs_str.replace(",", "\n").split("\n") if s.strip()]

    if not sig_names:
        raise HTTPException(status_code=400, detail="No ACM SIG names configured. Add them in Settings.")

    if task_manager.is_running:
        return {"message": "A task is already running. Check status."}

    _sigs = list(sig_names)

    async def _bg_acm():
        async with async_session() as sess:
            count = await scrape_acm_and_store(sess, _sigs)
            return f"Added {count} new papers from ACM SIGs: {', '.join(_sigs)}."

    task_manager.start(_bg_acm(), description=f"Scraping ACM SIGs: {', '.join(sig_names)}...")
    return {"message": f"ACM scrape for {', '.join(sig_names)} started...", "task": task_manager.get_status()}


# ---- Scholar scrape (background) ----

@router.post("/scholar-scrape")
async def trigger_scholar_scrape(db: AsyncSession = Depends(get_db)):
    urls_str = await _get_pref(db, "scholar_profile_urls", settings.SCHOLAR_PROFILE_URLS)
    # Support both newline and comma separated
    urls = [u.strip() for u in urls_str.replace(",", "\n").split("\n") if u.strip()]

    if not urls:
        raise HTTPException(status_code=400, detail="No Scholar profile URLs configured.")

    if task_manager.is_running:
        return {"message": "A task is already running. Check status."}

    _urls = list(urls)

    async def _bg_scholar():
        async with async_session() as sess:
            count = await scrape_scholar_and_store(sess, _urls)
            return f"Added {count} new papers from {len(_urls)} Scholar profile(s)."

    task_manager.start(_bg_scholar(), description="Scraping Google Scholar...")
    return {"message": "Scholar scrape started in background...", "task": task_manager.get_status()}


# ---- Raindrop ----

@router.get("/raindrop/collections")
async def raindrop_collections(db: AsyncSession = Depends(get_db)):
    token = await _get_pref(db, "raindrop_token", settings.RAINDROP_TOKEN)
    if not token:
        raise HTTPException(status_code=400, detail="No Raindrop token configured.")
    try:
        collections = await get_raindrop_collections(token)
        return {"collections": collections}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/raindrop/test")
async def raindrop_test(db: AsyncSession = Depends(get_db)):
    token = await _get_pref(db, "raindrop_token", settings.RAINDROP_TOKEN)
    if not token:
        return {"valid": False, "message": "No token configured."}
    ok = await test_raindrop_token(token)
    return {"valid": ok}


@router.get("/health")
async def health_check():
    """Check system health (Ollama connectivity, etc.)."""
    ollama_ok = await check_ollama_health()
    return {
        "status": "ok",
        "ollama": "connected" if ollama_ok else "disconnected",
        "ollama_url": settings.OLLAMA_BASE_URL,
        "ollama_model": settings.OLLAMA_MODEL,
    }
