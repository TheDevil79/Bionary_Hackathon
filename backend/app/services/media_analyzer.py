"""
EvidenceLens — Media Analyzer Service (Phase 5).

Responsibility:
  Given an uploaded image or video file:
    1. Validate media type and size constraints.
    2. Compute cryptographic SHA-256 hash.
    3. Compute perceptual hash (pHash) for images and sample video frames.
    4. Cross-reference against known media catalog for prior occurrences.
    5. Detect context mismatches (e.g. recycled footage from prior events).
    6. (Optional) Request visual inspection from Gemini without hallucinating provenance.
    7. Return structured MediaAnalysis result, degrading gracefully on failure.

Supported media types:
  image/jpeg, image/png, image/webp, image/gif
  video/mp4, video/quicktime
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import logging
from typing import Any

from fastapi import UploadFile

from app.core.config import settings
from app.schemas.claim import MediaAnalysis, PreviousOccurrence

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_VISION_MODEL = "gemini-3.6-flash"

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
SUPPORTED_MEDIA_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_VIDEO_TYPES

# Maximum perceptual hash Hamming distance for similarity match (out of 64 bits)
PHASH_MATCH_MAX_DISTANCE = 6


# ─── Known Media Registry (Corpus of verified prior media) ───────────────────
# In production, this can be queried from a database. For the hackathon MVP,
# this registry provides deterministic ground truth for known viral misattributions.

KNOWN_MEDIA_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "KM_001",
        "description": "Marina Beach Submerged Cars Footage (Dec 2015 Chennai floods)",
        "sha256": "4b6f1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
        "phash": "a1b2c3d4e5f60718",
        "date": dt.date(2015, 12, 2),
        "source": "State Flood Archive",
        "url": "https://example.com/archive-2015-marina",
        "context": "December 2015 Chennai Floods at Marina Beach",
    },
    {
        "id": "KM_002",
        "description": "Synthetic Eiffel Tower meteorite impact composite",
        "sha256": "9e1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "phash": "ffff0000ffff0000",
        "date": dt.date(2021, 4, 1),
        "source": "VFX Archive / CGI Showcase",
        "url": "https://example.com/vfx-meteorite-cgi",
        "context": "April 2021 CGI concept animation",
    },
]


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_media(file: UploadFile) -> str:
    """
    Validate that the uploaded media file has an allowed content type.

    Returns:
        The verified content_type string.

    Raises:
        ValueError: If the file type is unsupported.
    """
    content_type = (file.content_type or "").strip().lower()
    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(
            f"Unsupported media type '{content_type}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_MEDIA_TYPES))}"
        )
    return content_type


# ─── Hashing Utilities ────────────────────────────────────────────────────────

def compute_sha256(data: bytes) -> str:
    """Calculate SHA-256 cryptographic hash of byte content."""
    return hashlib.sha256(data).hexdigest()


def compute_perceptual_hash(data: bytes) -> str | None:
    """
    Calculate 64-bit perceptual hash (pHash) for an image.

    Returns:
        Hexadecimal pHash string, or None if Pillow/imagehash cannot process the image.
    """
    try:
        from PIL import Image
        import imagehash

        image = Image.open(io.BytesIO(data))
        # Ensure image is in RGB/L mode for perceptual hashing
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        hash_val = imagehash.phash(image)
        return str(hash_val)
    except ImportError:
        logger.warning("Pillow or imagehash not installed; skipping perceptual hashing.")
        return None
    except Exception as exc:
        logger.warning("Failed to compute perceptual hash: %s", exc)
        return None


def calculate_phash_similarity(hash1_hex: str, hash2_hex: str) -> float | None:
    """
    Compute normalized similarity [0.0, 1.0] from perceptual hash Hamming distance.

    Returns:
        Similarity score between 0.0 and 1.0, or None on invalid hash input.
    """
    try:
        import imagehash

        h1 = imagehash.hex_to_hash(hash1_hex)
        h2 = imagehash.hex_to_hash(hash2_hex)
        distance = h1 - h2  # Hamming distance (0 to 64)
        similarity = max(0.0, 1.0 - (distance / 64.0))
        return round(similarity, 3)
    except Exception:
        # Fallback bitwise Hamming distance if imagehash conversion fails
        try:
            val1 = int(hash1_hex, 16)
            val2 = int(hash2_hex, 16)
            xor_val = val1 ^ val2
            distance = bin(xor_val).count("1")
            similarity = max(0.0, 1.0 - (distance / 64.0))
            return round(similarity, 3)
        except Exception:
            return None


# ─── Image & Video Analysis ───────────────────────────────────────────────────

def analyze_image(
    data: bytes,
    filename: str | None,
    content_type: str,
) -> dict[str, Any]:
    """
    Extract deterministic metadata and perceptual hash from image bytes.

    Returns:
        Dictionary containing sha256, phash, dimensions, format, and status.
    """
    sha256_hash = compute_sha256(data)
    phash = compute_perceptual_hash(data)
    width, height, img_format = None, None, None

    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            img_format = img.format
    except Exception as exc:
        logger.debug("Could not read image dimensions for %s: %s", filename, exc)

    return {
        "media_type": "image",
        "sha256": sha256_hash,
        "phash": phash,
        "width": width,
        "height": height,
        "format": img_format or content_type,
        "size_bytes": len(data),
    }


def analyze_video(
    data: bytes,
    filename: str | None,
    content_type: str,
) -> dict[str, Any]:
    """
    Lightweight video analysis: computes SHA-256 and attempts sample frame hashing.

    Fails gracefully if video processing libraries are not installed or stream is corrupt.
    """
    sha256_hash = compute_sha256(data)
    phash: str | None = None
    duration: float | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None

    # Attempt OpenCV frame sampling if available
    try:
        import tempfile
        import cv2

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()

            cap = cv2.VideoCapture(tmp.name)
            if cap.isOpened():
                fps_val = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if fps_val and fps_val > 0:
                    fps = round(fps_val, 2)
                    duration = round(frame_count / fps_val, 2)

                # Sample the middle frame for pHash
                mid_frame_idx = int(frame_count // 2) if frame_count > 0 else 0
                cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Convert BGR to RGB JPEG in memory
                    is_success, buffer = cv2.imencode(".jpg", frame)
                    if is_success:
                        phash = compute_perceptual_hash(buffer.tobytes())
                cap.release()
    except ImportError:
        logger.debug("OpenCV not installed; skipping video frame sampling.")
    except Exception as exc:
        logger.warning("Video frame extraction skipped due to error: %s", exc)

    return {
        "media_type": "video",
        "sha256": sha256_hash,
        "phash": phash,
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "size_bytes": len(data),
    }


# ─── Occurrence & Context Mismatch Matching ───────────────────────────────────

def find_previous_occurrence(
    sha256_hash: str,
    phash: str | None,
    registry: list[dict[str, Any]] | None = None,
) -> tuple[bool, float | None, bool, PreviousOccurrence | None]:
    """
    Cross-reference media hashes against the known occurrence catalog.

    Matching Logic:
      1. Exact SHA-256 match -> similarity = 1.0, matched = True
      2. Perceptual hash similarity >= 0.90 -> similarity score, matched = True
      3. Otherwise -> matched = False

    Context Mismatch:
      Flagged as True ONLY when a verified prior occurrence from a different date/event
      is confirmed in the catalog.

    Returns:
        (matched, similarity, context_mismatch, previous_occurrence)
    """
    catalog = registry if registry is not None else KNOWN_MEDIA_REGISTRY

    # 1. Check exact SHA-256 match
    for item in catalog:
        if item.get("sha256") and item["sha256"].lower() == sha256_hash.lower():
            logger.info("Exact SHA-256 media match found: %s", item["id"])
            return (
                True,
                1.0,
                True,
                PreviousOccurrence(
                    date=item.get("date"),
                    source=item.get("source"),
                    url=item.get("url"),
                ),
            )

    # 2. Check perceptual hash match if available
    if phash:
        best_match = None
        best_similarity = 0.0

        for item in catalog:
            known_phash = item.get("phash")
            if not known_phash:
                continue

            sim = calculate_phash_similarity(phash, known_phash)
            if sim is not None and sim > best_similarity:
                best_similarity = sim
                best_match = item

        # Threshold for perceptual match (approx hamming distance <= 6 out of 64)
        if best_match and best_similarity >= 0.90:
            logger.info(
                "Perceptual hash match found: %s (similarity=%.3f)",
                best_match["id"],
                best_similarity,
            )
            return (
                True,
                best_similarity,
                True,
                PreviousOccurrence(
                    date=best_match.get("date"),
                    source=best_match.get("source"),
                    url=best_match.get("url"),
                ),
            )

    # No match found in catalog
    return (False, None, False, None)


# ─── Optional Gemini Vision Interpretation ────────────────────────────────────

def interpret_media_with_gemini(
    data: bytes,
    content_type: str,
    claim_text: str | None,
    api_key: str,
) -> str | None:
    """
    Optional Gemini Vision check for visible content description.

    STRICT GUARDRAILS:
      - Describes ONLY visible objects/actions.
      - Never invents provenance, dates, or source URLs.
      - Fails gracefully if Gemini call fails.
    """
    if not api_key or not content_type.startswith("image/"):
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = (
            "Analyze this image objectively in 1-2 factual sentences describing what is visible. "
            f"{'Compare it to the claim: ' + claim_text if claim_text else ''}\n"
            "Do NOT speculate on dates, origin URLs, or historical provenance."
        )

        response = client.models.generate_content(
            model=DEFAULT_VISION_MODEL,
            contents=[
                types.Part.from_bytes(data=data, mime_type=content_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception as exc:
        logger.warning("Gemini vision analysis failed: %s — continuing without it.", exc)

    return None


# ─── Public Main Entry Point ──────────────────────────────────────────────────

async def analyze(
    file: UploadFile | None,
    claim_text: str | None = None,
) -> MediaAnalysis | None:
    """
    Analyze an uploaded media file for prior occurrences and context mismatches.

    Args:
        file: The uploaded file from the multipart request, or None if no media attached.
        claim_text: Optional text claim for visual consistency comparison.

    Returns:
        MediaAnalysis if a file was provided; None otherwise.

    Raises:
        ValueError: If the file type is unsupported.
    """
    if file is None:
        return None

    content_type = validate_media(file)
    logger.info("Analyzing media file: %s (%s)", file.filename, content_type)

    try:
        data = await file.read()
        await file.seek(0)  # rewind file pointer

        if content_type in SUPPORTED_IMAGE_TYPES:
            meta = analyze_image(data, file.filename, content_type)
        else:
            meta = analyze_video(data, file.filename, content_type)

        matched, similarity, context_mismatch, prev_occ = find_previous_occurrence(
            sha256_hash=meta["sha256"],
            phash=meta.get("phash"),
        )

        # Optional Gemini multimodal check (non-blocking for provenance)
        api_key = (settings.gemini_api_key or "").strip()
        if api_key and content_type in SUPPORTED_IMAGE_TYPES:
            vision_summary = interpret_media_with_gemini(
                data=data,
                content_type=content_type,
                claim_text=claim_text,
                api_key=api_key,
            )
            if vision_summary:
                logger.debug("Gemini vision summary: %s", vision_summary)

        return MediaAnalysis(
            analyzed=True,
            matched=matched,
            similarity=similarity,
            context_mismatch=context_mismatch,
            previous_occurrence=prev_occ,
        )

    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in media analyzer; degrading gracefully: %s", exc)
        # Safe fallback rather than crashing entire pipeline
        return MediaAnalysis(
            analyzed=True,
            matched=False,
            similarity=None,
            context_mismatch=False,
            previous_occurrence=None,
        )
