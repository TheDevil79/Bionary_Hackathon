"""
EvidenceLens — Document Chunker.

Implements a configurable, sentence-aware sliding window chunker.
Preserves context across chunk boundaries with configurable overlap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ingestion.loader import DocumentRecord

# Default chunking hyperparameters
DEFAULT_CHUNK_SIZE = 450      # Target character length per chunk
DEFAULT_CHUNK_OVERLAP = 80    # Overlapping character length between consecutive chunks


@dataclass
class ChunkRecord:
    """An individual text chunk linked to its parent source document."""
    source_id: str
    chunk_index: int
    text: str


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using regex boundary detection."""
    # Split on periods/newlines followed by space or uppercase
    sentences = re.split(r"(?<=[.!?])\s+|\n\n+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    source_id: str = "doc",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkRecord]:
    """
    Split text into overlapping, sentence-aware chunks.

    Args:
        text: Raw document text to chunk.
        source_id: Identifier of the parent source.
        chunk_size: Maximum target character count per chunk.
        chunk_overlap: Character overlap window between consecutive chunks.

    Returns:
        List of ChunkRecord instances in sequential order.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    # If the total text is smaller than chunk_size, return it as a single chunk
    if len(cleaned_text) <= chunk_size:
        return [ChunkRecord(source_id=source_id, chunk_index=0, text=cleaned_text)]

    sentences = split_into_sentences(cleaned_text)
    if not sentences:
        return [ChunkRecord(source_id=source_id, chunk_index=0, text=cleaned_text)]

    chunks: list[ChunkRecord] = []
    current_sentences: list[str] = []
    current_len = 0
    chunk_idx = 0

    for sentence in sentences:
        sentence_len = len(sentence) + 1  # +1 for space

        # If adding this sentence exceeds chunk_size and we already have content
        if current_len + sentence_len > chunk_size and current_sentences:
            chunk_str = " ".join(current_sentences).strip()
            chunks.append(
                ChunkRecord(
                    source_id=source_id,
                    chunk_index=chunk_idx,
                    text=chunk_str,
                )
            )
            chunk_idx += 1

            # Build overlap from the end of current_sentences
            overlap_sentences: list[str] = []
            overlap_len = 0
            for prev_sent in reversed(current_sentences):
                if overlap_len + len(prev_sent) <= chunk_overlap:
                    overlap_sentences.insert(0, prev_sent)
                    overlap_len += len(prev_sent) + 1
                else:
                    break

            current_sentences = overlap_sentences
            current_len = sum(len(s) + 1 for s in current_sentences)

        current_sentences.append(sentence)
        current_len += sentence_len

    # Flush any remaining sentences
    if current_sentences:
        chunk_str = " ".join(current_sentences).strip()
        if not chunks or chunk_str != chunks[-1].text:
            chunks.append(
                ChunkRecord(
                    source_id=source_id,
                    chunk_index=chunk_idx,
                    text=chunk_str,
                )
            )

    return chunks


def chunk_document(
    doc: DocumentRecord,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkRecord]:
    """Convenience helper to chunk a DocumentRecord."""
    return chunk_text(
        text=doc.text,
        source_id=doc.source_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
