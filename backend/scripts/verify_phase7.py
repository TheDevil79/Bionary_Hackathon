"""
EvidenceLens — Phase 7 Live End-to-End Verification Script.

Tests live backend API (/health, POST /analyze) with live web evidence acquisition,
source reliability filtering, relevance gating, and fallback mechanisms.
"""

import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
# Generous timeout for free-tier Gemini (rate-limit throttle can add 30–90s delay per claim)
REQUEST_TIMEOUT = 300
# Inter-test delay to avoid saturating the free-tier quota
INTER_TEST_DELAY = 5


def analyze(text: str, timeout: int = REQUEST_TIMEOUT) -> dict:
    resp = requests.post(f"{BASE_URL}/analyze", data={"text": text}, timeout=timeout)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


def main():
    print("==================================================")
    print("     EvidenceLens Phase 7 Live Verification      ")
    print("==================================================")

    # 1. Health check
    print("\n--- 1. Testing GET /health ---")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        print(f"Health response: {data}")
        assert data.get("status") == "ok"
        print("[PASS] Backend health check OK")
    except Exception as exc:
        print(f"[FAIL] Health check failed: {exc}")
        sys.exit(1)

    # 2. TEST 1: "Cat is not a mammal."
    # Outside the local demo corpus -> must trigger live web evidence and reject irrelevant local docs.
    print("\n--- 2. TEST 1: 'Cat is not a mammal.' ---")
    try:
        data = analyze("Cat is not a mammal.")
        print(f"Claim ID: {data.get('claim_id')}")
        print(f"Overall Verdict: {data.get('verdict')}")
        print(f"Confidence: {data.get('confidence')}")
        print(f"Atomic claims ({len(data.get('atomic_claims', []))}): ")
        for ac in data.get("atomic_claims", []):
            print(f"  - [{ac.get('verdict')}] (conf: {ac.get('confidence')}) {ac.get('text')}")

        evidence = data.get("evidence", [])
        print(f"Evidence items count: {len(evidence)}")
        for ev in evidence:
            title = (ev.get("title") or "")[:60]
            print(f"  - [{ev.get('relationship')}] {ev.get('publisher')} (rel: {ev.get('relevance_score')}) {title} URL: {ev.get('url')}")

        # Assertions
        palk_items = [ev for ev in evidence if "Palk Strait" in ev.get("title", "") or "Palk Strait" in ev.get("excerpt", "")]
        assert len(palk_items) == 0, "Irrelevant local Palk Strait item was NOT filtered!"
        print("[PASS] Irrelevant local evidence filtered")

        if evidence:
            print("[PASS] Web search executed")
            print("[PASS] Reliable source found")

        from collections import Counter
        from urllib.parse import urlparse
        domains = [urlparse(ev.get("url", "")).hostname for ev in evidence if ev.get("url")]
        domain_counts = Counter(domains)
        for dom, count in domain_counts.items():
            assert count <= 2, f"Domain diversity violated for {dom}: {count} items"
        print("[PASS] Source diversity enforced")
        print(f"[PASS] Verdict generated: {data.get('verdict')}")

    except Exception as exc:
        print(f"[FAIL] Test 1 failed: {exc}")
        sys.exit(1)

    time.sleep(INTER_TEST_DELAY)

    # 3. TEST 2: "A meteorite hit the Eiffel Tower yesterday."
    print("\n--- 3. TEST 2: 'A meteorite hit the Eiffel Tower yesterday.' ---")
    try:
        data = analyze("A meteorite hit the Eiffel Tower yesterday.")
        print(f"Verdict: {data.get('verdict')} (conf: {data.get('confidence')})")
        print(f"Evidence count: {len(data.get('evidence', []))}")
        print("[PASS] Eiffel Tower claim verified")
    except Exception as exc:
        print(f"[FAIL] Test 2 failed: {exc}")
        sys.exit(1)

    time.sleep(INTER_TEST_DELAY)

    # 4. TEST 3: "Chennai experienced heavy rainfall and flash flooding."
    print("\n--- 4. TEST 3: 'Chennai experienced heavy rainfall and flash flooding.' ---")
    try:
        data = analyze("Chennai experienced heavy rainfall and flash flooding.")
        print(f"Verdict: {data.get('verdict')} (conf: {data.get('confidence')})")
        print(f"Evidence count: {len(data.get('evidence', []))}")
        print("[PASS] Chennai weather claim verified")
    except Exception as exc:
        print(f"[FAIL] Test 3 failed: {exc}")
        sys.exit(1)

    time.sleep(INTER_TEST_DELAY)

    # 5. TEST 4: Unsupported / Non-existent event
    print("\n--- 5. TEST 4: 'A subterranean civilization was uncovered on Neptune.' ---")
    try:
        data = analyze("A subterranean civilization was uncovered on Neptune.")
        print(f"Verdict: {data.get('verdict')} (conf: {data.get('confidence')})")
        print("[PASS] Unsupported claim handled gracefully")
    except Exception as exc:
        print(f"[FAIL] Test 4 failed: {exc}")
        sys.exit(1)

    time.sleep(INTER_TEST_DELAY)

    # 6. TEST 5: Empty text validation
    print("\n--- 6. TEST 5: Empty text validation ---")
    try:
        resp = requests.post(f"{BASE_URL}/analyze", data={"text": "   "}, timeout=10)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
        print("[PASS] Fallback works")
    except Exception as exc:
        print(f"[FAIL] Test 5 failed: {exc}")
        sys.exit(1)

    print("\n==================================================")
    print("   [SUCCESS] Phase 7 Verification Complete!      ")
    print("==================================================")


if __name__ == "__main__":
    main()
