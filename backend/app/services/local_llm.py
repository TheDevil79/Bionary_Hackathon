"""
EvidenceLens — Local LLM Client (Ollama).

Provides Gemma (or any Ollama-hosted model) as a drop-in fallback when the
Gemini API is rate-limited (HTTP 429) or quota-exhausted.

Uses Ollama's OpenAI-compatible REST endpoint so no extra SDK is needed.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 180.0  # seconds — allows warmup and inference on CPU/GPU


def _ollama_available() -> bool:
    """Quick liveness check against the Ollama server."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _chat(system: str, user: str, model: str | None = None) -> str:
    """
    Send a chat request to Ollama and return the assistant's text response.
    Uses the /api/chat endpoint (OpenAI-compatible style).
    """
    model = model or getattr(settings, "ollama_model", "gemma3:4b")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0},
    }
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def _extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a response string."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Find first [...] block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in response: {text[:300]}")


# ─── Claim Extraction ─────────────────────────────────────────────────────────

_CLAIM_SYSTEM = """You are a fact-checking claim decomposition analyst.
Given text, extract all atomic, independently verifiable factual claims.
Rules:
- Split compound statements into individual atomic assertions.
- Preserve all specific details: dates, names, numbers, locations.
- Do NOT add facts not in the input.
- Do NOT judge truth or generate evidence.
- Label claims sequentially: C1, C2, C3...
- If the text is a single atomic claim, return it as C1.
- Return ONLY valid JSON matching: {"claims": [{"id": "C1", "text": "..."}]}"""


def extract_claims_local(text: str) -> list[dict]:
    """
    Extract atomic claims from text using a local Ollama model.
    Returns a list of {"id": "C1", "text": "..."} dicts.
    """
    if not _ollama_available():
        logger.warning("[LOCAL LLM] Ollama not running — cannot extract claims locally.")
        return []

    model = getattr(settings, "ollama_model", "gemma3:4b")
    logger.info("[LOCAL LLM] Extracting claims via Ollama (%s).", model)

    prompt = (
        f'Extract all atomic factual claims from the following text:\n\n"""\n{text}\n"""'
        "\n\nReturn ONLY JSON, no explanation."
    )
    try:
        raw = _chat(system=_CLAIM_SYSTEM, user=prompt, model=model)
        data = _extract_json(raw)
        claims = data.get("claims", []) if isinstance(data, dict) else data
        logger.info("[LOCAL LLM] Extracted %d claims.", len(claims))
        return claims
    except Exception as exc:
        logger.error("[LOCAL LLM] Claim extraction failed: %s", exc)
        return []


# ─── Stance Assessment ────────────────────────────────────────────────────────

_STANCE_SYSTEM = """You are a strict evidence stance assessor for a fact-checking system.
Given a factual claim and a list of evidence excerpts, assess each evidence item's stance.
Rules:
- ONLY use information explicitly stated in the provided excerpts.
- Do NOT use external knowledge or make assumptions.
- SUPPORTS: excerpt explicitly confirms the claim.
- CONTRADICTS: excerpt explicitly denies or refutes the claim.
- NEUTRAL: excerpt is related but does not clearly support or contradict.
- Return ONLY valid JSON: {"stances": {"<evidence_id>": "SUPPORTS"|"CONTRADICTS"|"NEUTRAL"}}"""


def assess_stances_local(claim_text: str, evidence_items: list[dict]) -> dict[str, str]:
    """
    Assess the stance of each evidence item against the claim using a local Ollama model.
    Returns a dict mapping evidence_id -> "SUPPORTS" | "CONTRADICTS" | "NEUTRAL".
    """
    if not evidence_items:
        return {}

    if not _ollama_available():
        logger.warning("[LOCAL LLM] Ollama not running — cannot assess stances locally.")
        return {}

    model = getattr(settings, "ollama_model", "gemma3:4b")
    logger.info("[LOCAL LLM] Assessing %d evidence stances via Ollama (%s).", len(evidence_items), model)

    # Build evidence block
    ev_lines = []
    for ev in evidence_items:
        ev_lines.append(
            f"[{ev['id']}] Source: {ev.get('publisher', 'Unknown')}\n"
            f"Title: {ev.get('title', '')}\n"
            f"Excerpt: {ev.get('excerpt', '')}"
        )
    evidence_block = "\n\n".join(ev_lines)

    prompt = (
        f"Claim: \"{claim_text}\"\n\n"
        f"Evidence Items:\n{evidence_block}\n\n"
        "Assess each evidence item's stance toward the claim. "
        "Return ONLY JSON: {\"stances\": {\"<id>\": \"SUPPORTS\"|\"CONTRADICTS\"|\"NEUTRAL\"}}"
    )

    try:
        raw = _chat(system=_STANCE_SYSTEM, user=prompt, model=model)
        data = _extract_json(raw)
        stances = data.get("stances", {}) if isinstance(data, dict) else {}
        logger.info("[LOCAL LLM] Stances assessed: %s", stances)
        return {str(k): str(v).upper() for k, v in stances.items()}
    except Exception as exc:
        logger.error("[LOCAL LLM] Stance assessment failed: %s", exc)
        return {}
