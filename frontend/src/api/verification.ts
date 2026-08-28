import {
  VerificationResponse,
  BackendAnalyzeResponse,
  BackendEvidenceItem,
  ClaimResult,
  EvidenceItem,
  MediaAnalysis,
  UncertaintyItem,
  Verdict,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

// ─── Request interface ───────────────────────────────────────────────────────

export interface VerifyRequest {
  text: string;
  file?: File | null;
}

// ─── Backend → UI Adapter ────────────────────────────────────────────────────

function mapVerdict(raw: string): Verdict {
  const v = raw.toUpperCase().replace(/_/g, ' ');
  if (v === 'SUPPORTED') return 'SUPPORTED';
  if (v === 'CONTRADICTED') return 'CONTRADICTED';
  if (v === 'MIXED') return 'MIXED';
  if (v === 'INSUFFICIENT EVIDENCE' || v === 'INSUFFICIENT_EVIDENCE') return 'INSUFFICIENT EVIDENCE';
  return 'INSUFFICIENT EVIDENCE';
}

function mapEvidenceItem(be: BackendEvidenceItem): EvidenceItem {
  return {
    id: String(be.id),
    publisher: be.publisher || 'Unknown',
    title: be.title,
    publication_date: be.published_at || '',
    source_type: be.relationship === 'SUPPORTS' ? 'Supporting Source' : be.relationship === 'CONTRADICTS' ? 'Contradicting Source' : 'Related Source',
    excerpt: be.excerpt,
    // Backend uses 0.0-1.0 scale, frontend displays as 0-100
    relevance_score: Math.round(be.relevance_score * 100),
    url: be.url || '',
  };
}

function transformBackendResponse(raw: BackendAnalyzeResponse): VerificationResponse {
  // Group evidence by claim: backend returns a flat evidence list, so we
  // distribute evidence to ALL claims (the backend doesn't map evidence per claim
  // in the response — the verdict engine does this internally).
  const supportingEvidence = raw.evidence
    .filter(e => e.relationship === 'SUPPORTS')
    .map(mapEvidenceItem);
  const contradictingEvidence = raw.evidence
    .filter(e => e.relationship === 'CONTRADICTS' || e.relationship === 'CONTEXT_MISMATCH')
    .map(mapEvidenceItem);

  const claims: ClaimResult[] = raw.atomic_claims.map(ac => ({
    id: ac.id,
    text: ac.text,
    verdict: mapVerdict(ac.verdict),
    confidence: ac.confidence,
    // Distribute evidence based on claim verdict for the UI breakdown
    supporting_evidence: ac.verdict === 'SUPPORTED' || ac.verdict === 'MIXED' ? supportingEvidence : [],
    contradicting_evidence: ac.verdict === 'CONTRADICTED' || ac.verdict === 'MIXED' ? contradictingEvidence : [],
  }));

  // Transform media_analysis
  let media_analysis: MediaAnalysis | null = null;
  if (raw.media_analysis && raw.media_analysis.analyzed) {
    media_analysis = {
      similarity_score: raw.media_analysis.similarity !== null
        ? Math.round(raw.media_analysis.similarity * 100)
        : undefined,
      previous_occurrence_date: raw.media_analysis.previous_occurrence?.date || null,
      possible_context_mismatch: raw.media_analysis.context_mismatch
        ? `Media matched a prior occurrence${raw.media_analysis.previous_occurrence?.source ? ` from ${raw.media_analysis.previous_occurrence.source}` : ''}. This may indicate recycled or misattributed media.`
        : null,
      metadata: {
        original_upload_date: raw.media_analysis.previous_occurrence?.date || null,
        location: raw.media_analysis.previous_occurrence?.source || null,
      },
    };
  }

  // Transform uncertainty (backend sends string[], UI wants {field, reason}[])
  const uncertainty: UncertaintyItem[] = raw.uncertainty.map((u, i) => ({
    field: `note_${i + 1}`,
    reason: u,
  }));

  return {
    verification_id: String(raw.claim_id),
    overall_verdict: mapVerdict(raw.verdict),
    confidence: raw.confidence,
    claims,
    media_analysis,
    uncertainty,
  };
}


// ─── Main verify function ────────────────────────────────────────────────────

export async function verify(request: VerifyRequest): Promise<VerificationResponse> {
  if (USE_MOCKS) {
    // Dynamic isolated mock — kept for offline development
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          verification_id: `ver_${Math.random().toString(36).substring(2, 9)}`,
          overall_verdict: 'MIXED',
          confidence: 0.85,
          claims: [
            {
              id: `C1`,
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
              id: `C2`,
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
          media_analysis: request.file ? {
            similarity_score: 88,
            previous_occurrence_date: '2025-01-01',
            possible_context_mismatch: 'The attached media appears to be older than the text implies.',
          } : null,
          uncertainty: []
        });
      }, 3500);
    });
  }

  // ── Real backend call: POST /analyze with multipart/form-data ──────────
  const formData = new FormData();
  formData.append('text', request.text);
  if (request.file) {
    formData.append('media', request.file);
  }

  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    body: formData,
    // Do NOT set Content-Type header — browser sets it with boundary automatically
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail = errorBody?.detail || `Server responded with ${response.status}`;
    throw new Error(detail);
  }

  const backendData: BackendAnalyzeResponse = await response.json();
  return transformBackendResponse(backendData);
}


// ─── Feedback ────────────────────────────────────────────────────────────────

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
