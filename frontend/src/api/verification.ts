import { AnalyzeResponse } from './types';

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
// Normalize by removing any accidental trailing slash or /api suffix
export const API_BASE = RAW_API_BASE.replace(/\/+$/, '').replace(/\/api$/, '');
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export interface VerifyOptions {
  text: string;
  media?: File | null;
}

export async function verify(textOrOptions: string | VerifyOptions, fileArg?: File | null): Promise<AnalyzeResponse> {
  let text = '';
  let media: File | null | undefined = null;

  if (typeof textOrOptions === 'string') {
    text = textOrOptions;
    media = fileArg;
  } else {
    text = textOrOptions.text;
    media = textOrOptions.media;
  }

  if (USE_MOCKS) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          claim_id: `9b1deb4d-${Math.random().toString(36).substring(2, 6)}-4bad-9bdd-2b0d7b3dcb6d`,
          atomic_claims: [
            {
              id: 'C1',
              text: text || 'Sample verified claim.',
              verdict: 'SUPPORTED',
              confidence: 0.91,
            },
            {
              id: 'C2',
              text: 'Secondary contextual assertion regarding event severity.',
              verdict: 'CONTRADICTED',
              confidence: 0.78,
            },
          ],
          verdict: 'MIXED',
          confidence: 0.85,
          evidence: [
            {
              id: '00000000-0000-0000-0000-000000000001',
              title: 'Official Situation Bulletin & Fact Report',
              publisher: 'National Verification Bureau',
              published_at: '2026-08-27',
              url: 'https://example.com/situation-bulletin',
              excerpt: 'Official meteorological reports confirmed heavy precipitation events across the metropolitan region on Thursday.',
              relationship: 'SUPPORTS',
              relevance_score: 0.94,
            },
            {
              id: '00000000-0000-0000-0000-000000000002',
              title: 'Fact Check: Viral incident footage archival verification',
              publisher: 'FactCheck Network',
              published_at: '2026-08-28',
              url: 'https://example.com/fact-check-archive',
              excerpt: 'Visual media circulating online was recorded during an earlier 2015 occurrence and does not reflect current conditions.',
              relationship: 'CONTRADICTS',
              relevance_score: 0.88,
            },
          ],
          media_analysis: media
            ? {
                analyzed: true,
                matched: true,
                similarity: 0.942,
                context_mismatch: true,
                previous_occurrence: {
                  date: '2015-12-02',
                  source: 'State Media Archive',
                  url: 'https://example.com/archive-2015',
                },
              }
            : null,
          uncertainty: [
            'Image metadata lacked original EXIF capture timestamp.',
          ],
          analyst_notes: null,
        });
      }, 1500);
    });
  }

  const formData = new FormData();
  formData.append('text', text);
  if (media) {
    formData.append('media', media);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      body: formData,
      // Note: Do NOT set Content-Type header manually so the browser sets the multipart boundary!
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Unable to connect to EvidenceLens backend at ${API_BASE}. Please verify the server is running. (${errorMsg})`
    );
  }

  if (!response.ok) {
    let errorDetail = '';
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.error || JSON.stringify(errorJson);
    } catch {
      errorDetail = `${response.status} ${response.statusText}`;
    }

    if (response.status === 413) {
      throw new Error(errorDetail || 'File exceeds the maximum allowed size of 20 MB.');
    } else if (response.status === 415) {
      throw new Error(errorDetail || 'Unsupported media type. Supported formats: JPG, PNG, WEBP, GIF, MP4, MOV.');
    } else if (response.status === 422) {
      throw new Error(errorDetail || 'Invalid submission. Claim text must not be empty.');
    } else if (response.status === 503) {
      throw new Error(errorDetail || 'Verification service is temporarily unavailable. Please try again later.');
    } else {
      throw new Error(`Server error (${response.status}): ${errorDetail}`);
    }
  }

  const data: AnalyzeResponse = await response.json();
  return data;
}

export interface FeedbackRequest {
  verification_id: string;
  is_correct: boolean;
  correction_note: string;
}

export async function submitFeedback(feedback: FeedbackRequest): Promise<{ success: boolean }> {
  if (USE_MOCKS) {
    return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 500));
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedback),
    });

    if (!response.ok) {
      return { success: true }; // Graceful degradation for optional analyst feedback
    }

    return response.json();
  } catch {
    // Graceful degradation for optional analyst feedback
    return { success: true };
  }
}
