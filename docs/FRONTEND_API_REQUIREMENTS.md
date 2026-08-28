# Frontend API Requirements: EvidenceLens

This document outlines the strict API contracts expected by the frontend. The backend developer (`var_dev`) should implement these endpoints to match this exact schema. 

## 1. Verify Claim
**Endpoint:** `POST /api/v1/verify`
**Description:** Submits a text claim and an optional media ID for verification.
**UI Component:** `LandingPage`, `ResultsPage`

**Request Body (JSON):**
```json
{
  "text": "The text of the claim provided by the user.",
  "media_id": "optional-media-id-string"
}
```

**Response (JSON):**
```json
{
  "verification_id": "string",
  "overall_verdict": "SUPPORTED" | "CONTRADICTED" | "MIXED" | "INSUFFICIENT EVIDENCE" | "INSUFFICIENT",
  "confidence": number, // 0.0 to 1.0
  "claims": [
    {
      "id": "string",
      "text": "string",
      "verdict": "SUPPORTED" | "CONTRADICTED" | "MIXED" | "INSUFFICIENT EVIDENCE" | "INSUFFICIENT",
      "confidence": number, // 0.0 to 1.0
      "supporting_evidence": [
        {
          "id": "string",
          "publisher": "string",
          "title": "string",
          "publication_date": "YYYY-MM-DD",
          "source_type": "string",
          "excerpt": "string",
          "relevance_score": number, // 0 to 100
          "url": "string"
        }
      ],
      "contradicting_evidence": [
        // Same structure as supporting_evidence
      ]
    }
  ],
  "media_analysis": {
    "similarity_score": number, // optional, 0 to 100
    "previous_occurrence_date": "YYYY-MM-DD" | null,
    "possible_context_mismatch": "string" | null,
    "metadata": {
      "original_upload_date": "YYYY-MM-DD" | null,
      "location": "string" | null
    }
  } | null,
  "uncertainty": [
    {
      "field": "string",
      "reason": "string"
    }
  ]
}
```

## 2. Submit Analyst Feedback (Optional/Future)
**Endpoint:** `POST /api/v1/feedback`
**Description:** Allows an analyst to submit corrections.
**UI Component:** `AnalystReview`

**Request Body (JSON):**
```json
{
  "verification_id": "string",
  "is_correct": boolean,
  "correction_note": "string"
}
```

**Response (JSON):**
```json
{
  "success": true
}
```
