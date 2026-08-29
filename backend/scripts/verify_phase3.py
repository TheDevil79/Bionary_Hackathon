"""
Phase 3 Verification Script — Atomic Claim Extraction.

Demonstrates:
1. Live Gemini extraction (if GEMINI_API_KEY is configured in backend/.env)
2. Deterministic rule-based fallback (if GEMINI_API_KEY is not set)
"""

import asyncio
from app.core.config import settings
from app.services.claim_extractor import extract_claims

TEST_INPUTS = [
    (
        "Compound Claim (Eiffel Tower)",
        "A meteorite hit the Eiffel Tower yesterday and the tower was closed because of the damage.",
    ),
    (
        "Compound Claim (Chennai Floods)",
        "Chennai received heavy rainfall yesterday and several roads were flooded.",
    ),
    (
        "Entity & Fact Preservation (NASA Exoplanet)",
        "NASA announced that water vapor was detected on a distant planet.",
    ),
]


async def main():
    print("=" * 70)
    print("EvidenceLens — Phase 3 Claim Decomposition Verification")
    print("=" * 70)

    has_key = bool(settings.gemini_api_key.strip())
    if has_key:
        print(f"Mode: LIVE GEMINI (Model: gemini-1.5-flash)")
    else:
        print("Mode: DETERMINISTIC MOCK FALLBACK (GEMINI_API_KEY not configured)")
    print("=" * 70)

    for label, text in TEST_INPUTS:
        print(f"\n[Case: {label}]")
        print(f"Input: \"{text}\"")
        claims = await extract_claims(text)
        print(f"Extracted {len(claims)} atomic claims:")
        for c in claims:
            print(f"  [{c.id}] \"{c.text}\" (Verdict: {c.verdict.value})")

    print("\n" + "=" * 70)
    print("[SUCCESS] Phase 3 Extraction Verification Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
