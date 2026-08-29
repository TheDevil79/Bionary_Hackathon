"""
EvidenceLens — Phase 6 End-to-End Verification Script

Tests:
  1. Backend /health liveness and database status
  2. Frontend dev server accessibility
  3. POST /analyze (Claim 1: "A meteorite hit the Eiffel Tower yesterday.")
  4. POST /analyze (Claim 2: "Chennai received heavy rainfall and experienced flash floods.")
  5. POST /analyze with multimodal image attachment
  6. POST /analyze with unsupported media (415 error handling)
  7. POST /analyze with empty text (422 error handling)
"""

import io
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode


def test_health():
    print("\n--- 1. Testing GET http://127.0.0.1:8000/health ---")
    req = urllib.request.Request("http://127.0.0.1:8000/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        print(f"Health response: {data}")
        assert data.get("status") == "ok"
        print("PASS: Health endpoint OK")


def test_frontend_server():
    print("\n--- 2. Testing GET http://localhost:5173/ ---")
    req = urllib.request.Request("http://localhost:5173/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "EvidenceLens" in html or "<div id=\"root\">" in html
        print(f"Frontend response status: {resp.status}, HTML length: {len(html)}")
        print("PASS: Frontend dev server serving successfully")


def multipart_post(url, fields, files=None):
    boundary = "----WebKitFormBoundaryEvidenceLens7MA4YWxkTrZu0gW"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    if files:
        for name, (filename, content, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(content)
            body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return req


def test_claim_1_meteorite():
    print("\n--- 3. TEST 1: 'A meteorite hit the Eiffel Tower yesterday.' ---")
    req = multipart_post(
        "http://127.0.0.1:8000/analyze",
        {"text": "A meteorite hit the Eiffel Tower yesterday."},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        print(f"Claim ID: {data['claim_id']}")
        print(f"Overall Verdict: {data['verdict']}")
        print(f"Confidence: {data['confidence']}")
        print(f"Atomic claims count: {len(data['atomic_claims'])}")
        for c in data["atomic_claims"]:
            print(f"  - [{c['verdict']}] (conf: {c['confidence']}) {c['text']}")
        print(f"Evidence count: {len(data['evidence'])}")
        for e in data["evidence"]:
            print(f"  - [{e['relationship']}] {e['title']} (rel: {e['relevance_score']})")
        print(f"Uncertainty: {data.get('uncertainty')}")
        assert data["verdict"] in ["CONTRADICTED", "SUPPORTED", "MIXED", "INSUFFICIENT_EVIDENCE"]
        print("PASS: Claim 1 verified successfully")


def test_claim_2_chennai():
    print("\n--- 4. TEST 2: 'Chennai received heavy rainfall and experienced flash floods.' ---")
    req = multipart_post(
        "http://127.0.0.1:8000/analyze",
        {"text": "Chennai received heavy rainfall and experienced flash floods."},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        print(f"Claim ID: {data['claim_id']}")
        print(f"Overall Verdict: {data['verdict']}")
        print(f"Confidence: {data['confidence']}")
        print(f"Atomic claims count: {len(data['atomic_claims'])}")
        for c in data["atomic_claims"]:
            print(f"  - [{c['verdict']}] (conf: {c['confidence']}) {c['text']}")
        print(f"Evidence count: {len(data['evidence'])}")
        for e in data["evidence"]:
            print(f"  - [{e['relationship']}] {e['title']} (rel: {e['relevance_score']})")
        print("PASS: Claim 2 verified successfully")


def test_claim_3_image():
    print("\n--- 5. TEST 3: Claim with Image attachment ---")
    # Generate 1x1 dummy PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    req = multipart_post(
        "http://127.0.0.1:8000/analyze",
        {"text": "Photo shows submerged cars after flash floods."},
        files={"media": ("flood.png", png_bytes, "image/png")},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        print(f"Overall Verdict: {data['verdict']}")
        print(f"Media Analysis: {data.get('media_analysis')}")
        assert data.get("media_analysis") is not None
        assert data["media_analysis"].get("analyzed") is True
        print("PASS: Multimodal image submission verified")


def test_unsupported_media():
    print("\n--- 6. TEST 4: Unsupported media type (PDF) ---")
    req = multipart_post(
        "http://127.0.0.1:8000/analyze",
        {"text": "Sample claim with PDF"},
        files={"media": ("doc.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Expected 415 HTTPError"
    except urllib.error.HTTPError as exc:
        print(f"Received expected status code: {exc.code}")
        body = json.loads(exc.read().decode())
        print(f"Error detail: {body.get('detail')}")
        assert exc.code == 415
        print("PASS: 415 Unsupported Media Type verified")


def test_validation_error():
    print("\n--- 7. TEST 5: Empty text validation error ---")
    req = multipart_post(
        "http://127.0.0.1:8000/analyze",
        {"text": "   "},
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Expected 422 HTTPError"
    except urllib.error.HTTPError as exc:
        print(f"Received expected status code: {exc.code}")
        body = json.loads(exc.read().decode())
        print(f"Error detail: {body.get('detail')}")
        assert exc.code == 422
        print("PASS: 422 Validation error verified")


if __name__ == "__main__":
    test_health()
    test_frontend_server()
    test_claim_1_meteorite()
    test_claim_2_chennai()
    test_claim_3_image()
    test_unsupported_media()
    test_validation_error()
    print("\n==========================================")
    print("ALL PHASE 6 END-TO-END VERIFICATIONS PASSED!")
    print("==========================================")
