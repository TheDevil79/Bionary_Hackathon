"""
EvidenceLens — Claim Extractor Service.

Responsibility: decompose raw user input into a list of atomic, verifiable claims.

Current state: DEVELOPMENT MOCK
  Returns deterministic demo data so the pipeline can be tested end-to-end
  without a live Gemini API key.

TODO (Phase 2):
  - Replace _mock_extract() with a real Gemini API call.
  - Prompt-engineer the atomic claim decomposition.
  - Handle multi-language input.
"""

from __future__ import annotations

import logging

from app.schemas.claim import AtomicClaim, Verdict

logger = logging.getLogger(__name__)

# ─── Public interface ─────────────────────────────────────────────────────────

async def extract_claims(text: str) -> list[AtomicClaim]:
    """
    Extract atomic, verifiable claims from the user-supplied text.

    Args:
        text: Raw claim text from the /analyze request.

    Returns:
        A list of AtomicClaim objects.
        Each claim has a temporary verdict set to INSUFFICIENT_EVIDENCE;
        the VerdictEngine will update verdicts after evidence retrieval.

    Raises:
        RuntimeError: If the AI service is unavailable.
    """
    logger.info("Extracting claims from text (length=%d)", len(text))

    # TODO: replace with Gemini call in Phase 2
    return _mock_extract(text)


# ─── Mock (development only) ──────────────────────────────────────────────────

def _mock_extract(text: str) -> list[AtomicClaim]:
    """
    ⚠️  DEVELOPMENT MOCK — not real AI output.
    Returns deterministic demo claims derived from the input text.
    Replace this with a Gemini call in Phase 2.
    """
    # Split by full stop to simulate sentence-level claim extraction.
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
    if not sentences:
        sentences = [text.strip()]

    return [
        AtomicClaim(
            id=f"C{i + 1}",
            text=sentence,
            verdict=Verdict.INSUFFICIENT_EVIDENCE,  # placeholder — VerdictEngine overrides
            confidence=0.0,
        )
        for i, sentence in enumerate(sentences[:5])  # cap at 5 for demo
    ]
