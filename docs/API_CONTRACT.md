# EvidenceLens — API Contract

> **Version:** `1.0.0`  
> **Base URL (Local):** `http://localhost:8000`  
> **Interactive Docs (Swagger):** `http://localhost:8000/docs`  
> **ReDoc:** `http://localhost:8000/redoc`

This document serves as the **SINGLE SOURCE OF TRUTH** between the frontend (`har_dev`) and backend (`var_dev`) developers.

---

## 1. Overview & Conventions

- All responses are JSON (unless otherwise specified).
- Timestamps and dates follow ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`).
- UUIDs are standard RFC 4122 v4 strings.
- Status codes follow standard REST semantics (200, 400, 404, 413, 415, 422, 500, 503).
- CORS is enabled for `http://localhost:5173` (Vite dev server) by default.

---

## 2. Shared Types / Enums

### `Verdict`
```typescript
type Verdict = 
  | "SUPPORTED"
  | "CONTRADICTED"
  | "MIXED"
  | "INSUFFICIENT_EVIDENCE";
```

### `Relationship`
```typescript
type Relationship = 
  | "SUPPORTS"
  | "CONTRADICTS"
  | "CONTEXT_MISMATCH";
```

---

## 3. Endpoints

### 3.1. `GET /health`
Liveness and database readiness probe.

#### Response (`200 OK`)
```json
{
  "status": "ok",
  "database": "ok"
}
```
*Note: `database` may be `"ok"` or `"unavailable"`.*

---

### 3.2. `POST /analyze`
Primary claim verification and provenance pipeline.

#### Request Format
- **Content-Type:** `multipart/form-data`

#### Form Fields
| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | **Yes** | The text claim, social media post, or statement to verify. Non-empty. |
| `media` | File (binary) | No | Optional image or video file. (Max 20MB). |

**Allowed Media Content-Types:**
- Images: `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- Videos: `video/mp4`, `video/quicktime`

#### Response (`200 OK`)
```json
{
  "claim_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "atomic_claims": [
    {
      "id": "C1",
      "text": "A severe flash flood occurred in Chennai.",
      "verdict": "SUPPORTED",
      "confidence": 0.91
    },
    {
      "id": "C2",
      "text": "Over 500 cars were submerged in Marina Beach.",
      "verdict": "CONTRADICTED",
      "confidence": 0.78
    }
  ],
  "verdict": "MIXED",
  "confidence": 0.85,
  "evidence": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "title": "IMD Weather Bulletin: Heavy Rain in Chennai",
      "publisher": "National Meteorological Centre",
      "published_at": "2026-08-27",
      "url": "https://example.com/weather-bulletin",
      "excerpt": "Severe rainfall triggered localized waterlogging and flash floods across Chennai districts on Thursday.",
      "relationship": "SUPPORTS",
      "relevance_score": 0.94
    },
    {
      "id": "00000000-0000-0000-0000-000000000002",
      "title": "Fact Check: Marina Beach viral parking footage",
      "publisher": "FactCheck Today",
      "published_at": "2026-08-28",
      "url": "https://example.com/fact-check-marina",
      "excerpt": "Visuals showing submerged cars circulated on X are from the 2015 floods and not from recent rains.",
      "relationship": "CONTRADICTS",
      "relevance_score": 0.88
    }
  ],
  "media_analysis": {
    "analyzed": true,
    "matched": true,
    "similarity": 0.972,
    "context_mismatch": true,
    "previous_occurrence": {
      "date": "2015-12-02",
      "source": "State Flood Archive",
      "url": "https://example.com/archive-2015"
    }
  },
  "uncertainty": [
    "Image metadata lacked original EXIF capture timestamp."
  ],
  "analyst_notes": null
}
```

*Note: If no media was uploaded, `media_analysis` will be `null`.*

#### Error Responses
- `422 Unprocessable Entity`: Missing or empty `text` field.
  ```json
  {
    "detail": "'text' must not be empty."
  }
  ```
- `415 Unsupported Media Type`: Uploaded file format is not accepted.
  ```json
  {
    "detail": "Unsupported media type 'application/pdf'. Allowed: image/gif, image/jpeg, image/png, image/webp, video/mp4, video/quicktime"
  }
  ```
- `413 Request Entity Too Large`: File exceeds 20MB limit.
  ```json
  {
    "detail": "File exceeds the maximum allowed size of 20 MB."
  }
  ```
- `503 Service Unavailable`: Backend service or model temporarily unreachable.
  ```json
  {
    "detail": "Evidence retrieval service is unavailable. Please try again later."
  }
  ```

---

### 3.3. `GET /evidence/{id}`
Retrieve complete metadata and full context for a specific evidence item.

#### Path Parameters
- `id` (UUID, required): The UUID of the evidence chunk.

#### Response (`200 OK`)
```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "title": "IMD Weather Bulletin: Heavy Rain in Chennai",
  "publisher": "National Meteorological Centre",
  "published_at": "2026-08-27",
  "url": "https://example.com/weather-bulletin",
  "excerpt": "Severe rainfall triggered localized waterlogging and flash floods across Chennai districts on Thursday.",
  "source_type": "news",
  "language": "en"
}
```

#### Error Responses
- `404 Not Found`: Evidence chunk with given UUID not found.
  ```json
  {
    "detail": "Evidence item '00000000-0000-0000-0000-000000000001' not found."
  }
  ```

---

## 4. Frontend Integration Guidelines

1. **FormData Usage:** When submitting to `POST /analyze`, use standard `FormData`:
   ```typescript
   const formData = new FormData();
   formData.append("text", claimText);
   if (file) {
     formData.append("media", file);
   }
   const response = await fetch("http://localhost:8000/analyze", {
     method: "POST",
     body: formData,
   });
   ```
2. **Mocking during frontend development:** If the backend server is offline, the frontend API service should return mock data matching the exact schema above.
