"""
EvidenceLens — Claim Extractor Service.

Decomposes raw user input into a list of atomic, verifiable claims using Google Gemini.
Falls back deterministically to rule-based mock extraction when GEMINI_API_KEY is not set.

SDK:  google-genai  (replaces the deprecated google-generativeai package)
      https://googleapis.github.io/python-genai/

Prompt Rules:
  - Extract only factual, independently verifiable claims.
  - Split compound statements into individual atomic sub-claims.
  - Faithfully preserve dates, locations, proper entities, quantities, and causal links.
  - Do NOT hallucinate facts not present in the input.
  - Do NOT evaluate veracity or generate evidence.
  - Output structured JSON matching ClaimExtractionResult.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.claim import AtomicClaim, Verdict

logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


# ─── Structured Output Schemas ────────────────────────────────────────────────

class ExtractedClaimItem(BaseModel):
    """A single atomic factual claim item produced by Gemini."""
    id: str = Field(description="Deterministic sequential identifier, e.g. 'C1', 'C2'")
    text: str = Field(description="Self-contained, independently verifiable factual claim")


class ClaimExtractionResult(BaseModel):
    """Structured response container for atomic claim extraction."""
    claims: list[ExtractedClaimItem] = Field(
        default_factory=list,
        description="List of atomic claims extracted from the input text",
    )


# ─── System Instructions ─────────────────────────────────────────────────────

CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are an expert fact-checking claim decomposition analyst for EvidenceLens.
Your mission is to analyze user-supplied text and decompose it into distinct, atomic, independently verifiable factual claims.

Strict Decomposition Rules:
1. ATOMICITY: Split compound sentences into standalone, individual factual assertions. Each claim must be verifiable on its own.
2. PRESERVATION: Faithfully preserve all specific details from the input:
   - Specific dates, times, and temporal references (e.g. "yesterday", "December 2, 2015").
   - Geographic locations and proper names (e.g. "Chennai", "Marina Beach", "Eiffel Tower").
   - Organizations, institutions, and agencies (e.g. "NASA", "IMD", "SETE").
   - Numbers, measurements, statistics, and quantities (e.g. "142mm", "500 cars", "89.4%").
   - Explicit causal connections stated in the input (e.g. "The Eiffel Tower was closed because of damage").
3. NO HALLUCINATIONS: Do NOT add, infer, or assume any facts not explicitly present in the input text.
4. NO VERDICT / OPINION: Do NOT judge whether claims are true or false. Do NOT generate evidence, explanations, or opinions.
5. DETERMINISTIC IDENTIFIERS: Label extracted claims sequentially as "C1", "C2", "C3", etc.
6. EMPTY / NON-FACTUAL INPUT: If the input text contains no verifiable factual claims (e.g., pure opinions, greetings, insults, or vague questions), return an empty list of claims.
7. ATOMIC PRESERVATION: If the input is already a single atomic claim, do NOT split it further. Return it as "C1".
"""


# ─── Gemini Client Wrapper ───────────────────────────────────────────────────

class _GeminiModelWrapper:
    """
    Thin wrapper around the new google.genai client that exposes a
    `generate_content(prompt: str)` method matching the interface that
    tests mock via `patch("app.services.claim_extractor._get_gemini_model")`.
    """

    def __init__(self, client: Any, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    def generate_content(self, prompt: str) -> Any:
        from google.genai import types  # lazy import keeps startup fast

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClaimExtractionResult,
            temperature=0.0,
            system_instruction=CLAIM_EXTRACTION_SYSTEM_PROMPT,
        )
        return self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )


def _get_gemini_model(api_key: str, model_name: str = DEFAULT_GEMINI_MODEL) -> Any:
    """Initialize and return a configured Gemini model wrapper instance."""
    from google import genai  # lazy import — only loaded when API key is present

    client = genai.Client(api_key=api_key)
    return _GeminiModelWrapper(client=client, model_name=model_name)


# ─── Core Extraction Logic ───────────────────────────────────────────────────

def _call_gemini_extractor(
    text: str, api_key: str, model_name: str = DEFAULT_GEMINI_MODEL
) -> list[AtomicClaim]:
    """Call the Gemini API with structured output and parse the atomic claims."""
    model = _get_gemini_model(api_key=api_key, model_name=model_name)

    prompt = f'Extract all atomic factual claims from the following text:\n\n"""\n{text}\n"""'
    response = model.generate_content(prompt)

    if not response or not response.text:
        logger.warning("Gemini returned an empty response.")
        return []

    try:
        parsed_data = json.loads(response.text)
        result = ClaimExtractionResult.model_validate(parsed_data)
    except Exception as exc:
        logger.warning(
            "Failed to parse Gemini structured JSON response: %s (Raw: %s)",
            exc,
            response.text[:200],
        )
        # Fallback to loose validation if model returned a direct list
        if isinstance(parsed_data, list):
            result = ClaimExtractionResult(
                claims=[
                    ExtractedClaimItem(id=f"C{i+1}", text=item.get("text", str(item)))
                    for i, item in enumerate(parsed_data)
                ]
            )
        else:
            raise ValueError(
                f"Invalid structured output format from Gemini: {exc}"
            ) from exc

    atomic_claims: list[AtomicClaim] = []
    for idx, item in enumerate(result.claims, start=1):
        claim_text = item.text.strip()
        if not claim_text:
            continue
        claim_id = item.id.strip() if item.id and item.id.startswith("C") else f"C{idx}"
        atomic_claims.append(
            AtomicClaim(
                id=claim_id,
                text=claim_text,
                verdict=Verdict.INSUFFICIENT_EVIDENCE,  # placeholder before VerdictEngine
                confidence=0.0,
            )
        )

    return atomic_claims


# ─── Public Interface ─────────────────────────────────────────────────────────

async def extract_claims(
    text: str, model_name: str = DEFAULT_GEMINI_MODEL
) -> list[AtomicClaim]:
    """
    Extract atomic, verifiable claims from user-supplied text.

    If GEMINI_API_KEY is configured in settings, calls Google Gemini.
    Otherwise, uses the deterministic development fallback.

    Args:
        text: Raw text to decompose into atomic claims.
        model_name: Gemini model identifier (default: 'gemini-3.6-flash').

    Returns:
        List of AtomicClaim objects with deterministic IDs (C1, C2, ...).
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        logger.info("Empty text received, returning 0 claims.")
        return []

    api_key = settings.gemini_api_key.strip()

    # 1. Fallback when API key is missing
    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Using deterministic mock claim extraction.")
        return _mock_extract(cleaned_text)

    # 2. Call Gemini
    logger.info(
        "Decomposing text using Gemini (%s, input_len=%d)", model_name, len(cleaned_text)
    )
    try:
        claims = _call_gemini_extractor(cleaned_text, api_key=api_key, model_name=model_name)
        logger.info("Gemini successfully extracted %d atomic claims.", len(claims))
        return claims
    except Exception as exc:
        logger.warning(
            "Gemini claim extraction failed (%s). Using fast deterministic extractor.", exc
        )
        return _mock_extract(cleaned_text)




# ─── Mock Fallback (Development Only) ──────────────────────────────────────────

def _mock_extract(text: str) -> list[AtomicClaim]:
    """
    Deterministic rule-based mock extractor used when GEMINI_API_KEY is not provided.
    Splits compound sentences by punctuation and connectors to simulate decomposition.
    """
    import re

    cleaned = text.strip()
    if not cleaned:
        return []

    # Split by conjunctions ('and', 'because', 'while') or sentence terminators
    clauses = re.split(
        r"(?<=[.!?])\s+|\s+(?:and|because|while|furthermore)\s+",
        cleaned,
        flags=re.IGNORECASE,
    )
    valid_clauses = [c.strip(" .,;:-") for c in clauses if len(c.strip(" .,;:-")) > 5]

    if not valid_clauses:
        valid_clauses = [cleaned]

    return [
        AtomicClaim(
            id=f"C{i + 1}",
            text=clause if clause.endswith(".") else f"{clause}.",
            verdict=Verdict.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
        )
        for i, clause in enumerate(valid_clauses[:5])
    ]
