"""
Phase 2 Verification Script.

Executes:
1. Ingestion of the evidence_corpus into PostgreSQL + pgvector
2. Verifies row counts and 768-dim embeddings in database
3. Runs semantic search queries with EvidenceRetriever
4. Displays top retrieved results with full provenance and relevance scores
"""

import asyncio
from sqlalchemy import text
from app.core.database import get_session_factory
from app.ingestion.ingest import find_default_corpus_dir, ingest_corpus
from app.services.evidence_retriever import search

QUERIES = [
    "Flooding and submerged cars in Chennai",
    "James Webb Space Telescope exoplanet discovery",
    "Viral reports of meteorite hitting the Eiffel Tower",
]

async def main():
    print("=" * 70)
    print("EvidenceLens — Phase 2 Evidence Corpus & Ingestion Verification")
    print("=" * 70)

    # 1. Ingest
    corpus_dir = find_default_corpus_dir()
    print(f"\n[1] Ingesting corpus from: {corpus_dir}")
    stats = await ingest_corpus(corpus_dir=corpus_dir, chunk_size=450, chunk_overlap=80)
    print(f"    Loaded:  {stats.documents_loaded} documents")
    print(f"    Sources: {stats.sources_created} created, {stats.sources_updated} updated")
    print(f"    Chunks:  {stats.chunks_created} chunks stored in pgvector")

    # 2. Database verification
    print("\n[2] Verifying database records...")
    factory = get_session_factory()
    if factory is None:
        print("[ERROR] Database session factory not available.")
        return

    async with factory() as session:
        src_count = (await session.execute(text("SELECT count(*) FROM sources;"))).scalar()
        chunk_count = (await session.execute(text("SELECT count(*) FROM evidence_chunks;"))).scalar()
        print(f"    Total Sources in DB:        {src_count}")
        print(f"    Total EvidenceChunks in DB: {chunk_count}")

        # Check dimension of stored vector
        dim_res = await session.execute(
            text("SELECT vector_dims(embedding) FROM evidence_chunks LIMIT 1;")
        )
        dim_val = dim_res.scalar()
        print(f"    Stored Vector Dimension:    {dim_val} (Target: 768)")
        assert dim_val == 768, f"Dimension mismatch: expected 768, got {dim_val}"

    # 3. Semantic Search Demonstration
    print("\n[3] Running Real Semantic Search via EvidenceRetriever...")
    for q in QUERIES:
        print(f"\n" + "-" * 70)
        print(f"Query: \"{q}\"")
        print("-" * 70)
        results = await search(q, top_k=3)
        if not results:
            print("  No matching evidence found.")
            continue

        for rank, item in enumerate(results, start=1):
            print(f"  #{rank} [Score: {item.relevance_score:.4f}] {item.title}")
            print(f"     Publisher: {item.publisher or 'N/A'} | Date: {item.published_at or 'N/A'}")
            print(f"     Excerpt:   \"{item.excerpt[:130]}...\"")
            print(f"     URL:       {item.url}")

    print("\n" + "=" * 70)
    print("[SUCCESS] Phase 2 Verification Complete!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
