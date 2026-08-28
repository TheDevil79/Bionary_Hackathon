"""
EvidenceLens — Corpus Loader.

Reads source metadata JSON files and raw document TXT files, validates
their fields, and computes a SHA-256 content hash for deduplication.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """In-memory representation of a validated source document."""
    source_id: str
    title: str
    publisher: str | None
    url: str | None
    published_at: datetime | None
    source_type: str | None
    license: str | None
    language: str | None
    content_hash: str
    text: str


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hex digest of the raw document text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO formatted timestamp string into datetime."""
    if not dt_str:
        return None
    try:
        # Handle trailing Z
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception as exc:
        logger.warning("Could not parse datetime string '%s': %s", dt_str, exc)
        return None


def load_single_document(meta_path: Path, doc_path: Path) -> DocumentRecord:
    """
    Load a single document from its metadata JSON and text file.

    Raises:
        FileNotFoundError: If either file does not exist.
        ValueError: If JSON metadata is invalid or text is empty.
    """
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {meta_path}")
    if not doc_path.exists():
        raise FileNotFoundError(f"Document text file not found: {doc_path}")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta: dict[str, Any] = json.load(f)

    with open(doc_path, "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    if not raw_text:
        raise ValueError(f"Document text is empty: {doc_path}")

    source_id = meta.get("id") or meta_path.stem
    title = meta.get("title", "Untitled Document").strip()
    publisher = meta.get("publisher")
    url = meta.get("url")
    published_at = parse_datetime(meta.get("published_at"))
    source_type = meta.get("source_type", "news")
    license_str = meta.get("license")
    language = meta.get("language", "en")

    content_hash = compute_content_hash(raw_text)

    return DocumentRecord(
        source_id=source_id,
        title=title,
        publisher=publisher,
        url=url,
        published_at=published_at,
        source_type=source_type,
        license=license_str,
        language=language,
        content_hash=content_hash,
        text=raw_text,
    )


def load_corpus(corpus_dir: Path | str) -> list[DocumentRecord]:
    """
    Load all source documents from an evidence corpus directory.

    Expected directory structure:
        corpus_dir/
            sources/   (*.json)
            documents/ (*.txt)

    Returns:
        List of DocumentRecord objects ordered by source ID.
    """
    corpus_path = Path(corpus_dir).resolve()
    sources_dir = corpus_path / "sources"
    documents_dir = corpus_path / "documents"

    if not sources_dir.exists():
        raise FileNotFoundError(f"Corpus sources directory not found: {sources_dir}")
    if not documents_dir.exists():
        raise FileNotFoundError(f"Corpus documents directory not found: {documents_dir}")

    meta_files = sorted(sources_dir.glob("*.json"))
    if not meta_files:
        logger.warning("No metadata JSON files found in %s", sources_dir)
        return []

    documents: list[DocumentRecord] = []
    for meta_file in meta_files:
        stem = meta_file.stem
        doc_file = documents_dir / f"{stem}.txt"
        if not doc_file.exists():
            logger.warning("Missing matching text document for %s, skipping.", meta_file.name)
            continue

        try:
            doc = load_single_document(meta_file, doc_file)
            documents.append(doc)
            logger.info("Loaded document '%s' (title: %s, %d chars)", doc.source_id, doc.title, len(doc.text))
        except Exception as exc:
            logger.error("Failed to load document %s: %s", meta_file.name, exc)

    return documents
