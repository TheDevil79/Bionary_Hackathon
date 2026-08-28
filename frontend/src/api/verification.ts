import { VerificationResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export interface VerifyRequest {
  text: string;
  media_id?: string;
}

export async function verify(request: VerifyRequest): Promise<VerificationResponse> {
  if (USE_MOCKS) {
    // Dynamic isolated mock
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          verification_id: `ver_${Math.random().toString(36).substring(2, 9)}`,
          overall_verdict: 'MIXED',
          confidence: 0.85,
          claims: [
            {
              id: `claim_${Math.random().toString(36).substring(2, 6)}`,
              text: request.text || "Analyzed generic claim.",
              verdict: 'SUPPORTED',
              confidence: 0.92,
              supporting_evidence: [
                {
                  id: 'ev_sup_1',
                  publisher: 'Mock Verified Source',
                  title: 'Corroborating Report for Uploaded Claim',
                  publication_date: new Date().toISOString().split('T')[0],
                  source_type: 'News Article',
                  excerpt: 'This automatically generated mock excerpt supports the text you just uploaded.',
                  relevance_score: 95,
                  url: 'https://example.com/mock-support'
                }
              ],
              contradicting_evidence: []
            },
            {
              id: `claim_${Math.random().toString(36).substring(2, 6)}`,
              text: "Implicit secondary claim derived from context.",
              verdict: 'CONTRADICTED',
              confidence: 0.78,
              supporting_evidence: [],
              contradicting_evidence: [
                {
                  id: 'ev_con_1',
                  publisher: 'Mock Fact Check',
                  title: 'Fact Check: Secondary element is false',
                  publication_date: '2026-08-20',
                  source_type: 'Fact Check',
                  excerpt: 'An investigation revealed that the secondary elements of this claim are entirely false.',
                  relevance_score: 89,
                  url: 'https://example.com/mock-contradict'
                }
              ]
            }
          ],
          media_analysis: request.media_id ? {
            similarity_score: 88,
            previous_occurrence_date: '2025-01-01',
            possible_context_mismatch: 'The attached media appears to be older than the text implies.',
          } : null,
          uncertainty: []
        });
      }, 3500); // Wait 3.5s to allow for professional loading state sequencing
    });
  }

  const response = await fetch(`${API_BASE}/api/v1/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error('Verification failed from backend API');
  }

  return response.json();
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

  const response = await fetch(`${API_BASE}/api/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feedback),
  });

  if (!response.ok) {
    throw new Error('Failed to submit feedback');
  }

  return response.json();
}
