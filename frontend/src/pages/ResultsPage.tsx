import { useLocation, Navigate, Link } from 'react-router-dom';
import { VerificationResponse, EvidenceItem } from '../api/types';
import VerdictBadge from '../components/VerdictBadge';
import ClaimBreakdown from '../components/ClaimBreakdown';
import EvidencePanel from '../components/EvidencePanel';
import MediaForensics from '../components/MediaForensics';
import EvidenceGraph from '../components/EvidenceGraph';
import AnalystReview from '../components/AnalystReview';
import { ArrowLeft, BarChart3 } from 'lucide-react';

export default function ResultsPage() {
  const location = useLocation();
  const result = location.state?.result as VerificationResponse | undefined;

  if (!result) {
    return <Navigate to="/" replace />;
  }

  // Flatten the evidence for the generic Evidence Panel
  const allEvidence: (EvidenceItem & { relationship: 'SUPPORTS' | 'CONTRADICTS' })[] = [];
  result.claims.forEach(claim => {
    claim.supporting_evidence.forEach(ev => {
      // only add if not already present to avoid pure duplicates in UI
      if (!allEvidence.some(e => e.id === ev.id && e.relationship === 'SUPPORTS')) {
        allEvidence.push({ ...ev, relationship: 'SUPPORTS' });
      }
    });
    claim.contradicting_evidence.forEach(ev => {
      if (!allEvidence.some(e => e.id === ev.id && e.relationship === 'CONTRADICTS')) {
        allEvidence.push({ ...ev, relationship: 'CONTRADICTS' });
      }
    });
  });

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-8 pb-10">
      
      <div className="flex items-center gap-4">
        <Link to="/" className="p-2 hover:bg-slate-200 bg-slate-100 rounded-full text-slate-600 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          Verification Results
        </h1>
      </div>

      {/* Overview Card */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <span className="text-sm font-bold tracking-wider text-slate-400 uppercase mb-2 block">Overall Verdict</span>
          <VerdictBadge verdict={result.overall_verdict} size="lg" />
        </div>
        
        <div className="hidden md:block w-px h-16 bg-slate-200"></div>
        
        <div>
          <span className="text-sm font-bold tracking-wider text-slate-400 uppercase mb-2 block">Overall Confidence</span>
          <div className="flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-indigo-500" />
            <span className="text-4xl font-extrabold text-slate-900">{Math.round(result.confidence * 100)}%</span>
          </div>
        </div>
        
        <div className="hidden md:block w-px h-16 bg-slate-200"></div>

        <div>
          <span className="text-sm font-bold tracking-wider text-slate-400 uppercase mb-2 block">Job ID</span>
          <span className="font-mono text-slate-600">{result.verification_id}</span>
        </div>
      </div>

      {/* Subcomponents */}
      <ClaimBreakdown claims={result.claims} />
      
      {result.media_analysis && (
        <MediaForensics analysis={result.media_analysis} />
      )}

      <EvidenceGraph claims={result.claims} />

      <EvidencePanel evidence={allEvidence} />

      <div className="mt-8">
        <AnalystReview verificationId={result.verification_id} />
      </div>

    </div>
  );
}
