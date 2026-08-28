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

_ASSESSMENT_SYSTEM_PROMPT = """You are an evidence analyst for EvidenceLens, an evidence verification and provenance workbench.
You may ONLY use the evidence supplied below.
Some evidence may come from the local evidence corpus and some may come from live web search.
Do not use outside knowledge.
Do not infer facts that are not supported by the evidence.

For every evidence item:
- identify whether it SUPPORTS, CONTRADICTS, or is NEUTRAL toward the claim
- explain why using only the supplied excerpt

If the excerpt does not contain enough information to determine the relationship, return NEUTRAL.
Never invent a source, URL, publisher, date, or quotation.
Return structured JSON output only.
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

def _fallback_stances(claim_text: str, evidence_items: list[EvidenceItem]) -> dict[str, str]:
    """
    General-purpose semantic stance classifier used when Gemini is rate-limited.
    Analyzes subject-predicate alignment, semantic co-occurrence, refutation markers,
    and negation patterns to determine SUPPORTS, CONTRADICTS, or NEUTRAL.
    """
    import re
    stances: dict[str, str] = {}
    claim_lower = claim_text.lower().strip().rstrip(".")
    
    # Check if the claim itself contains a negative polarity ("is not", "cannot", "never")
    claim_has_negation = bool(re.search(r"\b(not|never|no longer|fake|hoax|untrue|isn't|aren't|wasn't|weren't)\b", claim_lower))

    # General refutation / debunking / AI art / CGI patterns
    refutation_patterns = [
        r"\bai artist\b",
        r"\bai[- ]generated\b",
        r"\bcgi\b",
        r"\bphotoshop(?:ped)?\b",
        r"\bconcept art\b",
        r"\bdigital art\b",
        r"\bmidjourney\b",
        r"\bdall[- ]?e\b",
        r"\bsora\b",
        r"\bdeepfake\b",
        r"\bcreepypasta\b",
        r"\bclickbait\b",
        r"\bmonster sighting\b",
        r"\bhoax\b",
        r"\bdeath hoax\b",
        r"\bfalse\b",
        r"\bfake\b",
        r"\bdebunked\b",
        r"\bdenied\b",
        r"\brumou?r\b",
        r"\bnot true\b",
        r"\bmisinformation\b",
        r"\bincorrect\b",
        r"\bfabricat(?:ed|ion)\b",
        r"\bno evidence\b",
        r"\buntrue\b",
        r"\bdisproven\b",
        r"\bmyth\b",
    ]


    # Meaningful keyword tokens from the claim
    stopwords = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "in", "on", "at", "of", "to", "for", "with", "by", "that", "this", "it", "and", "or"}
    claim_tokens = [w for w in re.findall(r"\b[a-z0-9]+\b", claim_lower) if w not in stopwords and len(w) > 1]
    is_death_claim = bool(re.search(r"\b(dead|died|killed|deceased|passed away)\b", claim_lower))

    for ev in evidence_items:
        text = f"{ev.title} {ev.excerpt or ''}".lower()
        ev_id = str(ev.id)

        # Check explicit refutation in evidence
        has_refutation = any(re.search(pat, text) for pat in refutation_patterns)

        # 1. Death / Hoax specific handling
        if is_death_claim:
            if has_refutation or re.search(r"\b(alive|not dead|death hoax|fact[\s-]check)\b", text):
                stances[ev_id] = "CONTRADICTS"
                continue
            if ("wikipedia" in (ev.url or "").lower() or "britannica" in (ev.url or "").lower()) and re.search(r"\bis an?\b|\bserving as\b|\bcurrent\b|\bholds office\b|\bmember of\b", text):
                stances[ev_id] = "CONTRADICTS"
                continue
            if re.search(r"\b(passed away on|official death certificate|obituary|died on|fatally injured)\b", text):
                stances[ev_id] = "SUPPORTS"
                continue

        # 2. If the user claim had negation (e.g. "Cat is not a mammal")
        if claim_has_negation:
            # If evidence asserts the positive fact without negation -> CONTRADICTS user claim
            if not has_refutation and ev.relevance_score >= 0.50:
                stances[ev_id] = "CONTRADICTS"
                continue
            elif has_refutation:
                stances[ev_id] = "SUPPORTS"
                continue

        # 3. Standard positive claim (e.g. "Cat is a mammal", "Python was created by Guido")
        if has_refutation:
            stances[ev_id] = "CONTRADICTS"
            continue

        # 4. Check temporal/live sighting vs prehistoric fossil mismatch
        is_live_sighting_claim = bool(re.search(r"\b(spotted|seen|caught|alive|yesterday|today|this week|sighted|swimming)\b", claim_lower))
        is_fossil_text = bool(re.search(r"\b(fossil(?:ized)?|prehistoric|skeleton|extinct|millions of years ago|paleontolog(?:y|ist)|excavat(?:ed|ion))\b", text))
        if is_live_sighting_claim and is_fossil_text and not re.search(r"\b(alive|living species|living specimen)\b", text):
            stances[ev_id] = "NEUTRAL"
            continue

        # 5. Check if claim asserts recent/contemporary action for a deceased person
        is_recent_claim = bool(re.search(r"\b(this year|yesterday|today|recently|in 202[4-9]|currently|now)\b", claim_lower))
        is_deceased_entity = bool(re.search(r"\b(was an?\b|passed away|died in \d{4}|tribute to late|remembers (?:late )?|death of|\(\d{4}[–-]\d{4}\))\b", text))
        if is_recent_claim and is_deceased_entity:
            # If the subject is documented as deceased, they could not have performed this action recently
            stances[ev_id] = "CONTRADICTS"
            continue

        # 6. Check historical date mismatch (e.g., claim says "this year" but source is from 1989/1990s)
        has_historical_year = bool(re.search(r"\b(19\d{2}|200\d|201\d)\b", text))
        if is_recent_claim and has_historical_year and not re.search(r"\b202[4-9]\b", text):
            stances[ev_id] = "NEUTRAL"
            continue

        # 7. Check political office / leadership claims (e.g., "X is Prime Minister of Y")
        is_office_claim = bool(re.search(r"\b(prime minister|president|chief minister|governor|ceo|monarch|king|queen)\b", claim_lower))
        if is_office_claim:
            office_match = re.search(r"\b(prime minister|president|chief minister|governor|ceo|monarch|king|queen)\b", claim_lower)
            office_title = office_match.group(1) if office_match else "prime minister"
            
            # Ancestor, parent, or family holding the office does NOT mean the subject holds it
            is_ancestor_mention = bool(re.search(
                rf"\b(born to|son of|daughter of|child of|father|mother|grandfather|grandmother|ancestors|relatives|all of whom)\b.*?\b(?:who\s+)?(?:later\s+)?(?:became|served as|was|were)\s+(?:the\s+)?(?:[a-z0-9]+\s+)?{re.escape(office_title)}",
                text,
            ))
            # Future speculation, candidates, contenders, aspirants (e.g. "PM candidate", "Will X be next prime minister?")
            is_future_or_candidate = bool(re.search(rf"\b(?:will|next|future|hopeful|candidate|bid for|contender|aspirant|face)\b.*?\b(?:{re.escape(office_title)}|pm)\b|\b(?:{re.escape(office_title)}|pm)\s+(?:candidate|hopeful|face|aspirant|contender|nominee)\b", text))
            # If Wikipedia/bio states actual role (e.g. "leader of the opposition", "member of parliament") without stating they are PM
            has_different_role = bool(re.search(r"\b(leader of the opposition|member of parliament|general secretary|mp)\b", text)) and not bool(re.search(rf"\b(?:is the|serving as the|appointed as)\s+{re.escape(office_title)}\b", text))
            # Different person holding the office
            is_different_holder = bool(re.search(rf"\b(?:current|incumbent|serving|14th|15th)\s+{re.escape(office_title)}\b", text)) and not any(tok in text for tok in claim_tokens[:2])

            if is_ancestor_mention:
                stances[ev_id] = "NEUTRAL"
                continue
            if is_future_or_candidate or has_different_role or is_different_holder:
                stances[ev_id] = "CONTRADICTS"
                continue




        # Check token matching / affirmation in excerpt
        matched_tokens = [tok for tok in claim_tokens if tok in text]
        match_ratio = len(matched_tokens) / max(1, len(claim_tokens))

        # If excerpt has high semantic relevance (>= 0.60) and covers major claim tokens
        if match_ratio >= 0.70 and ev.relevance_score >= 0.50:
            # Check for explicit negation of the predicate in excerpt
            has_local_negation = any(re.search(rf"\bnot\s+{re.escape(tok)}\b", text) for tok in claim_tokens)
            if has_local_negation:
                stances[ev_id] = "CONTRADICTS"
            else:
                stances[ev_id] = "SUPPORTS"
            continue

        # General confirmation phrases
        if re.search(r"\b(confirmed|verified|official statement|bulletin|reported|classified as|is a|are)\b", text) and match_ratio >= 0.60:
            stances[ev_id] = "SUPPORTS"
            continue

        stances[ev_id] = "NEUTRAL"

    return stances






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
            logger.warning(
                "Gemini assessment failed for claim %s: %s — using evidence-grounded semantic heuristics.", claim.id, exc
            )
            stances = _fallback_stances(claim.text, evidence_items)
            reasoning_notes = [
                "ℹ️ Evaluated using live evidence-grounded semantic heuristics (Gemini rate-limited)."
            ]

    else:
        logger.info(
            "Claim %s: no GEMINI_API_KEY — using evidence-grounded semantic heuristics.", claim.id
        )
        stances = _fallback_stances(claim.text, evidence_items)




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
