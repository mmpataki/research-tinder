"""
ACM SIG scraper via the Semantic Scholar Academic Graph API.
Searches for recent papers from specified ACM SIG venues (CHI, SIGKDD, CSCW, etc.)
No API key required for basic usage (rate limited).
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper

logger = logging.getLogger(__name__)

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,abstract,authors,year,externalIds,publicationTypes,venue,publicationDate,openAccessPdf"

# Common artifact URL patterns
ARTIFACT_PATTERN = re.compile(
    r"https?://(?:github\.com|gitlab\.com|zenodo\.org|huggingface\.co|"
    r"paperswithcode\.com|drive\.google\.com|figshare\.com|osf\.io|"
    r"bitbucket\.org|sourceforge\.net)[^\s\"'>)\]]+",
    re.IGNORECASE,
)


def _extract_artifacts(text: str) -> List[str]:
    """Extract artifact URLs from abstract/body text."""
    return list(dict.fromkeys(ARTIFACT_PATTERN.findall(text or "")))


def _build_paper_id(paper: Dict) -> str:
    """Make a stable unique ID for a Semantic Scholar paper."""
    doi = paper.get("externalIds", {}).get("DOI", "")
    arxiv = paper.get("externalIds", {}).get("ArXiv", "")
    s2id = paper.get("paperId", "")
    if arxiv:
        return f"arxiv:{arxiv}"
    if doi:
        return doi.replace("/", "_")
    return f"s2:{s2id}"


def _parse_paper(paper: Dict) -> Optional[Dict[str, Any]]:
    """Convert Semantic Scholar API result to Paper dict."""
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    if not title or not abstract:
        return None

    authors = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]

    # Build URLs
    ext_ids = paper.get("externalIds") or {}
    arxiv_id_raw = ext_ids.get("ArXiv")
    doi = ext_ids.get("DOI")

    if arxiv_id_raw:
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id_raw}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id_raw}"
    elif doi:
        arxiv_url = f"https://doi.org/{doi}"
        pdf_url = (paper.get("openAccessPdf") or {}).get("url") or f"https://doi.org/{doi}"
    else:
        s2id = paper.get("paperId", "")
        arxiv_url = f"https://www.semanticscholar.org/paper/{s2id}"
        pdf_url = (paper.get("openAccessPdf") or {}).get("url") or arxiv_url

    # Date
    pub_date_str = paper.get("publicationDate") or ""
    try:
        pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d") if pub_date_str else datetime(paper.get("year", 2024), 1, 1)
    except ValueError:
        pub_date = datetime(paper.get("year") or 2024, 1, 1)

    # Artifacts
    artifact_links = _extract_artifacts(abstract)

    unique_id = _build_paper_id(paper)
    venue = (paper.get("venue") or "ACM").strip()

    return {
        "arxiv_id": unique_id,
        "title": title,
        "abstract": abstract,
        "authors": json.dumps(authors),
        "categories": venue,
        "pdf_url": pdf_url,
        "arxiv_url": arxiv_url,
        "published_date": pub_date,
        "source": "acm",
        "has_artifacts": len(artifact_links) > 0,
        "artifact_links": json.dumps(artifact_links) if artifact_links else None,
    }


async def fetch_acm_sig_papers(
    sig_names: List[str],
    max_per_sig: int = 50,
    year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch recent papers from ACM SIG venues using the Semantic Scholar API.

    Args:
        sig_names: List of venue/short names e.g. ["CHI", "SIGKDD", "CSCW"]
        max_per_sig: Max results per venue query
        year: Filter to this year (defaults to current year)
    """
    if not sig_names:
        return []

    year = year or datetime.utcnow().year
    papers = []

    headers = {
        "User-Agent": "ResearchTinder/1.0 (research paper recommendation app)",
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        for sig in sig_names:
            sig = sig.strip().upper()
            if not sig:
                continue
            logger.info(f"Fetching ACM {sig} papers from Semantic Scholar")
            try:
                # Query by venue name + year
                params = {
                    "query": f"{sig} {year}",
                    "fields": S2_FIELDS,
                    "limit": max_per_sig,
                    "offset": 0,
                }
                resp = await client.get(S2_SEARCH_URL, params=params)
                if resp.status_code == 429:
                    logger.warning(f"Semantic Scholar rate limit hit for {sig}")
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", [])
                for item in items:
                    parsed = _parse_paper(item)
                    if parsed:
                        papers.append(parsed)
                logger.info(f"Got {len(items)} results for {sig}")
            except Exception as e:
                logger.error(f"Error fetching ACM {sig}: {e}")
                continue

    logger.info(f"Total ACM papers fetched: {len(papers)}")
    return papers


async def scrape_acm_and_store(
    db: AsyncSession,
    sig_names: List[str],
    max_per_sig: int = 50,
) -> int:
    """Fetch ACM SIG papers and store new ones in DB. Returns count of new papers."""
    papers = await fetch_acm_sig_papers(sig_names, max_per_sig=max_per_sig)
    new_count = 0

    for paper_data in papers:
        result = await db.execute(
            select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
        )
        if result.scalar_one_or_none() is None:
            db.add(Paper(**paper_data))
            new_count += 1

    await db.commit()
    logger.info(f"Stored {new_count} new ACM papers out of {len(papers)} fetched")
    return new_count
