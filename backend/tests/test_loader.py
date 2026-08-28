import tempfile
import json
from pathlib import Path
import pytest
from app.ingestion.loader import load_corpus, load_single_document, compute_content_hash


def test_compute_content_hash():
    text1 = "This is a sample document for hashing."
    text2 = "  This is a sample document for hashing.  \n"
    # Stripped text produces identical hash
    assert compute_content_hash(text1) == compute_content_hash(text2)
    assert len(compute_content_hash(text1)) == 64


def test_load_corpus_from_sample_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sources_dir = root / "sources"
        documents_dir = root / "documents"
        sources_dir.mkdir()
        documents_dir.mkdir()

        meta = {
            "id": "doc_test_1",
            "title": "Test Meteorological Bulletin",
            "publisher": "Test Weather Agency",
            "url": "https://example.com/test",
            "published_at": "2026-08-28T12:00:00Z",
            "source_type": "news",
            "language": "en"
        }
        with open(sources_dir / "doc_test_1.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        with open(documents_dir / "doc_test_1.txt", "w", encoding="utf-8") as f:
            f.write("Heavy rain and thunderstorms caused water stagnation across the city.")

        docs = load_corpus(root)
        assert len(docs) == 1
        assert docs[0].source_id == "doc_test_1"
        assert docs[0].title == "Test Meteorological Bulletin"
        assert "water stagnation" in docs[0].text
        assert docs[0].content_hash == compute_content_hash(docs[0].text)


def test_load_corpus_missing_txt():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "sources").mkdir()
        (root / "documents").mkdir()

        with open(root / "sources" / "doc_orphan.json", "w", encoding="utf-8") as f:
            json.dump({"id": "doc_orphan", "title": "Orphan"}, f)

        # No matching .txt file
        docs = load_corpus(root)
        assert len(docs) == 0
