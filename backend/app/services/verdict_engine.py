"""
EvidenceLens — Evidence-Grounded Verdict Engine (Phase 4).

Architecture:
  For each AtomicClaim supplied with its retrieved evidence:
    1. _assess_claim() calls Gemini to assign a SUPPORTS / CONTRADICTS / NEUTRAL
       stance to every evidence item using ONLY the retrieved excerpts.
    2. _compute_confidence() applies a deterministic formula on stance + relevance
       data to produce a (Verdict, confidence) pair.
  Finally, _aggregate_overall_verdict() combines per-claim results into the
  top-level AnalyzeResponse verdict.

──────────────────────────────────────────────────────────────
Verdict Rules (per-claim):
  SUPPORTED           — support_ratio  ≥ STRONG_THRESHOLD (0.75)
  CONTRADICTED        — contradict_ratio ≥ STRONG_THRESHOLD (0.75)
  MIXED               — neither side dominates (both < 0.75)
  INSUFFICIENT_EVIDENCE — total evidence mass < MIN_EVIDENCE_MASS (0.15),
                          or no evidence provided

Confidence Formula (deterministic, does NOT use Gemini self-reporting):
  1. Filter evidence below RELEVANCE_THRESHOLD (0.35).
  2. Group chunks by source identity (url or title) to de-duplicate.
     → Multiple chunks from the same source count as ONE independent source.
  3. Per source: take max(relevance_score) for SUPPORTS, separately for CONTRADICTS.
  4. support_mass   = sum of per-source SUPPORTS max-scores
     contradict_mass = sum of per-source CONTRADICTS max-scores
     total_mass = support_mass + contradict_mass
  5. dominance = |support_mass − contradict_mass| / total_mass
     mass_factor = min(1.0, total_mass)  ← capped so score stays in [0, 1]
     source_bonus = min(0.10, 0.04 × independent_source_count)
  6. SUPPORTED/CONTRADICTED: confidence = dominance × mass_factor + source_bonus
     MIXED:                  confidence = mass_factor × 0.65 + source_bonus
  All capped at 0.97 (never claim absolute certainty).

Overall Verdict Aggregation Policy:
  All SUPPORTED              → SUPPORTED (avg confidence)
  All CONTRADICTED           → CONTRADICTED (avg confidence)
  All INSUFFICIENT_EVIDENCE  → INSUFFICIENT_EVIDENCE
  No claims at all           → INSUFFICIENT_EVIDENCE
  Real verdicts all same + some INSUFFICIENT
                             → dominant real verdict at 0.85× avg confidence
  Any MIXED in real verdicts → MIXED
  SUPPORTED + CONTRADICTED   → MIXED
  All other mixes            → MIXED

Gemini Usage:
  - One structured API call per atomic claim (not per chunk).
  - Prompt explicitly forbids external knowledge, invented facts, and
    treating semantic similarity as proof.
  - Structured JSON output via google.genai SDK.
  - Full deterministic fallback when GEMINI_API_KEY is absent or call fails.

Fallback Mode (no GEMINI_API_KEY):
  - _fallback_stances() returns {} (no stance determinations).
  - All evidence treated as NEUTRAL → INSUFFICIENT_EVIDENCE.
  - This is honest: without Gemini we cannot determine stance.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.claim import (
    AnalyzeResponse,
    AtomicClaim,
    EvidenceItem,
    MediaAnalysis,
    Relationship,
    Verdict,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_ASSESSMENT_MODEL = "gemini-3.6-flash"
RELEVANCE_THRESHOLD = 0.35   # evidence below this score is too weak to count
MIN_EVIDENCE_MASS   = 0.15   # minimum combined (support+contradict) mass for a verdict
STRONG_THRESHOLD    = 0.75   # one side must hold ≥75 % of mass to be SUPPORTED/CONTRADICTED


# ─── Gemini Structured Output Schemas ─────────────────────────────────────────

class _EvidenceStanceItem(BaseModel):
    """Gemini-assessed stance for one retrieved evidence item."""
    evidence_id: str = Field(
        description="The UUID string of the evidence item, exactly as provided in the prompt."
    )
    stance: str = Field(
        description=(
            "SUPPORTS if the excerpt explicitly confirms the claim. "
            "CONTRADICTS if the excerpt explicitly denies or contradicts the claim. "
            "NEUTRAL if the excerpt is related but does not clearly confirm or deny it."
        )
    )
    reasoning: str = Field(
        description=(
            "1-2 sentences explaining the stance, referencing only the provided excerpt. "
            "Do NOT use outside knowledge."
        )
    )


class _ClaimAssessmentResult(BaseModel):
    """Structured output container for one claim's evidence assessment."""
    assessments: list[_EvidenceStanceItem] = Field(
        description="One assessment per evidence item provided in the prompt."
    )


# ─── System Prompt ────────────────────────────────────────────────────────────

_ASSESSMENT_SYSTEM_PROMPT = """You are an evidence analyst for EvidenceLens, a fact-checking and misinformation detection system.
Your task is to assess the relationship between an atomic factual claim and a set of retrieved evidence excerpts.

STRICT RULES — FOLLOW WITHOUT EXCEPTION:
1. Assess ONLY the evidence excerpts provided. Do NOT use your pretrained knowledge or external memory.
2. Do NOT invent facts, URLs, dates, names, or any information not present in the excerpts.
3. Do NOT treat semantic similarity or keyword overlap as proof. Read what the excerpt actually states.
4. SUPPORTS means the excerpt EXPLICITLY confirms the claim is true, not just related to the topic.
5. CONTRADICTS means the excerpt EXPLICITLY states the claim is false or presents directly opposing facts.
6. NEUTRAL means the excerpt is topically related but does not clearly confirm or contradict the claim.
7. If an excerpt is vague, off-topic, or does not directly address the claim → assign NEUTRAL.
8. If you cannot determine whether evidence supports or contradicts → assign NEUTRAL.
9. Return structured JSON only. Do NOT add commentary outside the JSON schema.
"""


# ─── Gemini Assessor ──────────────────────────────────────────────────────────

class _GeminiAssessor:
    """
    Thin wrapper around the google.genai client for evidence stance assessment.
    Exposes .assess() so tests can mock this entire object cleanly via
    patch("app.services.verdict_engine._get_gemini_assessor").
    """

    def __init__(self, client: Any, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    def assess(
        self,
        claim_text: str,
        evidence_items: list[EvidenceItem],
    ) -> tuple[dict[str, str], list[str]]:
        """
        Call Gemini to assess each evidence item's stance toward the claim.

        Returns:
            stances: dict of str(evidence_id) → "SUPPORTS" | "CONTRADICTS" | "NEUTRAL"
            reasoning_notes: list of reasoning strings for non-NEUTRAL items (for uncertainty field)
        """
        from google.genai import types  # lazy import — only loaded when key is present

        # Build numbered evidence block for the prompt
        evidence_block = "\n\n".join(
            f"[{i + 1}] ID: {item.id}\n"
            f"Title: {item.title}\n"
            f"Publisher: {item.publisher or 'Unknown'}\n"
            f'Excerpt: "{item.excerpt}"'
            for i, item in enumerate(evidence_items)
        )

        user_prompt = (
            f'CLAIM: "{claim_text}"\n\n'
            f"RETRIEVED EVIDENCE:\n{evidence_block}\n\n"
            "Assess each evidence item's stance toward the claim using ONLY the excerpts above."
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_ClaimAssessmentResult,
            temperature=0.0,
            system_instruction=_ASSESSMENT_SYSTEM_PROMPT,
        )

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=user_prompt,
            config=config,
        )

        if not response or not response.text:
            logger.warning("Gemini returned empty assessment response.")
            return {}, []

        # Parse and validate
        parsed = json.loads(response.text)
        result = _ClaimAssessmentResult.model_validate(parsed)

        # Cross-validate returned IDs against our evidence
        valid_ids = {str(item.id) for item in evidence_items}
        stances: dict[str, str] = {}
        reasoning_notes: list[str] = []

        for assessed in result.assessments:
            ev_id = assessed.evidence_id.strip()
            if ev_id not in valid_ids:
                logger.warning("Gemini returned unknown evidence_id '%s' — ignoring.", ev_id)
                continue
            stance = assessed.stance.strip().upper()
            if stance not in ("SUPPORTS", "CONTRADICTS", "NEUTRAL"):
                logger.warning("Gemini returned unknown stance '%s' for %s — treating as NEUTRAL.", stance, ev_id)
                stance = "NEUTRAL"
            stances[ev_id] = stance
            if stance != "NEUTRAL":
                reasoning_notes.append(
                    f"[Evidence {ev_id[:8]}…] {assessed.reasoning.strip()}"
                )

        return stances, reasoning_notes


def _get_gemini_assessor(
    api_key: str,
    model_name: str = DEFAULT_ASSESSMENT_MODEL,
) -> _GeminiAssessor:
    """Initialize and return a configured Gemini assessor. Tests mock this function."""
    from google import genai  # lazy import

    client = genai.Client(api_key=api_key)
    return _GeminiAssessor(client=client, model_name=model_name)


# ─── Confidence Calculation ───────────────────────────────────────────────────

def _source_key(item: EvidenceItem) -> str:
    """Unique identity for a source document — used to de-duplicate chunks."""
    return item.url or item.title


def _compute_confidence(
    evidence_items: list[EvidenceItem],
    stances: dict[str, str],  # str(evidence_id) → "SUPPORTS" | "CONTRADICTS" | "NEUTRAL"
) -> tuple[Verdict, float]:
    """
    Compute the evidence-grounded verdict and confidence for one atomic claim.

    De-duplicates by source identity so multiple chunks from the same document
    do not inflate confidence. Returns (Verdict, confidence ∈ [0.0, 0.97]).
    """
    # source_key → {"support": max_score, "contradict": max_score}
    source_data: dict[str, dict[str, float]] = {}

    for item in evidence_items:
        if item.relevance_score < RELEVANCE_THRESHOLD:
            continue  # too weak to influence verdict
        stance = stances.get(str(item.id), "NEUTRAL")
        if stance == "NEUTRAL":
            continue  # neutral evidence doesn't shift the verdict

        key = _source_key(item)
        if key not in source_data:
            source_data[key] = {"support": 0.0, "contradict": 0.0}

        score = item.relevance_score
        if stance == "SUPPORTS":
            source_data[key]["support"] = max(source_data[key]["support"], score)
        elif stance == "CONTRADICTS":
            source_data[key]["contradict"] = max(source_data[key]["contradict"], score)

    support_mass    = sum(v["support"]    for v in source_data.values())
    contradict_mass = sum(v["contradict"] for v in source_data.values())
    total_mass      = support_mass + contradict_mass
    independent_source_count = len(source_data)

    # Not enough meaningful evidence
    if total_mass < MIN_EVIDENCE_MASS:
        return Verdict.INSUFFICIENT_EVIDENCE, 0.0

    support_ratio = support_mass / total_mass  # always in [0.0, 1.0]

    if support_ratio >= STRONG_THRESHOLD:
        verdict = Verdict.SUPPORTED
    elif support_ratio <= (1.0 - STRONG_THRESHOLD):  # contradict_ratio ≥ STRONG_THRESHOLD
        verdict = Verdict.CONTRADICTED
    else:
        verdict = Verdict.MIXED

    # Deterministic confidence formula
    dominance    = abs(support_mass - contradict_mass) / total_mass  # 0.0 → 1.0
    mass_factor  = min(1.0, total_mass)                               # capped at 1.0
    source_bonus = min(0.10, 0.04 * independent_source_count)

    if verdict == Verdict.MIXED:
        # For MIXED, confidence reflects quantity of evidence, not dominance
        raw_conf = mass_factor * 0.65 + source_bonus
    else:
        raw_conf = dominance * mass_factor + source_bonus

    confidence = round(min(0.97, max(0.05, raw_conf)), 3)
    return verdict, confidence


# ─── Overall Verdict Aggregation ─────────────────────────────────────────────

def _aggregate_overall_verdict(
    per_claim_verdicts: list[Verdict],
    per_claim_confidences: list[float],
) -> tuple[Verdict, float]:
    """
    Combine per-claim verdicts into a single top-level verdict and confidence.

    Policy (deterministic — see module docstring for full table):
      Unanimous             → that verdict at avg confidence
      Real verdicts all same + some INSUFFICIENT
                            → that verdict at 0.85 × avg confidence
      Any MIXED in real set → MIXED
      SUPPORTED + CONTRADICTED → MIXED
      All other mixes       → MIXED
    """
    if not per_claim_verdicts:
        return Verdict.INSUFFICIENT_EVIDENCE, 0.0

    avg_conf = round(sum(per_claim_confidences) / len(per_claim_confidences), 3)
    v_set = set(per_claim_verdicts)

    # Unanimous across all claims
    if len(v_set) == 1:
        return per_claim_verdicts[0], avg_conf

    # Filter out INSUFFICIENT to find real verdicts
    real_verdicts = [v for v in per_claim_verdicts if v != Verdict.INSUFFICIENT_EVIDENCE]
    if not real_verdicts:
        return Verdict.INSUFFICIENT_EVIDENCE, avg_conf

    real_set = set(real_verdicts)

    # Any MIXED in real verdicts → MIXED overall
    if Verdict.MIXED in real_set:
        return Verdict.MIXED, avg_conf

    # All real verdicts are the same (SUPPORTED or CONTRADICTED) with some INSUFFICIENT
    if len(real_set) == 1:
        dominant = real_verdicts[0]
        # Some claims lacked evidence — penalise confidence
        reduced = round(avg_conf * 0.85, 3)
        return dominant, max(0.0, reduced)

    # Real verdicts include both SUPPORTED and CONTRADICTED → MIXED
    return Verdict.MIXED, avg_conf


# ─── Fallback Assessment ──────────────────────────────────────────────────────

def _fallback_stances(evidence_items: list[EvidenceItem]) -> dict[str, str]:
    """
    Deterministic fallback when GEMINI_API_KEY is absent or Gemini fails.

    Without a language model we cannot determine whether an evidence excerpt
    supports or contradicts a claim — semantic similarity is retrieval quality,
    not truth determination. Returning {} means all evidence is treated as NEUTRAL,
    producing an honest INSUFFICIENT_EVIDENCE verdict.
    """
    return {}  # No stance determinations — all evidence treated as NEUTRAL


# ─── Per-claim Assessment ─────────────────────────────────────────────────────

async def _assess_claim(
    claim: AtomicClaim,
    evidence_items: list[EvidenceItem],
    api_key: str,
) -> tuple[AtomicClaim, list[EvidenceItem], list[str]]:
    """
    Assess evidence stance and compute verdict for one atomic claim.

    Returns:
        updated_claim:    AtomicClaim with real verdict + confidence
        updated_evidence: EvidenceItems with Relationship set from Gemini stances
        uncertainty_notes: reasoning lines for the AnalyzeResponse.uncertainty field
    """
    if not evidence_items:
        logger.info("Claim %s: no evidence. → INSUFFICIENT_EVIDENCE", claim.id)
        return (
            AtomicClaim(id=claim.id, text=claim.text,
                        verdict=Verdict.INSUFFICIENT_EVIDENCE, confidence=0.0),
            [],
            [],
        )

    stances: dict[str, str] = {}
    reasoning_notes: list[str] = []

    if api_key:
        logger.info(
            "Claim %s: Gemini assessing %d evidence items.", claim.id, len(evidence_items)
        )
        try:
            assessor = _get_gemini_assessor(api_key)
            stances, reasoning_notes = assessor.assess(claim.text, evidence_items)
            logger.info(
                "Claim %s: Gemini returned stances for %d items.", claim.id, len(stances)
            )
        except Exception as exc:
            logger.error(
                "Gemini assessment failed for claim %s: %s — falling back.", claim.id, exc
            )
            stances = _fallback_stances(evidence_items)
            reasoning_notes = [
                "⚠️ Gemini assessment failed for one or more claims; "
                "using deterministic fallback (INSUFFICIENT_EVIDENCE)."
            ]
    else:
        logger.info(
            "Claim %s: no GEMINI_API_KEY — using deterministic fallback.", claim.id
        )
        stances = _fallback_stances(evidence_items)

    # Compute verdict + confidence from stances
    verdict, confidence = _compute_confidence(evidence_items, stances)

    logger.info(
        "Claim %s → %s (confidence=%.3f) | evidence_ids=[%s]",
        claim.id, verdict.value, confidence,
        ", ".join(str(e.id)[:8] for e in evidence_items),
    )

    # Update EvidenceItem relationship field from assessed stances
    updated_evidence: list[EvidenceItem] = []
    for ev in evidence_items:
        stance = stances.get(str(ev.id), "NEUTRAL")
        if stance == "SUPPORTS":
            rel = Relationship.SUPPORTS
        elif stance == "CONTRADICTS":
            rel = Relationship.CONTRADICTS
        else:
            rel = Relationship.CONTEXT_MISMATCH
        updated_evidence.append(ev.model_copy(update={"relationship": rel}))

    updated_claim = AtomicClaim(
        id=claim.id,
        text=claim.text,
        verdict=verdict,
        confidence=confidence,
    )
    return updated_claim, updated_evidence, reasoning_notes


# ─── Public Interface ─────────────────────────────────────────────────────────

async def verify(
    claims: list[AtomicClaim],
    evidence_per_claim: dict[str, list[EvidenceItem]],
    all_evidence: list[EvidenceItem],
    media_analysis: MediaAnalysis | None,
) -> AnalyzeResponse:
    """
    Produce a final AnalyzeResponse using evidence-grounded verdict computation.

    Args:
        claims:             Atomic claims from the ClaimExtractor.
        evidence_per_claim: Mapping of claim.id → list[EvidenceItem] from EvidenceRetriever.
        all_evidence:       Flat, deduplicated list of all retrieved evidence (for response).
        media_analysis:     Media analysis result, or None if no media was uploaded.

    Returns:
        AnalyzeResponse with real verdicts, confidences, and evidence relationships
        grounded exclusively in the retrieved corpus — no hallucinated facts.
    """
    logger.info(
        "VerdictEngine: %d claims, evidence_per_claim keys=%s",
        len(claims), list(evidence_per_claim.keys()),
    )

    api_key = (settings.gemini_api_key or "").strip()

    updated_claims: list[AtomicClaim] = []
    all_updated_evidence_map: dict[str, EvidenceItem] = {}
    per_claim_verdicts: list[Verdict] = []
    per_claim_confidences: list[float] = []
    uncertainty_notes: list[str] = []

    for claim in claims:
        claim_evidence = evidence_per_claim.get(claim.id, [])
        updated_claim, updated_evidence, reasoning = await _assess_claim(
            claim, claim_evidence, api_key
        )
        updated_claims.append(updated_claim)
        per_claim_verdicts.append(updated_claim.verdict)
        per_claim_confidences.append(updated_claim.confidence)
        uncertainty_notes.extend(reasoning)

        for ev in updated_evidence:
            all_updated_evidence_map[str(ev.id)] = ev

    # Aggregate top-level verdict
    overall_verdict, overall_confidence = _aggregate_overall_verdict(
        per_claim_verdicts, per_claim_confidences
    )
    logger.info(
        "VerdictEngine: overall=%s confidence=%.3f", overall_verdict.value, overall_confidence
    )

    # Media mismatch note
    if media_analysis and media_analysis.context_mismatch:
        uncertainty_notes.append(
            "Uploaded media may have been reused out of context — verify independently."
        )

    # Build final evidence list:
    #   1. All updated items (with assessed stances)
    #   2. Any items from all_evidence not reached by assessment (edge case)
    final_evidence: list[EvidenceItem] = list(all_updated_evidence_map.values())
    assessed_ids = set(all_updated_evidence_map.keys())
    for ev in all_evidence:
        if str(ev.id) not in assessed_ids:
            final_evidence.append(ev)

    return AnalyzeResponse(
        claim_id=uuid.uuid4(),
        atomic_claims=updated_claims,
        verdict=overall_verdict,
        confidence=overall_confidence,
        evidence=final_evidence,
        media_analysis=media_analysis,
        uncertainty=uncertainty_notes,
        analyst_notes=None,
    )
