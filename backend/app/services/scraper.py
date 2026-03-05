"""
ArXiv scraper service.
Uses the `arxiv` Python library to fetch new papers from configured categories.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

import arxiv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper

logger = logging.getLogger(__name__)

# Detect links to code/data repositories in paper abstracts
_ARTIFACT_PATTERN = re.compile(
    r"https?://(?:github\.com|gitlab\.com|zenodo\.org|huggingface\.co|"
    r"paperswithcode\.com|drive\.google\.com|figshare\.com|osf\.io|"
    r"bitbucket\.org|sourceforge\.net)[^\s\"'>)\]]+",
    re.IGNORECASE,
)


def _extract_artifacts(text: str) -> List[str]:
    """Return unique artifact URLs found in text."""
    return list(dict.fromkeys(_ARTIFACT_PATTERN.findall(text or "")))


def fetch_papers_from_arxiv(categories: List[str], max_results: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch recent papers from arXiv for given categories.
    Uses the arxiv library (synchronous) — we'll call this from an async wrapper.
    """
    papers = []

    for category in categories:
        category = category.strip()
        logger.info(f"Fetching papers for category: {category}")

        # Search for recent papers in this category
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        client = arxiv.Client()
        for result in client.results(search):
            abstract = result.summary.replace("\n", " ").strip()
            artifact_links = _extract_artifacts(abstract)
            paper_data = {
                "arxiv_id": result.entry_id.split("/abs/")[-1],
                "title": result.title.replace("\n", " ").strip(),
                "abstract": abstract,
                "authors": json.dumps([a.name for a in result.authors]),
                "categories": ",".join(result.categories),
                "pdf_url": result.pdf_url,
                "arxiv_url": result.entry_id,
                "published_date": result.published,
                "source": "arxiv",
                "has_artifacts": len(artifact_links) > 0,
                "artifact_links": json.dumps(artifact_links) if artifact_links else None,
            }
            papers.append(paper_data)

    logger.info(f"Fetched {len(papers)} total papers")
    return papers


async def scrape_and_store(db: AsyncSession, categories: List[str], max_results: int = 100) -> int:
    """
    Fetch papers from arXiv and store new ones in the database.
    Returns the count of newly added papers.
    """
    import asyncio

    # Run the synchronous arxiv fetch in a thread pool
    loop = asyncio.get_event_loop()
    papers = await loop.run_in_executor(None, fetch_papers_from_arxiv, categories, max_results)

    new_count = 0
    for paper_data in papers:
        # Check if paper already exists
        result = await db.execute(
            select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            paper = Paper(**paper_data)
            db.add(paper)
            new_count += 1

    await db.commit()
    logger.info(f"Stored {new_count} new papers out of {len(papers)} fetched")
    return new_count


async def get_unscored_papers(db: AsyncSession) -> List[Paper]:
    """Get papers that haven't been scored by the LLM yet."""
    result = await db.execute(
        select(Paper).where(Paper.relevance_score == None).order_by(Paper.published_date.desc())
    )
    return result.scalars().all()
