"""
Recommendation engine that learns from swipe history.

Builds a keyword profile from liked/passed papers and uses it to
re-rank new papers, combining the LLM relevance score with a
personalized preference signal.

The feed shows the top ~25 papers; the rest are "stashed" but accessible.
A daily cleanup auto-passes papers ranked beyond the top 100.
"""
import math
import re
import logging
from collections import Counter
from typing import List, Dict, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was",
    "were", "been", "have", "has", "had", "not", "but", "its", "our",
    "their", "which", "can", "will", "also", "than", "into", "more",
    "other", "some", "such", "only", "over", "these", "between", "each",
    "all", "both", "through", "does", "about", "most", "when", "where",
    "how", "what", "who", "whom", "they", "them", "then", "there",
    "here", "very", "just", "use", "used", "using", "based", "show",
    "shown", "well", "paper", "propose", "proposed", "method", "methods",
    "approach", "result", "results", "work", "present", "new", "first",
    "two", "one", "however", "while", "may", "could", "should", "would",
    "able", "many", "much", "under", "per", "via", "given", "make",
}


def _tokenize(text: str) -> List[str]:
    """Extract lowercase words (3+ chars), dropping stop words."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [w for w in words if w not in STOP_WORDS]


def build_user_profile(
    liked_papers: List[Paper],
    passed_papers: List[Paper],
) -> Dict[str, float]:
    """
    Build a weighted keyword profile from swipe history.
    Liked papers get positive weight, passed papers get negative weight.
    Returns {word: weight} dict.
    """
    like_counts = Counter()
    pass_counts = Counter()

    for p in liked_papers:
        tokens = _tokenize(f"{p.title} {p.title} {p.abstract}")  # title weighted 2x
        like_counts.update(tokens)

    for p in passed_papers:
        tokens = _tokenize(f"{p.title} {p.abstract}")
        pass_counts.update(tokens)

    # Combine: likes are positive, passes are negative (at 0.3x weight)
    all_words = set(like_counts.keys()) | set(pass_counts.keys())
    profile: Dict[str, float] = {}

    for word in all_words:
        lc = like_counts.get(word, 0)
        pc = pass_counts.get(word, 0)
        weight = lc - 0.3 * pc
        if abs(weight) > 0.1:
            profile[word] = weight

    return profile


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    shared = set(vec_a.keys()) & set(vec_b.keys())
    if not shared:
        return 0.0

    dot = sum(vec_a[w] * vec_b[w] for w in shared)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if norm_a * norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_recommendation_score(
    paper: Paper,
    profile: Dict[str, float],
    category_boost: Dict[str, float],
) -> float:
    """
    Compute a composite recommendation score for a paper.

    final = 0.70 * llm_score + 0.22 * preference_similarity + 0.08 * category_boost

    Papers with a high LLM score (>= 0.8) are guaranteed a minimum
    recommendation score so they never get buried in the stash.

    Returns float 0.0 - 1.0.
    """
    llm_score = paper.relevance_score or 0.0

    # If no swipe history yet, just use LLM score
    if not profile:
        return llm_score

    # Build paper token vector
    tokens = _tokenize(f"{paper.title} {paper.title} {paper.abstract}")
    paper_vec = dict(Counter(tokens))

    # Cosine similarity with user profile (-1 to 1, normalize to 0-1)
    sim = _cosine_similarity(paper_vec, profile)
    pref_score = max(0.0, min(1.0, (sim + 1.0) / 2.0))

    # Category boost: fraction of paper's categories that user liked
    cat_score = 0.0
    if category_boost and paper.categories:
        cats = [c.strip() for c in paper.categories.split(",")]
        if cats:
            cat_score = sum(category_boost.get(c, 0.0) for c in cats) / len(cats)
            cat_score = max(0.0, min(1.0, cat_score))

    final = 0.70 * llm_score + 0.22 * pref_score + 0.08 * cat_score

    # Floor: high LLM scores should never produce a low recommendation.
    # A paper the LLM rated 90% should show up in the feed, not the stash.
    floor = llm_score * 0.85
    final = max(final, floor)

    return round(max(0.0, min(1.0, final)), 4)


def build_category_boost(
    liked_papers: List[Paper],
    passed_papers: List[Paper],
) -> Dict[str, float]:
    """
    Count which arxiv categories user tends to like vs pass.
    Returns {category: score 0-1}.
    """
    cat_likes = Counter()
    cat_passes = Counter()

    for p in liked_papers:
        for c in (p.categories or "").split(","):
            c = c.strip()
            if c:
                cat_likes[c] += 1

    for p in passed_papers:
        for c in (p.categories or "").split(","):
            c = c.strip()
            if c:
                cat_passes[c] += 1

    all_cats = set(cat_likes.keys()) | set(cat_passes.keys())
    boost = {}
    for cat in all_cats:
        lc = cat_likes.get(cat, 0)
        pc = cat_passes.get(cat, 0)
        total = lc + pc
        if total > 0:
            boost[cat] = lc / total  # simple ratio
    return boost


async def get_recommended_feed(
    db: AsyncSession,
    limit: int = 25,
    offset: int = 0,
    min_score: float = 0.0,
) -> Tuple[List[dict], int]:
    """
    Get recommended papers for the user.
    Returns (list_of_paper_dicts_with_rec_score, total_available).
    """
    # 1. Fetch user's swipe history
    liked_result = await db.execute(
        select(Paper).where(Paper.status == "liked")
    )
    liked = liked_result.scalars().all()

    passed_result = await db.execute(
        select(Paper).where(Paper.status == "passed")
    )
    passed = passed_result.scalars().all()

    # 2. Build user profile
    profile = build_user_profile(liked, passed)
    cat_boost = build_category_boost(liked, passed)

    logger.info(
        f"Recommendation profile: {len(profile)} keywords, "
        f"{len(cat_boost)} categories, "
        f"from {len(liked)} likes + {len(passed)} passes"
    )

    # 3. Fetch all pending scored papers
    pending_result = await db.execute(
        select(Paper)
        .where(Paper.status == "pending")
        .where(Paper.relevance_score != None)
        .where(Paper.relevance_score >= min_score)
    )
    pending = pending_result.scalars().all()

    if not pending:
        return [], 0

    # 4. Score and rank
    scored_papers = []
    for p in pending:
        rec_score = compute_recommendation_score(p, profile, cat_boost)
        d = p.to_dict()
        d["recommendation_score"] = rec_score
        scored_papers.append(d)

    # Sort descending by recommendation score
    scored_papers.sort(key=lambda x: x["recommendation_score"], reverse=True)

    total = len(scored_papers)

    # 5. Slice for requested page
    page = scored_papers[offset: offset + limit]

    return page, total


async def auto_archive_old_papers(db: AsyncSession, keep_top: int = 100):
    """
    Auto-pass papers ranked beyond keep_top.
    Called by the daily scheduler to keep the backlog manageable.
    """
    liked_result = await db.execute(select(Paper).where(Paper.status == "liked"))
    liked = liked_result.scalars().all()
    passed_result = await db.execute(select(Paper).where(Paper.status == "passed"))
    passed = passed_result.scalars().all()

    profile = build_user_profile(liked, passed)
    cat_boost = build_category_boost(liked, passed)

    pending_result = await db.execute(
        select(Paper)
        .where(Paper.status == "pending")
        .where(Paper.relevance_score != None)
    )
    pending = pending_result.scalars().all()

    if len(pending) <= keep_top:
        return 0

    # Score and sort
    scored = [
        (p, compute_recommendation_score(p, profile, cat_boost))
        for p in pending
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Auto-pass everything beyond keep_top
    archived = 0
    for paper, _ in scored[keep_top:]:
        paper.status = "passed"
        archived += 1

    await db.commit()
    logger.info(f"Auto-archived {archived} low-ranked papers (keeping top {keep_top})")
    return archived
