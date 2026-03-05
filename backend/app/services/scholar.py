"""
Google Scholar profile scraper.
Given a Scholar profile URL, fetches the author's recent publications
and converts them into the same format as arXiv papers.
"""
import json
import logging
import re
from typing import List, Dict, Any
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper

logger = logging.getLogger(__name__)

SCHOLAR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_user_id(url: str) -> str:
    """Extract the user ID from a Google Scholar profile URL."""
    match = re.search(r"user=([^&]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract user ID from URL: {url}")


async def fetch_scholar_profile(profile_url: str, max_papers: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch publications from a Google Scholar profile page.
    Returns list of paper dicts in the same format as arXiv scraper output.
    """
    user_id = _extract_user_id(profile_url)
    papers = []

    # Fetch the profile page with publications sorted by date
    url = (
        f"https://scholar.google.com/citations"
        f"?user={user_id}&hl=en&sortby=pubdate&cstart=0&pagesize={max_papers}"
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, headers=SCHOLAR_HEADERS, timeout=30.0)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Each publication row has class "gsc_a_tr"
    rows = soup.select("tr.gsc_a_tr")
    logger.info(f"Found {len(rows)} publications on Scholar profile {user_id}")

    for row in rows:
        title_el = row.select_one("a.gsc_a_at")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        detail_link = title_el.get("href", "")
        if detail_link and not detail_link.startswith("http"):
            detail_link = f"https://scholar.google.com{detail_link}"

        # Authors and venue info
        gray_els = row.select("div.gs_gray")
        authors = gray_els[0].get_text(strip=True) if len(gray_els) > 0 else "Unknown"
        venue = gray_els[1].get_text(strip=True) if len(gray_els) > 1 else ""

        # Year
        year_el = row.select_one("span.gsc_a_h")
        year_str = year_el.get_text(strip=True) if year_el else ""
        try:
            pub_year = int(year_str) if year_str else datetime.utcnow().year
        except ValueError:
            pub_year = datetime.utcnow().year

        # Generate a unique ID based on title hash
        scholar_id = f"scholar_{abs(hash(title + authors))}"

        paper_data = {
            "arxiv_id": scholar_id,
            "title": title,
            "abstract": f"[Google Scholar] {venue}. Authors: {authors}",
            "authors": json.dumps([a.strip() for a in authors.split(",")]),
            "categories": "scholar",
            "pdf_url": detail_link,
            "arxiv_url": detail_link,
            "published_date": datetime(pub_year, 1, 1),
        }
        papers.append(paper_data)

    return papers


async def fetch_scholar_paper_details(detail_url: str) -> str:
    """
    Fetch the detail page of a Scholar paper to try to get the abstract.
    Returns abstract text or empty string.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(detail_url, headers=SCHOLAR_HEADERS, timeout=15.0)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        # The abstract is in div#gsc_oci_descr
        abstract_div = soup.select_one("div#gsc_oci_descr")
        if abstract_div:
            return abstract_div.get_text(strip=True)
    except Exception as e:
        logger.warning(f"Could not fetch Scholar detail page: {e}")

    return ""


async def scrape_scholar_and_store(
    db: AsyncSession, profile_urls: List[str], max_per_profile: int = 30
) -> int:
    """
    Fetch papers from Google Scholar profiles and store new ones.
    Optionally fetches abstracts from detail pages.
    Returns count of newly added papers.
    """
    new_count = 0

    for url in profile_urls:
        url = url.strip()
        if not url:
            continue

        try:
            logger.info(f"Scraping Scholar profile: {url}")
            papers = await fetch_scholar_profile(url, max_papers=max_per_profile)

            for paper_data in papers:
                # Check if already exists
                result = await db.execute(
                    select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    # Try to fetch abstract from detail page
                    if paper_data["pdf_url"]:
                        abstract = await fetch_scholar_paper_details(paper_data["pdf_url"])
                        if abstract:
                            paper_data["abstract"] = abstract

                    paper = Paper(**paper_data)
                    db.add(paper)
                    new_count += 1

            await db.commit()
            logger.info(f"Added {new_count} papers from {url}")

        except Exception as e:
            logger.error(f"Failed to scrape Scholar profile {url}: {e}")
            continue

    return new_count
