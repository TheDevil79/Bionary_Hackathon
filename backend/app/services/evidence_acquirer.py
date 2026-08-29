"""
EvidenceLens — Combined Evidence Acquisition Orchestrator (Phase 7).

Orchestrates:
  1. Local pgvector retrieval
  2. Live web evidence acquisition (Google Search grounding)
  3. Relevance filtering (relevance_score >= 0.35)
  4. Source diversity enforcement (max 2 per domain/source)
  5. Combined score ranking (0.65 * relevance + 0.35 * reliability)
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.claim import AtomicClaim, EvidenceItem
from app.services import evidence_retriever
from app.services.source_reliability import (
    classify_domain,
    compute_combined_score,
    extract_domain,
)
from app.services.web_evidence import web_evidence_service

logger = logging.getLogger(__name__)

RELEVANCE_GATE_THRESHOLD = 0.35


async def acquire_evidence(
    claim: AtomicClaim,
    top_k: int = 5,
) -> list[EvidenceItem]:
    """
    Acquire, filter, merge, and rank evidence from both local corpus and live web.

    Args:
        claim: Atomic sub-claim to gather evidence for.
        top_k: Maximum number of merged evidence items to return.

    Returns:
        List of EvidenceItem objects ranked by combined score descending.
    """
    # 1. Fetch local pgvector evidence
    try:
        local_results = await evidence_retriever.search(claim, top_k=top_k)
    except Exception as exc:
        logger.warning("Local evidence retrieval failed: %s", exc)
        local_results = []

    # 2. Fetch live web evidence (Google Search grounding)
    try:
        web_results = await web_evidence_service.search(claim, max_results=top_k)
    except Exception as exc:
        logger.warning("Web evidence search failed: %s", exc)
        web_results = []

    return merge_and_rank_evidence(local_results, web_results, max_results=top_k)


def merge_and_rank_evidence(
    local_results: list[EvidenceItem],
    web_results: list[EvidenceItem],
    max_results: int = 5,
) -> list[EvidenceItem]:
    """
    Merge local and web evidence sets, enforcing:
      - Relevance gate: relevance_score >= 0.35
      - Source diversity: max 2 items per domain/source
      - Deduplication
      - Combined score ranking (0.65 * relevance + 0.35 * reliability)
    """
    scored_items: list[tuple[EvidenceItem, float]] = []
    seen_identities: set[str] = set()
    domain_counts: dict[str, int] = {}

    # A. Process local corpus items
    for item in local_results:
        # Enforce relevance gate
        if item.relevance_score < RELEVANCE_GATE_THRESHOLD:
            logger.info(
                "[EVIDENCE GATE] Filtered irrelevant local item: '%s' (relevance=%.2f < %.2f)",
                item.title,
                item.relevance_score,
                RELEVANCE_GATE_THRESHOLD,
            )
            continue

        identity = str(item.id)
        if identity in seen_identities:
            continue
        seen_identities.add(identity)

        # Local corpus is verified -> reliability 1.0
        combined = compute_combined_score(item.relevance_score, 1.0)
        scored_items.append((item, combined))

    # B. Process live web items
    for item in web_results:
        # Enforce relevance gate
        if item.relevance_score < RELEVANCE_GATE_THRESHOLD:
            logger.info(
                "[EVIDENCE GATE] Filtered weak web item: '%s' (relevance=%.2f < %.2f)",
                item.title,
                item.relevance_score,
                RELEVANCE_GATE_THRESHOLD,
            )
            continue

        domain = extract_domain(item.url or "")
        if domain:
            if domain_counts.get(domain, 0) >= 2:
                logger.info("[EVIDENCE DIVERSITY] Skipped duplicate domain web item: %s", domain)
                continue
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        url_key = item.url or str(item.id)
        if url_key in seen_identities:
            continue
        seen_identities.add(url_key)

        tier, reliability, _ = classify_domain(domain)
        combined = compute_combined_score(item.relevance_score, reliability)
        scored_items.append((item, combined))

    # Sort by combined score descending
    scored_items.sort(key=lambda pair: pair[1], reverse=True)
    return [pair[0] for pair in scored_items[:max_results]]
