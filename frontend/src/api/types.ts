/**
 * EvidenceLens — Frontend API TypeScript Definitions
 * 
 * Sourced directly from docs/API_CONTRACT.md and backend/app/schemas/claim.py.
 */

export type Verdict =
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'MIXED'
  | 'INSUFFICIENT_EVIDENCE';

export type Relationship =
  | 'SUPPORTS'
  | 'CONTRADICTS'
  | 'CONTEXT_MISMATCH';

export interface AtomicClaim {
  id: string;
  text: string;
  verdict: Verdict;
  confidence: number;
}

export interface PreviousOccurrence {
  date: string | null;
  source: string | null;
  url: string | null;
}

export interface MediaAnalysis {
  analyzed: boolean;
  matched: boolean;
  similarity: number | null;
  context_mismatch: boolean;
  previous_occurrence: PreviousOccurrence | null;
}

export interface EvidenceItem {
  id: string;
  title: string;
  publisher: string | null;
  published_at: string | null;
  url: string | null;
  excerpt: string;
  relationship: Relationship;
  relevance_score: number;
}

export interface AnalyzeResponse {
  claim_id: string;
  atomic_claims: AtomicClaim[];
  verdict: Verdict;
  confidence: number;
  evidence: EvidenceItem[];
  media_analysis: MediaAnalysis | null;
  uncertainty: string[];
  analyst_notes: string | null;
}

// Backward-compatibility alias during integration
export type VerificationResponse = AnalyzeResponse;
export type ClaimResult = AtomicClaim;
