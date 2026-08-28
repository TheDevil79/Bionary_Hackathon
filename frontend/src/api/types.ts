export type Verdict = 'SUPPORTED' | 'CONTRADICTED' | 'MIXED' | 'INSUFFICIENT EVIDENCE' | 'INSUFFICIENT';

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
