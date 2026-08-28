"""
EvidenceLens — Media Analyzer Service.

Responsibility: given an uploaded image or video file, determine whether it
has appeared in the corpus before, detect context mismatches (e.g. an image
reused to misrepresent a different event), and compute similarity scores.

Current state: DEVELOPMENT MOCK
  Returns deterministic demo data so the pipeline can be tested
  without CLIP or a perceptual hash corpus.

TODO (Phase 2):
  - Compute perceptual hash (imagehash) for images.
  - Optionally run CLIP embedding for semantic image search.
  - Compare against stored hashes/embeddings in the corpus.
  - Detect context mismatches via metadata cross-reference.
  - Add video keyframe extraction (OpenCV).

Supported media types:
  image/jpeg, image/png, image/webp, image/gif
  video/mp4, video/quicktime
"""

from __future__ import annotations

import logging

from fastapi import UploadFile

from app.schemas.claim import MediaAnalysis, PreviousOccurrence

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
SUPPORTED_MEDIA_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_VIDEO_TYPES

# ─── Public interface ─────────────────────────────────────────────────────────

async def analyze(file: UploadFile | None) -> MediaAnalysis | None:
    """
    Analyze an uploaded media file for prior occurrences and context mismatches.

    Args:
        file: The uploaded file from the multipart request, or None if no
              media was attached.

    Returns:
        MediaAnalysis if a file was provided; None otherwise.

    Raises:
        ValueError: If the file type is unsupported.
        ValueError: If the file exceeds the size limit (checked in the route).
    """
    if file is None:
        return None

    content_type = file.content_type or ""
    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(
            f"Unsupported media type '{content_type}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_MEDIA_TYPES))}"
        )

    logger.info("Analyzing media file: %s (%s)", file.filename, content_type)

    # TODO: replace with real perceptual hash / CLIP analysis in Phase 2
    return _mock_analyze(file)


# ─── Mock (development only) ──────────────────────────────────────────────────

def _mock_analyze(file: UploadFile) -> MediaAnalysis:
    """
    ⚠️  DEVELOPMENT MOCK — not real media analysis.
    Always reports a context mismatch with a fabricated prior occurrence.
    Replace with perceptual hash + CLIP in Phase 2.
    """
    return MediaAnalysis(
        analyzed=True,
        matched=True,
        similarity=0.972,
        context_mismatch=True,
        previous_occurrence=PreviousOccurrence(
            date=None,
            source="[DEMO] Synthetic Prior Source",
            url="https://example.com/demo-prior-occurrence",
        ),
    )
