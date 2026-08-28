"""
Unit tests for VerdictEngine — Phase 4.

All Gemini API calls are mocked. No real API calls are made.
Tests cover:
  - _compute_confidence() directly (verdict thresholds, source deduplication)
  - _aggregate_overall_verdict() directly (aggregation policy)
  - verify() end-to-end (Gemini path, fallback path, error handling)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.core.config import settings
from app.schemas.claim import AtomicClaim, EvidenceItem, Relationship, Verdict
from app.services.verdict_engine import (
    _aggregate_overall_verdict,
    _compute_confidence,
    _fallback_stances,
    verify,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_claim(claim_id: str = "C1", text: str = "Test claim.") -> AtomicClaim:
    return AtomicClaim(
        id=claim_id, text=text,
        verdict=Verdict.INSUFFICIENT_EVIDENCE, confidence=0.0,
    )


def make_evidence(
    n: int,
    relevance: float,
    url: str | None = None,
    publisher: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        id=UUID(f"00000000-0000-0000-0000-{n:012d}"),
        title=f"Test Source {n}",
        publisher=publisher or f"Publisher {n}",
        published_at=None,
        url=url or f"https://example.com/source-{n}",
        excerpt=f"Test excerpt content for source {n}.",
        relationship=Relationship.CONTEXT_MISMATCH,  # placeholder; engine updates this
        relevance_score=relevance,
    )


def mock_assessor(stances: dict[str, str], notes: list[str] | None = None) -> MagicMock:
    """Return a mock _GeminiAssessor whose .assess() returns predetermined stances."""
    m = MagicMock()
    m.assess.return_value = (stances, notes or [])
    return m


# ─── _compute_confidence ──────────────────────────────────────────────────────

class TestComputeConfidence:

    def test_strong_support_returns_supported(self):
        ev = make_evidence(1, 0.9, url="https://imd.gov")
        verdict, conf = _compute_confidence([ev], {str(ev.id): "SUPPORTS"})
        assert verdict == Verdict.SUPPORTED
        assert conf > 0.5

    def test_strong_contradiction_returns_contradicted(self):
        ev = make_evidence(1, 0.9, url="https://factcheck.org")
        verdict, conf = _compute_confidence([ev], {str(ev.id): "CONTRADICTS"})
        assert verdict == Verdict.CONTRADICTED
        assert conf > 0.5

    def test_balanced_evidence_returns_mixed(self):
        ev1 = make_evidence(1, 0.8, url="https://src-a.com")
        ev2 = make_evidence(2, 0.75, url="https://src-b.com")
        verdict, conf = _compute_confidence(
            [ev1, ev2],
            {str(ev1.id): "SUPPORTS", str(ev2.id): "CONTRADICTS"},
        )
        assert verdict == Verdict.MIXED
        assert 0.0 < conf < 0.97

    def test_no_evidence_returns_insufficient(self):
        verdict, conf = _compute_confidence([], {})
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert conf == 0.0

    def test_evidence_below_relevance_threshold_returns_insufficient(self):
        # relevance 0.20 is below RELEVANCE_THRESHOLD=0.35
        ev = make_evidence(1, 0.20)
        verdict, conf = _compute_confidence([ev], {str(ev.id): "SUPPORTS"})
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE

    def test_all_neutral_stances_returns_insufficient(self):
        ev = make_evidence(1, 0.9)
        verdict, conf = _compute_confidence([ev], {str(ev.id): "NEUTRAL"})
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE

    def test_empty_stances_returns_insufficient(self):
        """Fallback mode: all evidence present but no stances determined."""
        ev = make_evidence(1, 0.9)
        verdict, conf = _compute_confidence([ev], {})
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE

    def test_same_source_deduplication(self):
        """3 chunks from the same URL must count as 1 independent source."""
        url = "https://same-source.com/article"
        ev1 = make_evidence(1, 0.85, url=url)
        ev2 = make_evidence(2, 0.80, url=url)
        ev3 = make_evidence(3, 0.75, url=url)
        stances_same = {str(ev1.id): "SUPPORTS", str(ev2.id): "SUPPORTS", str(ev3.id): "SUPPORTS"}
        _, conf_same = _compute_confidence([ev1, ev2, ev3], stances_same)

        # 3 different sources with same relevance scores
        ea = make_evidence(10, 0.85, url="https://src-a.com")
        eb = make_evidence(11, 0.80, url="https://src-b.com")
        ec = make_evidence(12, 0.75, url="https://src-c.com")
        stances_diff = {str(ea.id): "SUPPORTS", str(eb.id): "SUPPORTS", str(ec.id): "SUPPORTS"}
        _, conf_diff = _compute_confidence([ea, eb, ec], stances_diff)

        # More independent sources → higher source_bonus → higher confidence
        assert conf_diff > conf_same

    def test_multiple_independent_supporting_sources_raise_confidence(self):
        ev1 = make_evidence(1, 0.8, url="https://s1.com")
        ev2 = make_evidence(2, 0.75, url="https://s2.com")
        _, conf_two = _compute_confidence(
            [ev1, ev2], {str(ev1.id): "SUPPORTS", str(ev2.id): "SUPPORTS"}
        )
        _, conf_one = _compute_confidence([ev1], {str(ev1.id): "SUPPORTS"})
        assert conf_two > conf_one

    def test_confidence_capped_at_097(self):
        # Many very high-relevance supporting items
        evs = [make_evidence(i, 0.97, url=f"https://src-{i}.com") for i in range(1, 10)]
        stances = {str(e.id): "SUPPORTS" for e in evs}
        _, conf = _compute_confidence(evs, stances)
        assert conf <= 0.97


# ─── _aggregate_overall_verdict ──────────────────────────────────────────────

class TestAggregateOverallVerdict:

    def test_all_supported(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.SUPPORTED, Verdict.SUPPORTED], [0.9, 0.85]
        )
        assert v == Verdict.SUPPORTED

    def test_all_contradicted(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.CONTRADICTED, Verdict.CONTRADICTED], [0.88, 0.82]
        )
        assert v == Verdict.CONTRADICTED

    def test_all_insufficient(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.INSUFFICIENT_EVIDENCE, Verdict.INSUFFICIENT_EVIDENCE], [0.0, 0.0]
        )
        assert v == Verdict.INSUFFICIENT_EVIDENCE

    def test_supported_and_contradicted_gives_mixed(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.SUPPORTED, Verdict.CONTRADICTED], [0.9, 0.85]
        )
        assert v == Verdict.MIXED

    def test_any_mixed_claim_gives_mixed_overall(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.SUPPORTED, Verdict.MIXED], [0.9, 0.6]
        )
        assert v == Verdict.MIXED

    def test_supported_with_insufficient_gives_supported_lower_confidence(self):
        """SUPPORTED + INSUFFICIENT → dominant real verdict but penalised confidence."""
        v, c = _aggregate_overall_verdict(
            [Verdict.SUPPORTED, Verdict.INSUFFICIENT_EVIDENCE], [0.9, 0.0]
        )
        assert v == Verdict.SUPPORTED
        assert c < 0.9   # confidence reduced by penalty

    def test_contradicted_with_insufficient_gives_contradicted_lower_confidence(self):
        v, c = _aggregate_overall_verdict(
            [Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE], [0.85, 0.0]
        )
        assert v == Verdict.CONTRADICTED
        assert c < 0.85

    def test_no_claims_returns_insufficient(self):
        v, c = _aggregate_overall_verdict([], [])
        assert v == Verdict.INSUFFICIENT_EVIDENCE
        assert c == 0.0


# ─── verify() integration ─────────────────────────────────────────────────────

class TestVerifyIntegration:

    @pytest.mark.asyncio
    async def test_strong_support_verdict(self):
        claim = make_claim("C1", "Chennai experienced heavy rainfall.")
        ev = make_evidence(1, 0.9, url="https://imd.gov")
        assessor = mock_assessor({str(ev.id): "SUPPORTS"}, ["IMD confirmed heavy rainfall."])

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.SUPPORTED
        assert result.atomic_claims[0].confidence > 0.0
        assert result.verdict == Verdict.SUPPORTED

    @pytest.mark.asyncio
    async def test_strong_contradiction_verdict(self):
        claim = make_claim("C1", "Chennai experienced no rainfall.")
        ev = make_evidence(1, 0.9, url="https://imd.gov")
        assessor = mock_assessor({str(ev.id): "CONTRADICTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.CONTRADICTED
        assert result.verdict == Verdict.CONTRADICTED

    @pytest.mark.asyncio
    async def test_mixed_evidence_verdict(self):
        claim = make_claim("C1", "Chennai flooding was severe.")
        ev1 = make_evidence(1, 0.8, url="https://imd.gov")
        ev2 = make_evidence(2, 0.75, url="https://altreport.com")
        assessor = mock_assessor({str(ev1.id): "SUPPORTS", str(ev2.id): "CONTRADICTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev1, ev2]}, [ev1, ev2], None)

        assert result.atomic_claims[0].verdict == Verdict.MIXED
        assert result.verdict == Verdict.MIXED

    @pytest.mark.asyncio
    async def test_no_evidence_gives_insufficient(self):
        claim = make_claim("C1", "A unicorn landed at Chennai airport.")

        result = await verify([claim], {"C1": []}, [], None)

        assert result.atomic_claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE

    @pytest.mark.asyncio
    async def test_low_relevance_evidence_gives_insufficient(self):
        claim = make_claim("C1", "Test claim.")
        ev = make_evidence(1, 0.20)  # below RELEVANCE_THRESHOLD
        assessor = mock_assessor({str(ev.id): "SUPPORTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE

    @pytest.mark.asyncio
    async def test_missing_api_key_fallback_gives_insufficient(self):
        """Without GEMINI_API_KEY, all verdicts are INSUFFICIENT_EVIDENCE."""
        claim = make_claim("C1", "Chennai received heavy rainfall.")
        ev = make_evidence(1, 0.9)

        with patch.object(settings, "gemini_api_key", ""):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert result.atomic_claims[0].confidence == 0.0
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE

    @pytest.mark.asyncio
    async def test_gemini_api_exception_graceful_fallback(self):
        """RuntimeError from Gemini must degrade gracefully — never raise."""
        claim = make_claim("C1", "Chennai received heavy rainfall.")
        ev = make_evidence(1, 0.9)
        failing_assessor = MagicMock()
        failing_assessor.assess.side_effect = RuntimeError("ResourceExhausted: quota")

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=failing_assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE
        # uncertainty must mention the fallback
        assert any(
            "fallback" in n.lower() or "failed" in n.lower()
            for n in result.uncertainty
        )

    @pytest.mark.asyncio
    async def test_gemini_malformed_json_graceful_fallback(self):
        """ValueError/JSON parse error must degrade gracefully."""
        claim = make_claim("C1", "Test claim.")
        ev = make_evidence(1, 0.9)
        failing_assessor = MagicMock()
        failing_assessor.assess.side_effect = ValueError("JSON parse error")

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=failing_assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        assert result.atomic_claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert isinstance(result.evidence, list)

    @pytest.mark.asyncio
    async def test_no_atomic_claims_returns_insufficient(self):
        result = await verify([], {}, [], None)
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert result.confidence == 0.0
        assert result.atomic_claims == []

    @pytest.mark.asyncio
    async def test_evidence_ids_preserved_in_output(self):
        """Every evidence ID in the response must originate from the retriever."""
        claim = make_claim("C1", "Test claim.")
        ev = make_evidence(42, 0.9, url="https://source42.com")
        assessor = mock_assessor({str(ev.id): "SUPPORTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev]}, [ev], None)

        response_ids = {str(e.id) for e in result.evidence}
        assert str(ev.id) in response_ids
        # Must not contain fabricated IDs
        assert len(response_ids) == 1

    @pytest.mark.asyncio
    async def test_evidence_relationship_updated_from_gemini_stances(self):
        """EvidenceItem.relationship must reflect the Gemini-assessed stance."""
        claim = make_claim("C1", "Test claim.")
        ev_s = make_evidence(1, 0.9, url="https://s1.com")
        ev_c = make_evidence(2, 0.8, url="https://s2.com")
        assessor = mock_assessor({str(ev_s.id): "SUPPORTS", str(ev_c.id): "CONTRADICTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev_s, ev_c]}, [ev_s, ev_c], None)

        ev_map = {str(e.id): e for e in result.evidence}
        assert ev_map[str(ev_s.id)].relationship == Relationship.SUPPORTS
        assert ev_map[str(ev_c.id)].relationship == Relationship.CONTRADICTS

    @pytest.mark.asyncio
    async def test_multiple_independent_supporting_sources(self):
        """Two independent SUPPORTS sources → SUPPORTED with good confidence."""
        claim = make_claim("C1", "Chennai experienced severe flooding.")
        ev1 = make_evidence(1, 0.85, url="https://imd.gov")
        ev2 = make_evidence(2, 0.80, url="https://ndrf.gov")
        assessor = mock_assessor({str(ev1.id): "SUPPORTS", str(ev2.id): "SUPPORTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev1, ev2]}, [ev1, ev2], None)

        assert result.atomic_claims[0].verdict == Verdict.SUPPORTED
        assert result.atomic_claims[0].confidence > 0.5

    @pytest.mark.asyncio
    async def test_multiple_independent_contradicting_sources(self):
        """Two independent CONTRADICTS sources → CONTRADICTED."""
        claim = make_claim("C1", "The Eiffel Tower was destroyed.")
        ev1 = make_evidence(1, 0.85, url="https://sete.fr")
        ev2 = make_evidence(2, 0.80, url="https://afp.com")
        assessor = mock_assessor({str(ev1.id): "CONTRADICTS", str(ev2.id): "CONTRADICTS"})

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result = await verify([claim], {"C1": [ev1, ev2]}, [ev1, ev2], None)

        assert result.atomic_claims[0].verdict == Verdict.CONTRADICTED

    @pytest.mark.asyncio
    async def test_same_source_chunks_not_counted_as_independent(self):
        """3 chunks from the same URL must not inflate confidence as 3 sources."""
        claim = make_claim("C1", "Test claim.")
        url = "https://single-source.com/article"
        ev1 = make_evidence(1, 0.9, url=url)
        ev2 = make_evidence(2, 0.85, url=url)
        ev3 = make_evidence(3, 0.80, url=url)
        evidence = [ev1, ev2, ev3]
        assessor = mock_assessor(
            {str(ev1.id): "SUPPORTS", str(ev2.id): "SUPPORTS", str(ev3.id): "SUPPORTS"}
        )

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor):
            result_same = await verify([claim], {"C1": evidence}, evidence, None)

        # Compare against 3 truly independent sources
        ea = make_evidence(10, 0.9, url="https://src-a.com")
        eb = make_evidence(11, 0.85, url="https://src-b.com")
        ec = make_evidence(12, 0.80, url="https://src-c.com")
        evidence_diff = [ea, eb, ec]
        assessor_diff = mock_assessor(
            {str(ea.id): "SUPPORTS", str(eb.id): "SUPPORTS", str(ec.id): "SUPPORTS"}
        )

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", return_value=assessor_diff):
            result_diff = await verify(
                [make_claim("C1", "Test claim.")], {"C1": evidence_diff}, evidence_diff, None
            )

        # Same-source should yield lower confidence than independent sources
        assert result_diff.atomic_claims[0].confidence > result_same.atomic_claims[0].confidence

    @pytest.mark.asyncio
    async def test_overall_verdict_multi_claim_mixed(self):
        """Claim 1 SUPPORTED + Claim 2 CONTRADICTED → overall MIXED."""
        c1 = make_claim("C1", "Chennai received rainfall.")
        c2 = make_claim("C2", "No damage was reported.")
        ev1 = make_evidence(1, 0.9, url="https://imd.gov")
        ev2 = make_evidence(2, 0.85, url="https://ndma.gov")

        call_count = 0
        def _factory(*args, **kwargs):
            nonlocal call_count
            m = MagicMock()
            if call_count == 0:
                m.assess.return_value = ({str(ev1.id): "SUPPORTS"}, [])
            else:
                m.assess.return_value = ({str(ev2.id): "CONTRADICTS"}, [])
            call_count += 1
            return m

        with patch.object(settings, "gemini_api_key", "test-key"), \
             patch("app.services.verdict_engine._get_gemini_assessor", side_effect=_factory):
            result = await verify(
                [c1, c2],
                {"C1": [ev1], "C2": [ev2]},
                [ev1, ev2],
                None,
            )

        assert result.verdict == Verdict.MIXED

    @pytest.mark.asyncio
    async def test_fallback_stances_returns_empty_dict(self):
        """_fallback_stances must never assign stances — honest INSUFFICIENT_EVIDENCE."""
        ev = make_evidence(1, 0.95)
        stances = _fallback_stances([ev])
        assert stances == {}

    @pytest.mark.asyncio
    async def test_claim_id_in_response(self):
        """AnalyzeResponse must always contain a valid claim_id UUID."""
        import uuid as _uuid
        claim = make_claim("C1", "Test.")
        result = await verify([claim], {"C1": []}, [], None)
        # Should not raise; claim_id must be parseable
        parsed = _uuid.UUID(str(result.claim_id))
        assert parsed is not None
