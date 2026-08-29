"""
Unit tests for MediaAnalyzer service — Phase 5.

All tests operate locally using synthetic test images and mocked Gemini calls.
No external network requests or live Gemini calls are made during test runs.
"""

from __future__ import annotations

import datetime as dt
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import UploadFile
from httpx import AsyncClient
from PIL import Image

from app.core.config import settings
from app.schemas.claim import MediaAnalysis, PreviousOccurrence
from app.services import media_analyzer


# ─── Helpers to generate synthetic in-memory images ───────────────────────────

def create_synthetic_image(
    format: str = "JPEG",
    size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    """Create a minimal synthetic in-memory image for testing."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def create_mock_upload_file(
    content: bytes,
    filename: str = "test.jpg",
    content_type: str = "image/jpeg",
) -> UploadFile:
    """Create a FastAPI UploadFile wrapper around raw in-memory bytes."""
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


# ─── Unit Tests: Validation & Hashing ─────────────────────────────────────────

class TestMediaValidationAndHashing:

    def test_validate_media_valid_types(self):
        for mime in ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"]:
            upload = create_mock_upload_file(b"fake", "file", mime)
            assert media_analyzer.validate_media(upload) == mime

    def test_validate_media_unsupported_type_raises(self):
        upload = create_mock_upload_file(b"fake", "file.pdf", "application/pdf")
        with pytest.raises(ValueError, match="Unsupported media type"):
            media_analyzer.validate_media(upload)

    def test_compute_sha256(self):
        data = b"EvidenceLens test data"
        sha = media_analyzer.compute_sha256(data)
        assert len(sha) == 64
        # Deterministic
        assert sha == media_analyzer.compute_sha256(data)

    def test_compute_perceptual_hash_valid_image(self):
        img_bytes = create_synthetic_image("PNG", (32, 32), (0, 128, 255))
        phash = media_analyzer.compute_perceptual_hash(img_bytes)
        assert phash is not None
        assert len(phash) >= 8

    def test_compute_perceptual_hash_invalid_bytes_returns_none(self):
        phash = media_analyzer.compute_perceptual_hash(b"not an image at all")
        assert phash is None

    def test_calculate_phash_similarity_identical(self):
        h = "a1b2c3d4e5f60718"
        sim = media_analyzer.calculate_phash_similarity(h, h)
        assert sim == 1.0

    def test_calculate_phash_similarity_different(self):
        h1 = "0000000000000000"
        h2 = "ffffffffffffffff"
        sim = media_analyzer.calculate_phash_similarity(h1, h2)
        assert sim == 0.0


# ─── Unit Tests: Image & Video Analysis ───────────────────────────────────────

class TestMediaAnalysisPipelines:

    def test_analyze_image_extracts_metadata(self):
        img_bytes = create_synthetic_image("JPEG", (120, 80), (50, 100, 150))
        meta = media_analyzer.analyze_image(img_bytes, "sample.jpg", "image/jpeg")

        assert meta["media_type"] == "image"
        assert meta["width"] == 120
        assert meta["height"] == 80
        assert meta["sha256"] is not None
        assert meta["phash"] is not None
        assert meta["size_bytes"] == len(img_bytes)

    def test_analyze_video_graceful_fallback(self):
        # Provide dummy video bytes
        dummy_video = b"\x00\x00\x00 ftypmp42\x00\x00\x00\x00mp42isom"
        meta = media_analyzer.analyze_video(dummy_video, "sample.mp4", "video/mp4")

        assert meta["media_type"] == "video"
        assert meta["sha256"] is not None
        assert meta["size_bytes"] == len(dummy_video)


# ─── Unit Tests: Previous Occurrence & Context Mismatch ───────────────────────

class TestOccurrenceMatching:

    def test_find_previous_occurrence_exact_sha256_match(self):
        target_sha = "4b6f1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab"
        matched, sim, mismatch, prev = media_analyzer.find_previous_occurrence(
            sha256_hash=target_sha,
            phash=None,
        )
        assert matched is True
        assert sim == 1.0
        assert mismatch is True
        assert prev is not None
        assert prev.source == "State Flood Archive"
        assert prev.date == dt.date(2015, 12, 2)

    def test_find_previous_occurrence_phash_similarity_match(self):
        custom_registry = [
            {
                "id": "TEST_001",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "phash": "a1b2c3d4e5f60718",
                "date": dt.date(2020, 1, 1),
                "source": "Prior Test Archive",
                "url": "https://example.com/test",
            }
        ]
        # Query with exact or 1-bit differing phash
        matched, sim, mismatch, prev = media_analyzer.find_previous_occurrence(
            sha256_hash="unmatched_sha",
            phash="a1b2c3d4e5f60718",
            registry=custom_registry,
        )
        assert matched is True
        assert sim is not None and sim >= 0.90
        assert mismatch is True
        assert prev is not None
        assert prev.source == "Prior Test Archive"

    def test_find_previous_occurrence_no_match(self):
        matched, sim, mismatch, prev = media_analyzer.find_previous_occurrence(
            sha256_hash="unknown_hash_123456",
            phash="1111222233334444",
        )
        assert matched is False
        assert sim is None
        assert mismatch is False
        assert prev is None


# ─── Unit Tests: Gemini Multimodal Guardrails ─────────────────────────────────

class TestGeminiMultimodal:

    def test_interpret_media_no_api_key_returns_none(self):
        result = media_analyzer.interpret_media_with_gemini(
            data=b"fake",
            content_type="image/jpeg",
            claim_text="Some claim",
            api_key="",
        )
        assert result is None

    def test_interpret_media_gemini_success_mocked(self):
        mock_response = MagicMock()
        mock_response.text = "The image displays waterlogged vehicles on a flooded coastal road."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            summary = media_analyzer.interpret_media_with_gemini(
                data=b"synthetic_img_bytes",
                content_type="image/jpeg",
                claim_text="Submerged cars",
                api_key="valid-key",
            )
            assert summary == "The image displays waterlogged vehicles on a flooded coastal road."

    def test_interpret_media_gemini_exception_graceful_fallback(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API rate limit")

        with patch("google.genai.Client", return_value=mock_client):
            summary = media_analyzer.interpret_media_with_gemini(
                data=b"synthetic_img_bytes",
                content_type="image/jpeg",
                claim_text="Test",
                api_key="valid-key",
            )
            assert summary is None


# ─── Integration: analyze() public interface ──────────────────────────────────

class TestMediaAnalyzerPublicInterface:

    @pytest.mark.asyncio
    async def test_analyze_none_returns_none(self):
        res = await media_analyzer.analyze(None)
        assert res is None

    @pytest.mark.asyncio
    async def test_analyze_valid_unmatched_image(self):
        img_bytes = create_synthetic_image("PNG", (64, 64), (10, 20, 30))
        upload = create_mock_upload_file(img_bytes, "unmatched.png", "image/png")

        res = await media_analyzer.analyze(upload, claim_text="Unrelated claim")
        assert res is not None
        assert res.analyzed is True
        assert res.matched is False
        assert res.similarity is None
        assert res.context_mismatch is False
        assert res.previous_occurrence is None

    @pytest.mark.asyncio
    async def test_analyze_matched_image_via_sha(self):
        matched_sha_item = media_analyzer.KNOWN_MEDIA_REGISTRY[0]
        with patch("app.services.media_analyzer.compute_sha256", return_value=matched_sha_item["sha256"]):
            img_bytes = create_synthetic_image("JPEG", (64, 64))
            upload = create_mock_upload_file(img_bytes, "flood.jpg", "image/jpeg")

            res = await media_analyzer.analyze(upload)
            assert res is not None
            assert res.analyzed is True
            assert res.matched is True
            assert res.context_mismatch is True
            assert res.previous_occurrence is not None
            assert res.previous_occurrence.source == matched_sha_item["source"]

    @pytest.mark.asyncio
    async def test_analyze_corrupted_file_degrades_gracefully(self):
        corrupted_bytes = b"bad corrupted data not valid jpeg header"
        upload = create_mock_upload_file(corrupted_bytes, "corrupt.jpg", "image/jpeg")

        res = await media_analyzer.analyze(upload)
        assert res is not None
        assert res.analyzed is True
        assert res.matched is False


# ─── End-to-End API Route Tests with Media ────────────────────────────────────

@pytest.mark.asyncio
async def test_api_analyze_with_image_upload(client: AsyncClient):
    img_bytes = create_synthetic_image("JPEG", (64, 64), (200, 50, 50))
    files = {"media": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    response = await client.post(
        "/analyze",
        data={"text": "Heavy rainfall in coastal areas yesterday."},
        files=files,
    )
    assert response.status_code == 200
    data = response.json()
    assert "media_analysis" in data
    assert data["media_analysis"] is not None
    assert data["media_analysis"]["analyzed"] is True
