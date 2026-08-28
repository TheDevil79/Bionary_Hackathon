// ─── UI-facing types (consumed by all components) ───────────────────────────
// These remain stable so NO component code needs to change.

export type Verdict = 'SUPPORTED' | 'CONTRADICTED' | 'MIXED' | 'INSUFFICIENT EVIDENCE' | 'INSUFFICIENT' | 'INSUFFICIENT_EVIDENCE';

export interface EvidenceItem {
  id: string;
  publisher: string;
  title: string;
  publication_date: string;
  source_type: string;
  excerpt: string;
  relevance_score: number;
  url: string;
}

export interface ClaimResult {
  id: string;
  text: string;
  verdict: Verdict;
  confidence: number;
  supporting_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
}

export interface MediaAnalysis {
  similarity_score?: number;
  previous_occurrence_date?: string | null;
  possible_context_mismatch?: string | null;
  metadata?: {
    original_upload_date: string | null;
    location: string | null;
  };
}

export interface UncertaintyItem {
  field: string;
  reason: string;
}

export interface VerificationResponse {
  verification_id: string;
  overall_verdict: Verdict;
  confidence: number;
  claims: ClaimResult[];
  media_analysis: MediaAnalysis | null;
  uncertainty: UncertaintyItem[];
}


// ─── Backend raw response types (exact mirror of POST /analyze) ──────────────

export interface BackendAtomicClaim {
  id: string;
  text: string;
  verdict: string;
  confidence: number;
}

export interface BackendPreviousOccurrence {
  date: string | null;
  source: string | null;
  url: string | null;
}

export interface BackendMediaAnalysis {
  analyzed: boolean;
  matched: boolean;
  similarity: number | null;
  context_mismatch: boolean;
  previous_occurrence: BackendPreviousOccurrence | null;
}

export interface BackendEvidenceItem {
  id: string;
  title: string;
  publisher: string | null;
  published_at: string | null;
  url: string | null;
  excerpt: string;
  relationship: 'SUPPORTS' | 'CONTRADICTS' | 'CONTEXT_MISMATCH';
  relevance_score: number;
}

export interface BackendAnalyzeResponse {
  claim_id: string;
  atomic_claims: BackendAtomicClaim[];
  verdict: string;
  confidence: number;
  evidence: BackendEvidenceItem[];
  media_analysis: BackendMediaAnalysis | null;
  uncertainty: string[];
  analyst_notes: string | null;
}
