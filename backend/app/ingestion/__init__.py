"""
EvidenceLens — Evidence Corpus Ingestion Module.
"""

from app.ingestion.loader import DocumentRecord, load_corpus
from app.ingestion.chunker import ChunkRecord, chunk_document
from app.ingestion.embedder import Embedder, get_embedder

__all__ = [
    "DocumentRecord",
    "load_corpus",
    "ChunkRecord",
    "chunk_document",
    "Embedder",
    "get_embedder",
]
