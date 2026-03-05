"""
LLM service for scoring paper relevance.
Supports multiple providers: Ollama (local), OpenAI, Google Gemini.
Papers are scored in batches for speed.
"""
import json
import logging
from typing import Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.paper import Paper

logger = logging.getLogger(__name__)

BATCH_SIZE = 10

BATCH_PROMPT_TEMPLATE = """You are a research paper relevance scorer.

USER'S RESEARCH INTERESTS:
{interests}

Score each of the following papers for relevance to the user. For each paper return a JSON object with:
- "idx": the paper index (integer, as given)
- "score": float 0.0-1.0 (0.0-0.3 not relevant, 0.3-0.6 somewhat, 0.6-0.8 relevant, 0.8-1.0 highly relevant)
- "reason": one short sentence explaining the score

Respond ONLY with a valid JSON array, no markdown, no extra text. Example:
[{{"idx":0,"score":0.9,"reason":"Directly addresses LLM fine-tuning."}},{{"idx":1,"score":0.2,"reason":"Unrelated to the user's interests."}}]

PAPERS:
{papers_block}"""


def _build_papers_block(papers: list) -> str:
    lines = []
    for i, p in enumerate(papers):
        abstract = p.abstract[:400] + "..." if len(p.abstract) > 400 else p.abstract
        lines.append(f"[{i}] TITLE: {p.title}\nABSTRACT: {abstract}")
    return "\n\n".join(lines)


def _extract_json_list(text: str) -> Optional[list]:
    """Extract a JSON array from text that may contain extra prose."""
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Provider: Ollama (local)
# ---------------------------------------------------------------------------

async def check_ollama_health() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            return resp.status_code == 200
    except Exception:
        return False


async def _call_ollama(prompt: str, max_tokens: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": max_tokens},
            },
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


# ---------------------------------------------------------------------------
# Provider: OpenAI
# ---------------------------------------------------------------------------

async def _call_openai(prompt: str, max_tokens: int, api_key: str, model: str = "gpt-4o-mini") -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Provider: Google Gemini
# ---------------------------------------------------------------------------

async def _call_gemini(prompt: str, max_tokens: int, api_key: str, model: str = "gemini-2.0-flash") -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Unified LLM call
# ---------------------------------------------------------------------------

async def _call_llm(prompt: str, max_tokens: int, provider: str = "ollama",
                     api_key: str = "", model_override: str = "") -> str:
    """Route to the right LLM provider."""
    provider = provider.lower().strip()

    if provider == "openai":
        model = model_override or "gpt-4o-mini"
        return await _call_openai(prompt, max_tokens, api_key, model)
    elif provider == "gemini":
        model = model_override or "gemini-2.0-flash"
        return await _call_gemini(prompt, max_tokens, api_key, model)
    else:
        return await _call_ollama(prompt, max_tokens)


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

async def _score_batch(
    papers: list, interests: str,
    provider: str = "ollama", api_key: str = "", model_override: str = "",
) -> Dict[int, tuple]:
    """Score a batch of papers in one LLM call. Returns {index: (score, reason)}."""
    papers_block = _build_papers_block(papers)
    prompt = BATCH_PROMPT_TEMPLATE.format(interests=interests, papers_block=papers_block)
    num_predict = len(papers) * 80 + 100

    try:
        response_text = await _call_llm(prompt, num_predict, provider, api_key, model_override)
        logger.info(f"LLM response ({provider}): {response_text[:200]}")

        results = _extract_json_list(response_text)
        if not results:
            logger.warning(f"Could not parse batch response: {response_text[:300]}")
            return {}

        parsed = {}
        for item in results:
            idx = int(item.get("idx", -1))
            if 0 <= idx < len(papers):
                score = max(0.0, min(1.0, float(item.get("score", 0.5))))
                reason = item.get("reason", "No reason provided")
                parsed[idx] = (score, reason)
        return parsed

    except Exception as e:
        logger.error(f"Error in batch scoring ({provider}): {e}")
        return {}


async def score_papers(
    db: AsyncSession, papers: list, interests: str,
    provider: str = "ollama", api_key: str = "", model_override: str = "",
) -> int:
    """Score papers in batches and persist results. Returns count scored."""
    scored_count = 0
    total = len(papers)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = papers[batch_start: batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"Scoring batch {batch_num}/{total_batches} ({len(batch)} papers) via {provider}...")

        results = await _score_batch(batch, interests, provider, api_key, model_override)

        for local_idx, (score, reason) in results.items():
            paper = batch[local_idx]
            paper.relevance_score = score
            paper.relevance_reason = reason
            scored_count += 1

        await db.commit()
        logger.info(f"Batch done. Running total scored: {scored_count}/{total}")

    logger.info(f"Finished scoring: {scored_count}/{total} papers scored")
    return scored_count


async def check_provider_health(provider: str, api_key: str = "") -> bool:
    """Check if a given LLM provider is reachable."""
    if provider == "ollama":
        return await check_ollama_health()
    elif provider == "openai":
        if not api_key:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                return resp.status_code == 200
        except Exception:
            return False
    elif provider == "gemini":
        if not api_key:
            return False
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                return resp.status_code == 200
        except Exception:
            return False
    return False
