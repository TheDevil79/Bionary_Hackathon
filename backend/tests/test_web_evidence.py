"""
EvidenceLens — Web Evidence & Source Reliability Unit Tests (Phase 7).

All tests use deterministic mocks; NO external network or Gemini API calls are made.
"""

from __future__ import annotations

import unittest.mock as mock
import uuid
import pytest

from app.schemas.claim import AtomicClaim, EvidenceItem, Relationship, Verdict
from app.services import evidence_acquirer, source_reliability
from app.services.source_reliability import (
    classify_domain,
    compute_combined_score,
    derive_publisher,
    extract_domain,
)
from app.services.web_evidence import WebEvidenceService


# ─── Source Reliability Tests ──────────────────────────────────────────────────

def test_extract_domain():
    assert extract_domain("https://www.who.int/news/item/123") == "who.int"
    assert extract_domain("http://en.wikipedia.org/wiki/Cat") == "en.wikipedia.org"
    assert extract_domain("http://www2.cdc.gov/path") == "cdc.gov"
    assert extract_domain("nature.com/articles/s41586") == "nature.com"
    assert extract_domain("") == ""


def test_tier_1_trusted_domain():
    tier, score, label = classify_domain("who.int")
    assert tier == 1
    assert score == 1.0
    assert label == "TIER_1_HIGH_TRUST"

    tier, score, _ = classify_domain("https://news.un.org/en/story")
    assert tier == 1
    assert score == 1.0

    tier, score, _ = classify_domain("https://mausam.imd.gov.in/forecast")
    assert tier == 1
    assert score == 1.0


def test_tier_1_trusted_suffixes():
    tier, score, _ = classify_domain("https://state.gov")
    assert tier == 1
    assert score == 1.0

    tier, score, _ = classify_domain("https://gov.uk/guidance")
    assert tier == 1
    assert score == 1.0

    tier, score, _ = classify_domain("https://mit.edu")
    assert tier == 1
    assert score == 1.0

    tier, score, _ = classify_domain("https://ox.ac.uk")
    assert tier == 1
    assert score == 1.0


def test_tier_2_trusted_domain():
    tier, score, label = classify_domain("https://en.wikipedia.org/wiki/Mammal")
    assert tier == 2
    assert score == 0.8
    assert label == "TIER_2_GENERALLY_RELIABLE"

    tier, score, _ = classify_domain("https://www.reuters.com/world")
    # Reuters is configured in tier 1
    assert tier == 1
    assert score == 1.0

    tier, score, _ = classify_domain("https://theguardian.com/world")
    assert tier == 2
    assert score == 0.8


def test_tier_3_general_source():
    tier, score, label = classify_domain("https://myrandomblog123.com/post")
    assert tier == 3
    assert score == 0.4
    assert label == "TIER_3_LOW_TRUST"


def test_tier_4_blocked_domain():
    tier, score, label = classify_domain("https://clickbait.example/article")
    assert tier == 4
    assert score == 0.0
    assert label == "TIER_4_REJECT"


def test_derive_publisher():
    assert derive_publisher("https://www.who.int") == "World Health Organization"
    assert derive_publisher("https://nature.com/articles/123") == "Nature"
    assert derive_publisher("https://en.wikipedia.org") == "Wikipedia"
    assert derive_publisher("https://customnews.org") == "Customnews"


def test_combined_score_formula():
    # 0.65 * 0.90 + 0.35 * 1.0 = 0.585 + 0.35 = 0.935
    assert compute_combined_score(0.90, 1.0) == 0.935
    # 0.65 * 0.70 + 0.35 * 0.4 = 0.455 + 0.14 = 0.595
    assert compute_combined_score(0.70, 0.4) == 0.595


# ─── Web Evidence Service Tests (Mocked) ───────────────────────────────────────

class MockWebChunk:
    def __init__(self, uri: str, title: str):
        self.web = mock.MagicMock()
        self.web.uri = uri
        self.web.title = title


class MockGroundingSupport:
    def __init__(self, indices: list[int], text: str):
        self.grounding_chunk_indices = indices
        self.segment = mock.MagicMock()
        self.segment.text = text


class MockCandidate:
    def __init__(self, chunks, supports=None, queries=None):
        self.grounding_metadata = mock.MagicMock()
        self.grounding_metadata.grounding_chunks = chunks
        self.grounding_metadata.grounding_supports = supports or []
        self.grounding_metadata.web_search_queries = queries or ["mock search query"]


class MockGenerateResponse:
    def __init__(self, text: str, chunks, supports=None):
        self.text = text
        self.candidates = [MockCandidate(chunks, supports)]


@pytest.mark.asyncio
async def test_successful_web_search():
    service = WebEvidenceService(api_key="mock_key")

    mock_chunks = [
        MockWebChunk("https://nature.com/articles/cat-mammal", "Nature: Felis catus taxonomy"),
        MockWebChunk("https://en.wikipedia.org/wiki/Cat", "Cat - Wikipedia"),
    ]
    mock_supports = [
        MockGroundingSupport([0], "Cats are obligate carnivores belonging to the class Mammalia."),
        MockGroundingSupport([1], "The cat is a domestic species of small carnivorous mammal."),
    ]
    mock_resp = MockGenerateResponse("Cats are mammals.", mock_chunks, mock_supports)

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Cat is a mammal", verdict=Verdict.SUPPORTED, confidence=0.9)
        results = await service.search(claim, max_results=5)

        assert len(results) == 2
        assert results[0].url == "https://nature.com/articles/cat-mammal"
        assert results[0].publisher == "Nature"
        assert "Mammalia" in results[0].excerpt
        assert results[1].url == "https://en.wikipedia.org/wiki/Cat"


@pytest.mark.asyncio
async def test_no_grounding_results():
    service = WebEvidenceService(api_key="mock_key")
    mock_resp = MockGenerateResponse("No sources found.", [])

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Alien sighting", verdict=Verdict.SUPPORTED, confidence=0.5)
        results = await service.search(claim)
        assert results == []


@pytest.mark.asyncio
async def test_malformed_grounding_metadata():
    service = WebEvidenceService(api_key="mock_key")
    mock_resp = mock.MagicMock()
    mock_resp.candidates = [mock.MagicMock(grounding_metadata=None)]

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Unstructured", verdict=Verdict.SUPPORTED, confidence=0.5)
        results = await service.search(claim)
        assert results == []


@pytest.mark.asyncio
async def test_duplicate_urls():
    service = WebEvidenceService(api_key="mock_key")

    mock_chunks = [
        MockWebChunk("https://who.int/news/health", "WHO Health Article"),
        MockWebChunk("https://who.int/news/health", "WHO Health Article Duplicate"),
    ]
    mock_resp = MockGenerateResponse("Summary", mock_chunks)

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Health bulletin", verdict=Verdict.SUPPORTED, confidence=0.8)
        results = await service.search(claim)
        assert len(results) == 1
        assert results[0].url == "https://who.int/news/health"


@pytest.mark.asyncio
async def test_source_diversity_max_2_per_domain():
    service = WebEvidenceService(api_key="mock_key")

    mock_chunks = [
        MockWebChunk("https://example.com/article1", "Article 1"),
        MockWebChunk("https://example.com/article2", "Article 2"),
        MockWebChunk("https://example.com/article3", "Article 3"),
        MockWebChunk("https://bbc.com/news/1", "BBC 1"),
    ]
    mock_resp = MockGenerateResponse("Diverse sources", mock_chunks)

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Incident report", verdict=Verdict.SUPPORTED, confidence=0.8)
        results = await service.search(claim)

        # Example.com should only appear 2 times, BBC 1 time = 3 items total
        assert len(results) == 3
        domain_counts = [item.url for item in results if "example.com" in item.url]
        assert len(domain_counts) == 2


@pytest.mark.asyncio
async def test_blocked_domain_filtering():
    service = WebEvidenceService(api_key="mock_key")

    mock_chunks = [
        MockWebChunk("https://clickbait.example/shocking", "Fake Shocking Headline"),
        MockWebChunk("https://reuters.com/world/article", "Reuters Official Report"),
    ]
    mock_resp = MockGenerateResponse("Summary", mock_chunks)

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="News story", verdict=Verdict.SUPPORTED, confidence=0.8)
        results = await service.search(claim)

        assert len(results) == 1
        assert results[0].url == "https://reuters.com/world/article"


@pytest.mark.asyncio
async def test_google_api_failure_fallback():
    service = WebEvidenceService(api_key="mock_key")

    with mock.patch("google.genai.Client") as mock_client_cls:
        mock_client = mock.MagicMock()
        mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable / Quota limit")
        mock_client_cls.return_value = mock_client

        claim = AtomicClaim(id="C1", text="Fallback query", verdict=Verdict.SUPPORTED, confidence=0.8)
        results = await service.search(claim)
        # Must gracefully degrade to empty list without raising
        assert results == []


def test_build_search_query_temporal_awareness():
    service = WebEvidenceService(api_key="mock_key")
    claim_temporal = AtomicClaim(id="C1", text="A meteorite hit Eiffel Tower yesterday.", verdict=Verdict.SUPPORTED, confidence=0.5)
    query_temporal = service.build_search_query(claim_temporal)
    assert "recently occurred" in query_temporal or "latest" in query_temporal.lower() or "news" in query_temporal.lower()

    claim_static = AtomicClaim(id="C2", text="Cat is a mammal.", verdict=Verdict.SUPPORTED, confidence=0.5)
    query_static = service.build_search_query(claim_static)
    assert "scientific" in query_static.lower() or "encyclopedia" in query_static.lower() or "authoritative" in query_static.lower()


# ─── Combined Evidence Acquirer Tests ─────────────────────────────────────────

def test_evidence_acquirer_relevance_gate_and_merging():
    # Local item below relevance threshold (< 0.35) e.g. Palk Strait for cat query
    irrelevant_local = EvidenceItem(
        id=uuid.uuid4(),
        title="Geological Survey: Palk Strait Subsea",
        publisher="Survey Bureau",
        published_at=None,
        url="https://example.com/palk-strait",
        excerpt="Underwater geology survey report.",
        relationship=Relationship.CONTEXT_MISMATCH,
        relevance_score=0.22,  # < 0.35 -> MUST be filtered
    )

    relevant_local = EvidenceItem(
        id=uuid.uuid4(),
        title="Verified Local Report",
        publisher="National Archives",
        published_at=None,
        url="https://example.com/local-valid",
        excerpt="Local archival proof.",
        relationship=Relationship.SUPPORTS,
        relevance_score=0.88,  # >= 0.35
    )

    web_item = EvidenceItem(
        id=uuid.uuid4(),
        title="Live Web Verification",
        publisher="Nature",
        published_at=None,
        url="https://nature.com/articles/live-cat",
        excerpt="Scientific consensus on mammalian taxonomy.",
        relationship=Relationship.SUPPORTS,
        relevance_score=0.90,  # >= 0.35
    )

    merged = evidence_acquirer.merge_and_rank_evidence(
        local_results=[irrelevant_local, relevant_local],
        web_results=[web_item],
        max_results=5,
    )

    # Irrelevant local item must be rejected
    titles = [item.title for item in merged]
    assert "Geological Survey: Palk Strait Subsea" not in titles
    assert "Verified Local Report" in titles
    assert "Live Web Verification" in titles
    assert len(merged) == 2
