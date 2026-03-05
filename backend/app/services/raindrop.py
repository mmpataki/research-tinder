"""
Raindrop.io integration service.
Allows saving papers as bookmarks to a Raindrop.io collection.
Requires a Raindrop API test token (get from https://app.raindrop.io/settings/integrations).
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RAINDROP_API = "https://api.raindrop.io/rest/v1"


async def save_to_raindrop(
    token: str,
    title: str,
    link: str,
    excerpt: str = "",
    tags: list = None,
    collection_id: int = -1,  # -1 = Unsorted
) -> dict:
    """
    Save a bookmark to Raindrop.io.
    Returns the created raindrop dict or raises.
    """
    payload = {
        "link": link,
        "title": title,
        "excerpt": excerpt[:500] if excerpt else "",
        "tags": tags or ["research", "paper"],
        "collection": {"$id": collection_id},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RAINDROP_API}/raindrop",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("result"):
        logger.info(f"Saved to Raindrop: {title[:50]}")
        return data.get("item", {})
    else:
        raise Exception(f"Raindrop API error: {data}")


async def get_raindrop_collections(token: str) -> list:
    """Get user's Raindrop collections (for letting user pick one)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{RAINDROP_API}/collections",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {"id": c["_id"], "title": c["title"], "count": c.get("count", 0)}
        for c in data.get("items", [])
    ]


async def test_raindrop_token(token: str) -> bool:
    """Test if a Raindrop token is valid."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{RAINDROP_API}/user",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            return resp.status_code == 200
    except Exception:
        return False
