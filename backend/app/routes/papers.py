"""
API routes for papers - the core "Tinder" functionality.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.paper import Paper, UserPreference, FavoriteAuthor
from app.services.raindrop import save_to_raindrop
from app.services.recommender import get_recommended_feed

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("/feed")
async def get_feed(
    limit: int = Query(25, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recommended papers to swipe on.
    Uses the recommendation engine to blend LLM scores with swipe-history
    preferences. Returns top ~25 papers by default.
    """
    papers, total = await get_recommended_feed(db, limit=limit, offset=0, min_score=min_score)
    return {"papers": papers, "total_available": total}


@router.get("/stash")
async def get_stash(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Browse papers ranked beyond the daily top-25.
    These are still pending but lower-priority by the recommendation engine.
    """
    offset = (page - 1) * per_page + 25  # skip the top 25 (those are in /feed)
    papers, total = await get_recommended_feed(db, limit=per_page, offset=offset, min_score=min_score)
    return {
        "papers": papers,
        "total": max(0, total - 25),
        "page": page,
        "per_page": per_page,
    }


@router.post("/{paper_id}/swipe")
async def swipe_paper(
    paper_id: int,
    action: str = Query(..., regex="^(like|pass)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Swipe on a paper: 'like' (right swipe) or 'pass' (left swipe).
    """
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.status = "liked" if action == "like" else "passed"
    paper.swiped_at = datetime.utcnow()
    await db.commit()

    return {"message": f"Paper {action}d", "paper": paper.to_dict()}


@router.get("/reading-list")
async def get_reading_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all right-swiped (liked) papers."""
    offset = (page - 1) * per_page

    # Get count
    count_result = await db.execute(
        select(func.count(Paper.id)).where(Paper.status == "liked")
    )
    total = count_result.scalar()

    # Get papers
    result = await db.execute(
        select(Paper)
        .where(Paper.status == "liked")
        .order_by(Paper.swiped_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    papers = result.scalars().all()

    return {
        "papers": [p.to_dict() for p in papers],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/{paper_id}/unlike")
async def unlike_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a paper from reading list (move back to pending)."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.status = "pending"
    paper.swiped_at = None
    await db.commit()

    return {"message": "Paper removed from reading list"}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about papers."""
    total = (await db.execute(select(func.count(Paper.id)))).scalar()
    pending = (await db.execute(
        select(func.count(Paper.id)).where(Paper.status == "pending")
    )).scalar()
    liked = (await db.execute(
        select(func.count(Paper.id)).where(Paper.status == "liked")
    )).scalar()
    passed = (await db.execute(
        select(func.count(Paper.id)).where(Paper.status == "passed")
    )).scalar()
    unscored = (await db.execute(
        select(func.count(Paper.id)).where(Paper.relevance_score == None)
    )).scalar()
    scored_pending = (await db.execute(
        select(func.count(Paper.id))
        .where(Paper.status == "pending")
        .where(Paper.relevance_score != None)
    )).scalar()

    return {
        "total": total,
        "pending": pending,
        "liked": liked,
        "passed": passed,
        "unscored": unscored,
        "feed_ready": min(scored_pending, 25),
        "stashed": max(0, scored_pending - 25),
    }


# ---- Favorite Authors ----

@router.get("/favorite-authors")
async def get_favorite_authors(db: AsyncSession = Depends(get_db)):
    """Return the list of favorite author names."""
    result = await db.execute(select(FavoriteAuthor).order_by(FavoriteAuthor.added_at.desc()))
    authors = result.scalars().all()
    return {"authors": [a.name for a in authors]}


@router.post("/favorite-authors")
async def add_favorite_author(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Add an author to favorites."""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Author name is required")
    existing = (await db.execute(select(FavoriteAuthor).where(FavoriteAuthor.name == name))).scalar_one_or_none()
    if not existing:
        db.add(FavoriteAuthor(name=name))
        await db.commit()
    return {"message": "Added", "name": name}


@router.delete("/favorite-authors/{name}")
async def remove_favorite_author(name: str, db: AsyncSession = Depends(get_db)):
    """Remove an author from favorites."""
    result = await db.execute(select(FavoriteAuthor).where(FavoriteAuthor.name == name))
    author = result.scalar_one_or_none()
    if author:
        await db.delete(author)
        await db.commit()
    return {"message": "Removed", "name": name}


@router.post("/{paper_id}/raindrop")
async def share_to_raindrop(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Save a paper as a bookmark to Raindrop.io."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Get token and collection from prefs / env
    token_result = await db.execute(
        select(UserPreference).where(UserPreference.key == "raindrop_token")
    )
    token_pref = token_result.scalar_one_or_none()
    token = token_pref.value if token_pref else settings.RAINDROP_TOKEN

    coll_result = await db.execute(
        select(UserPreference).where(UserPreference.key == "raindrop_collection_id")
    )
    coll_pref = coll_result.scalar_one_or_none()
    collection_id = int(coll_pref.value) if coll_pref else settings.RAINDROP_COLLECTION_ID

    if not token:
        raise HTTPException(status_code=400, detail="No Raindrop token configured. Set it in Settings.")

    try:
        link = paper.arxiv_url or paper.pdf_url or ""
        item = await save_to_raindrop(
            token=token,
            title=paper.title,
            link=link,
            excerpt=paper.abstract[:500] if paper.abstract else "",
            tags=["research", "paper"] + (paper.categories.split(",") if paper.categories else []),
            collection_id=collection_id,
        )
        return {"message": "Saved to Raindrop!", "raindrop": item}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Raindrop error: {str(e)}")
