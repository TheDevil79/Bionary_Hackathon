import pytest
from app.schemas.claim import AtomicClaim, Verdict, EvidenceItem
from app.services.evidence_retriever import search


@pytest.mark.asyncio
async def test_search_empty_query():
    results = await search("   ")
    assert results == []


@pytest.mark.asyncio
async def test_search_with_atomic_claim():
    claim = AtomicClaim(
        id="C1",
        text="Severe waterlogging and rains in Chennai districts.",
        verdict=Verdict.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
    )
    results = await search(claim, top_k=3)
    assert isinstance(results, list)
    # Each result must conform to EvidenceItem with non-empty provenance fields
    for item in results:
        assert isinstance(item, EvidenceItem)
        assert item.title is not None
        assert item.excerpt is not None
        assert 0.0 <= item.relevance_score <= 1.0
