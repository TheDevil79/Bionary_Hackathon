"""
EvidenceLens — Web Evidence Service (Phase 7).

Responsibility:
  1. Build targeted search queries for atomic claims with temporal & primary-source awareness.
  2. Perform Google Search grounding using the modern `google.genai` SDK.
  3. Extract grounded web sources (URL, title, publisher, excerpt) strictly from grounding metadata.
  4. Enforce source reliability policy, source diversity (max 2 per domain), and relevance gating (>= 0.35).
  5. Rank using combined evidence score (0.65 * relevance + 0.35 * reliability).
  6. Return normalized EvidenceItem objects, degrading gracefully on failure.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any

from app.core.config import settings
from app.schemas.claim import AtomicClaim, EvidenceItem, Relationship
from app.services.source_reliability import (
    classify_domain,
    compute_combined_score,
    derive_publisher,
    extract_domain,
)

logger = logging.getLogger(__name__)

# Temporal keywords indicating time-sensitive claims
_TEMPORAL_KEYWORDS = (
    "yesterday",
    "today",
    "this week",
    "recently",
    "currently",
    "breaking",
    "latest",
    "hours ago",
)


class WebEvidenceService:
    """Live web evidence acquisition backed by Gemini Google Search grounding."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model_name = model_name or settings.web_search_model or "gemini-3.6-flash"

    def build_search_query(self, claim: AtomicClaim | str) -> str:
        """Formulate a targeted, factual query for Google Search grounding."""
        text = claim.text if isinstance(claim, AtomicClaim) else str(claim)
        cleaned = text.strip().rstrip(".").strip()

        # Check for temporal terms to prioritize recent/breaking sources
        is_temporal = any(re.search(r"\b" + re.escape(kw) + r"\b", cleaned, re.IGNORECASE) for kw in _TEMPORAL_KEYWORDS)
        
        # Craft focused query prompt for grounding
        if is_temporal:
            return (
                f'Search latest official news, fact checks, or agency reports regarding: "{cleaned}". '
                f"Verify whether this event recently occurred or is a hoax/misinformation."
            )
        return (
            f'Search authoritative scientific, educational, encyclopedia, or official sources regarding: "{cleaned}". '
            f"Provide verifiable facts with primary references."
        )

    async def search(
        self,
        claim: AtomicClaim | str,
        max_results: int = 5,
    ) -> list[EvidenceItem]:
        """
        Search live web for grounding evidence for an atomic claim.
        Tries Gemini Google Search grounding first; if rate-limited (429) or unavailable,
        falls back to direct DuckDuckGo web search.
        """
        claim_text = claim.text if isinstance(claim, AtomicClaim) else str(claim)
        claim_text = claim_text.strip()
        if not claim_text or not settings.web_search_enabled:
            return []

        # 1. Try Gemini Google Search Grounding first (if API key configured)
        if self.api_key:
            try:
                results = await self._execute_grounded_search(claim_text, max_results)
                if results:
                    return results
            except Exception as exc:
                logger.warning(
                    "[WEB SEARCH] Gemini Search grounding failed for '%s': %s — falling back to DuckDuckGo search.",
                    claim_text[:50],
                    exc,
                )

        # 2. Direct Web Search Fallback (DuckDuckGo)
        try:
            logger.info("[WEB SEARCH] Executing DuckDuckGo fallback search for '%s'", claim_text[:50])
            return await self._execute_ddg_search(claim_text, max_results)
        except Exception as exc:
            logger.error("[WEB SEARCH] DuckDuckGo search failed for '%s': %s", claim_text[:50], exc)
            return []

    async def _execute_ddg_search(
        self,
        claim_text: str,
        max_results: int,
    ) -> list[EvidenceItem]:
        """Direct web search via DuckDuckGo with relevance scoring and domain tiering."""
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        query = claim_text.strip().rstrip(".").strip()
        raw_results = []

        def _fetch_ddg(q: str) -> list[dict]:
            try:
                with DDGS(timeout=8.0) as client:
                    return list(client.text(q, max_results=max_results * 2))
            except Exception:
                return []

        raw_results = await asyncio.to_thread(_fetch_ddg, query)
        if not raw_results:
            stopwords = {"a", "an", "the", "that", "proves", "proven", "proves that", "taken", "by", "of", "in", "is", "it", "only", "where"}
            words = [w for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", query) if w.lower() not in stopwords]
            if len(words) >= 2:
                fallback_query = " ".join(words[:7])
                logger.info("[WEB SEARCH DDG] Trying fallback query: '%s'", fallback_query)
                raw_results = await asyncio.to_thread(_fetch_ddg, fallback_query)




        if not raw_results:
            return []

        # Lazy embedder for semantic relevance calculation
        embedder = None
        claim_vec = None
        try:
            from app.ingestion.embedder import get_embedder
            embedder = get_embedder()
            claim_vec = embedder.embed_texts([claim_text])[0]
        except Exception as exc:
            logger.warning("[WEB SEARCH DDG] Embedder unavailable for relevance scoring: %s", exc)


        evidence_items: list[tuple[EvidenceItem, float]] = []
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}

        for item in raw_results:
            raw_url = item.get("href") or item.get("url") or ""
            raw_title = item.get("title") or ""
            raw_body = item.get("body") or item.get("snippet") or ""

            if not raw_url or not raw_url.startswith("http"):
                continue

            normalized_url = raw_url.strip()
            if normalized_url in seen_urls:
                continue

            domain = extract_domain(normalized_url)
            if not domain:
                continue

            tier, reliability_score, tier_label = classify_domain(domain)
            if tier == 4:  # Blocked / spam
                logger.info("[WEB SOURCE DDG] REJECTED (Tier 4 / blocked): url=%s domain=%s", normalized_url, domain)
                continue

            # Diversity: max 2 items per domain
            if domain_counts.get(domain, 0) >= 2:
                continue

            excerpt = raw_body.strip()
            if not excerpt:
                excerpt = raw_title.strip()
            if len(excerpt) > 500:
                excerpt = excerpt[:497] + "..."

            # Compute semantic relevance score
            relevance_score = 0.50
            if embedder and claim_vec and excerpt:
                try:
                    snippet_vec = embedder.embed_texts([f"{raw_title} {excerpt}"])[0]
                    # Cosine similarity for unit vectors
                    dot_prod = sum(a * b for a, b in zip(claim_vec, snippet_vec))
                    relevance_score = max(0.0, min(1.0, float(dot_prod)))
                except Exception:
                    relevance_score = 0.55

            else:
                # Basic overlap heuristic if embedder not ready
                claim_words = set(re.findall(r"\w+", claim_text.lower()))
                snippet_words = set(re.findall(r"\w+", (raw_title + " " + excerpt).lower()))
                overlap = len(claim_words & snippet_words) / max(1, len(claim_words))
                relevance_score = min(0.90, max(0.35, 0.4 + 0.5 * overlap))

            # Relevance gate
            if relevance_score < 0.35:
                logger.info("[WEB SOURCE DDG] Filtered low relevance (%.2f < 0.35): %s", relevance_score, raw_title[:40])
                continue

            combined_score = compute_combined_score(relevance_score, reliability_score)
            ev_id = uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
            publisher = derive_publisher(domain, raw_title)

            evidence_item = EvidenceItem(
                id=ev_id,
                title=raw_title or f"Web Source: {domain}",
                publisher=publisher,
                published_at=None,
                url=normalized_url,
                excerpt=excerpt,
                relationship=Relationship.SUPPORTS,
                relevance_score=round(relevance_score, 3),
            )

            seen_urls.add(normalized_url)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            logger.info(
                "[WEB SOURCE DDG] url=%s domain=%s relevance=%.2f reliability=%.2f combined=%.2f",
                normalized_url,
                domain,
                relevance_score,
                reliability_score,
                combined_score,
            )
            evidence_items.append((evidence_item, combined_score))

        evidence_items.sort(key=lambda pair: pair[1], reverse=True)
        return [pair[0] for pair in evidence_items[:max_results]]


    async def _execute_grounded_search(
        self,
        claim_text: str,
        max_results: int,
    ) -> list[EvidenceItem]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        search_prompt = self.build_search_query(claim_text)

        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.0,
            system_instruction=(
                "You are an objective evidence research agent. "
                "Search for reliable sources, official statements, scientific consensus, or primary documents. "
                "Quote and cite exact factual evidence directly answering the query."
            ),
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=search_prompt,
            config=config,
        )

        if not response or not response.candidates:
            return []

        candidate = response.candidates[0]
        grounding_meta = getattr(candidate, "grounding_metadata", None)
        if not grounding_meta:
            return []

        web_queries = getattr(grounding_meta, "web_search_queries", []) or []
        chunks = getattr(grounding_meta, "grounding_chunks", []) or []
        supports = getattr(grounding_meta, "grounding_supports", []) or []

        logger.info("[WEB SEARCH] claim='%s' queries=%s chunks_found=%d", claim_text[:60], web_queries, len(chunks))

        # Map chunk indices to supporting text snippets if available
        chunk_snippets: dict[int, list[str]] = {}
        for supp in supports:
            indices = getattr(supp, "grounding_chunk_indices", []) or []
            segment = getattr(supp, "segment", None)
            seg_text = getattr(segment, "text", "") if segment else ""
            if seg_text:
                for idx in indices:
                    chunk_snippets.setdefault(idx, []).append(seg_text.strip())

        candidate_body = response.text or ""
        evidence_items: list[tuple[EvidenceItem, float]] = []  # (item, combined_score)
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}

        for idx, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            if not web:
                continue

            raw_url = getattr(web, "uri", "") or ""
            raw_title = getattr(web, "title", "") or ""
            if not raw_url or not raw_url.startswith("http"):
                continue

            # 1. URL Deduplication
            normalized_url = raw_url.strip()
            if normalized_url in seen_urls:
                continue

            # 2. Extract & classify domain
            domain = extract_domain(normalized_url)
            if not domain:
                continue

            tier, reliability_score, tier_label = classify_domain(domain)
            if tier == 4:  # Blocked / spam
                logger.info("[WEB SOURCE] REJECTED (Tier 4 / blocked): url=%s domain=%s", normalized_url, domain)
                continue

            # 3. Source diversity: max 2 items per domain
            if domain_counts.get(domain, 0) >= 2:
                logger.info("[WEB SOURCE] SKIPPED (domain diversity limit reached): domain=%s", domain)
                continue

            # 4. Extract excerpt
            if idx in chunk_snippets and chunk_snippets[idx]:
                excerpt = " ".join(chunk_snippets[idx])
            elif candidate_body:
                # Use a relevant portion of the grounded response text
                excerpt = candidate_body[:400].strip()
            else:
                excerpt = f"Evidence from {raw_title or domain} regarding '{claim_text}'."

            if len(excerpt) > 500:
                excerpt = excerpt[:497] + "..."

            # 5. Determine relevance score
            relevance_score = 0.85
            if tier == 1:
                relevance_score = 0.90
            elif tier == 2:
                relevance_score = 0.85
            else:
                relevance_score = 0.70

            # Relevance Gate: must be >= 0.35
            if relevance_score < 0.35:
                continue

            combined_score = compute_combined_score(relevance_score, reliability_score)

            # Generate stable UUID for evidence item based on URL
            ev_id = uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
            publisher = derive_publisher(domain, raw_title)

            item = EvidenceItem(
                id=ev_id,
                title=raw_title or f"Web Source: {domain}",
                publisher=publisher,
                published_at=None,
                url=normalized_url,
                excerpt=excerpt,
                relationship=Relationship.SUPPORTS,  # Temporary placeholder before VerdictEngine
                relevance_score=relevance_score,
            )

            seen_urls.add(normalized_url)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            logger.info(
                "[WEB SOURCE] url=%s domain=%s relevance=%.2f reliability=%.2f combined_score=%.2f",
                normalized_url,
                domain,
                relevance_score,
                reliability_score,
                combined_score,
            )

            evidence_items.append((item, combined_score))

        # Sort by combined_score descending
        evidence_items.sort(key=lambda pair: pair[1], reverse=True)
        return [pair[0] for pair in evidence_items[:max_results]]


# Global singleton instance
web_evidence_service = WebEvidenceService()
