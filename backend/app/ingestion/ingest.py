"""
EvidenceLens — Corpus Ingestion Orchestrator.

Orchestrates:
  Source Documents -> Cleaning & Hashing -> Chunking -> Embedding -> PostgreSQL + pgvector

Idempotent: safe to run multiple times without duplicating sources or chunks.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import get_embedder
from app.ingestion.loader import DocumentRecord, load_corpus
from app.models.evidence import EvidenceChunk, Source

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion")


class IngestionStats(NamedTuple):
    documents_loaded: int
    sources_created: int
    sources_updated: int
    chunks_created: int


async def ingest_corpus(
    corpus_dir: Path | str,
    chunk_size: int = 450,
    chunk_overlap: int = 80,
    session: AsyncSession | None = None,
) -> IngestionStats:
    """
    Ingest all documents from a corpus directory into PostgreSQL + pgvector.

    Args:
        corpus_dir: Path to evidence_corpus directory.
        chunk_size: Target character length per chunk.
        chunk_overlap: Character overlap between consecutive chunks.
        session: Optional external AsyncSession (used in tests).

    Returns:
        IngestionStats tuple with counts.
    """
    corpus_path = Path(corpus_dir).resolve()
    logger.info("Starting ingestion from: %s", corpus_path)

    # 1. Load documents
    documents = load_corpus(corpus_path)
    if not documents:
        logger.warning("No documents found to ingest.")
        return IngestionStats(0, 0, 0, 0)

    # 2. Get embedder
    embedder = get_embedder()

    # Session management
    own_session = False
    if session is None:
        factory = get_session_factory()
        if factory is None:
            raise RuntimeError(
                "Database session factory unavailable. Check DATABASE_URL in .env."
            )
        session = factory()
        own_session = True

    sources_created = 0
    sources_updated = 0
    chunks_created = 0

    try:
        for doc in documents:
            logger.info("Processing source '%s': %s", doc.source_id, doc.title)

            # Check if source with same content_hash or title already exists
            stmt = select(Source).where(Source.content_hash == doc.content_hash)
            res = await session.execute(stmt)
            source = res.scalars().first()

            if source is None:
                source = Source(
                    title=doc.title,
                    publisher=doc.publisher,
                    url=doc.url,
                    published_at=doc.published_at,
                    source_type=doc.source_type,
                    license=doc.license,
                    language=doc.language,
                    content_hash=doc.content_hash,
                )
                session.add(source)
                await session.flush()  # populate source.id
                sources_created += 1
                logger.info("Created new source ID: %s", source.id)
            else:
                # Update metadata if changed
                source.title = doc.title
                source.publisher = doc.publisher
                source.url = doc.url
                source.published_at = doc.published_at
                source.source_type = doc.source_type
                source.license = doc.license
                source.language = doc.language
                sources_updated += 1
                logger.info("Updated existing source ID: %s", source.id)

                # Delete existing chunks for this source to re-index fresh
                await session.execute(
                    delete(EvidenceChunk).where(EvidenceChunk.source_id == source.id)
                )
                await session.flush()

            # Chunk document
            chunk_records = chunk_document(
                doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
            if not chunk_records:
                continue

            chunk_texts = [c.text for c in chunk_records]
            logger.info("Generating embeddings for %d chunks...", len(chunk_texts))

            embeddings = embedder.embed_texts(chunk_texts)

            # Create EvidenceChunk records
            for c_rec, emb in zip(chunk_records, embeddings):
                chunk_obj = EvidenceChunk(
                    source_id=source.id,
                    text=c_rec.text,
                    embedding=emb,
                )
                session.add(chunk_obj)
                chunks_created += 1

            await session.flush()

        await session.commit()
        logger.info(
            "Ingestion finished successfully: %d docs, %d created, %d updated, %d chunks stored.",
            len(documents),
            sources_created,
            sources_updated,
            chunks_created,
        )
        return IngestionStats(
            documents_loaded=len(documents),
            sources_created=sources_created,
            sources_updated=sources_updated,
            chunks_created=chunks_created,
        )

    except Exception:
        await session.rollback()
        raise
    finally:
        if own_session:
            await session.close()


def find_default_corpus_dir() -> Path:
    """Locate the evidence_corpus directory relative to repo structure."""
    cwd = Path.cwd()
    # Try ../evidence_corpus from backend/
    cand1 = cwd / ".." / "evidence_corpus"
    if cand1.resolve().exists():
        return cand1.resolve()
    # Try evidence_corpus from workspace root
    cand2 = cwd / "evidence_corpus"
    if cand2.resolve().exists():
        return cand2.resolve()
    # Fallback to absolute relative to this file
    cand3 = Path(__file__).resolve().parents[3] / "evidence_corpus"
    return cand3


async def main_cli() -> None:
    parser = argparse.ArgumentParser(
        description="EvidenceLens — Ingest evidence corpus into PostgreSQL + pgvector."
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=None,
        help="Path to evidence_corpus directory (default: auto-detected)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=450,
        help="Target chunk character size (default: 450)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=80,
        help="Chunk overlap in characters (default: 80)",
    )

    args = parser.parse_args()
    corpus_dir = Path(args.corpus) if args.corpus else find_default_corpus_dir()

    if not corpus_dir.exists():
        print(f"[ERROR] Corpus directory not found at: {corpus_dir}")
        sys.exit(1)

    print("=" * 60)
    print("EvidenceLens Evidence Ingestion Pipeline")
    print("=" * 60)
    print(f"Corpus path:   {corpus_dir}")
    print(f"Chunk size:    {args.chunk_size}")
    print(f"Chunk overlap: {args.chunk_overlap}")
    print(f"Model:         all-mpnet-base-v2 (768-dim)")
    print("=" * 60)

    try:
        stats = await ingest_corpus(
            corpus_dir=corpus_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        print("\n" + "=" * 60)
        print("[SUCCESS] Ingestion Complete!")
        print(f"  Documents Loaded:  {stats.documents_loaded}")
        print(f"  Sources Created:   {stats.sources_created}")
        print(f"  Sources Updated:   {stats.sources_updated}")
        print(f"  Chunks Ingested:   {stats.chunks_created}")
        print("=" * 60)
    except Exception as exc:
        print(f"\n[FAIL] Ingestion failed: {exc}")
        logger.exception("Ingestion failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_cli())
