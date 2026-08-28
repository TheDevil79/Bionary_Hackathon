"""
Unit tests for ClaimExtractor service.

Note: Unit tests MUST NOT call the real Gemini API.
All Gemini SDK interactions are mocked.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.schemas.claim import AtomicClaim, Verdict
from app.services.claim_extractor import extract_claims, _mock_extract


@pytest.mark.asyncio
async def test_extract_claims_empty_input():
    """Empty or whitespace input must return an empty list without calling Gemini."""
    res = await extract_claims("   ")
    assert res == []


@pytest.mark.asyncio
async def test_extract_claims_missing_api_key_fallback():
    """When GEMINI_API_KEY is not configured, fall back to deterministic mock extractor."""
    with patch.object(settings, "gemini_api_key", ""):
        res = await extract_claims("Chennai received heavy rainfall yesterday and several roads were flooded.")
        assert len(res) >= 2
        assert res[0].id == "C1"
        assert res[1].id == "C2"
        assert res[0].verdict == Verdict.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_extract_claims_valid_single_atomic():
    """Test Gemini extraction for a single atomic statement."""
    mock_response_json = """{
        "claims": [
            {
                "id": "C1",
                "text": "Chennai received heavy rainfall yesterday."
            }
        ]
    }"""
    mock_resp = MagicMock()
    mock_resp.text = mock_response_json

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp

    with patch.object(settings, "gemini_api_key", "test_gemini_key_123"), \
         patch("app.services.claim_extractor._get_gemini_model", return_value=mock_model):
        
        claims = await extract_claims("Chennai received heavy rainfall yesterday.")
        assert len(claims) == 1
        assert claims[0].id == "C1"
        assert claims[0].text == "Chennai received heavy rainfall yesterday."
        assert claims[0].verdict == Verdict.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_extract_claims_compound_splitting_and_entities():
    """Test compound claim splitting and entity/date preservation."""
    mock_response_json = """{
        "claims": [
            {
                "id": "C1",
                "text": "A meteorite hit the Eiffel Tower in Paris on August 27, 2026."
            },
            {
                "id": "C2",
                "text": "The Eiffel Tower was closed by SETE management because of damage from the meteorite."
            }
        ]
    }"""
    mock_resp = MagicMock()
    mock_resp.text = mock_response_json

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp

    with patch.object(settings, "gemini_api_key", "test_gemini_key_123"), \
         patch("app.services.claim_extractor._get_gemini_model", return_value=mock_model):
        
        input_text = "A meteorite hit the Eiffel Tower in Paris on August 27, 2026 and the tower was closed by SETE management because of damage."
        claims = await extract_claims(input_text)
        
        assert len(claims) == 2
        assert claims[0].id == "C1"
        assert "Eiffel Tower" in claims[0].text
        assert "August 27, 2026" in claims[0].text
        assert claims[1].id == "C2"
        assert "SETE" in claims[1].text
        assert "closed" in claims[1].text


@pytest.mark.asyncio
async def test_extract_claims_preserves_nasa_scientific_facts():
    """Test NASA exoplanet case: verifies no hallucinated planet names."""
    mock_response_json = """{
        "claims": [
            {
                "id": "C1",
                "text": "NASA announced that water vapor was detected on a distant planet."
            }
        ]
    }"""
    mock_resp = MagicMock()
    mock_resp.text = mock_response_json

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp

    with patch.object(settings, "gemini_api_key", "test_gemini_key_123"), \
         patch("app.services.claim_extractor._get_gemini_model", return_value=mock_model):
        
        claims = await extract_claims("NASA announced that water vapor was detected on a distant planet.")
        assert len(claims) == 1
        assert "NASA" in claims[0].text
        assert "water vapor" in claims[0].text
        assert "distant planet" in claims[0].text


@pytest.mark.asyncio
async def test_extract_claims_gemini_malformed_json_fallback():
    """Malformed JSON from Gemini falls back gracefully to deterministic extractor."""
    mock_resp = MagicMock()
    mock_resp.text = "This is not valid JSON at all!"

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp

    with patch.object(settings, "gemini_api_key", "test_gemini_key_123"), \
         patch("app.services.claim_extractor._get_gemini_model", return_value=mock_model):
        
        claims = await extract_claims("Chennai received heavy rain yesterday.")
        # Must return valid AtomicClaim objects from deterministic fallback without throwing
        assert isinstance(claims, list)
        assert len(claims) >= 1
        assert claims[0].id == "C1"


@pytest.mark.asyncio
async def test_extract_claims_gemini_api_exception_fallback():
    """Gemini API network/quota exception falls back gracefully to deterministic extractor."""
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("ResourceExhausted: Quota exceeded")

    with patch.object(settings, "gemini_api_key", "test_gemini_key_123"), \
         patch("app.services.claim_extractor._get_gemini_model", return_value=mock_model):
        
        claims = await extract_claims("Heavy rain flooded the metro station.")
        assert isinstance(claims, list)
        assert len(claims) >= 1
        assert "Heavy rain" in claims[0].text
