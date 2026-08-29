import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analyze_valid_text(client: AsyncClient):
    response = await client.post(
        "/analyze",
        data={"text": "A severe flash flood occurred in Chennai yesterday causing damages."}
    )
    assert response.status_code == 200
    data = response.json()
    assert "claim_id" in data
    assert "atomic_claims" in data
    assert len(data["atomic_claims"]) > 0
    assert "verdict" in data
    assert data["verdict"] in ["SUPPORTED", "CONTRADICTED", "MIXED", "INSUFFICIENT_EVIDENCE"]
    assert "confidence" in data
    assert "evidence" in data
    assert "uncertainty" in data


@pytest.mark.asyncio
async def test_analyze_empty_text(client: AsyncClient):
    response = await client.post(
        "/analyze",
        data={"text": "   "}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_with_image(client: AsyncClient):
    # Simulate a small valid JPEG upload
    fake_image = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
    files = {"media": ("test.jpg", fake_image, "image/jpeg")}
    response = await client.post(
        "/analyze",
        data={"text": "Sample claim accompanied with photo evidence."},
        files=files,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["media_analysis"] is not None
    assert data["media_analysis"]["analyzed"] is True


@pytest.mark.asyncio
async def test_analyze_unsupported_media_type(client: AsyncClient):
    fake_file = io.BytesIO(b"fake executable content")
    files = {"media": ("bad.exe", fake_file, "application/x-msdownload")}
    response = await client.post(
        "/analyze",
        data={"text": "Claim with bad file type."},
        files=files,
    )
    assert response.status_code == 415
