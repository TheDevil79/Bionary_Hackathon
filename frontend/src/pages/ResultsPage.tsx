import { useLocation, Navigate, Link } from 'react-router-dom';
import { AnalyzeResponse } from '../api/types';
import VerdictBadge from '../components/VerdictBadge';
import ClaimBreakdown from '../components/ClaimBreakdown';
import EvidencePanel from '../components/EvidencePanel';
import MediaForensics from '../components/MediaForensics';
import EvidenceGraph from '../components/EvidenceGraph';
import AnalystReview from '../components/AnalystReview';
import { ArrowLeft, Crosshair, Fingerprint, Search, AlertCircle, Quote } from 'lucide-react';

export default function ResultsPage() {
  const location = useLocation();
  const result = location.state?.result as AnalyzeResponse | undefined;
  const userClaim = location.state?.userClaim as string | undefined;

  if (!result) {
    return <Navigate to="/" replace />;
  }

  const confidencePct =
    result.confidence <= 1.0 ? Math.round(result.confidence * 100) : Math.round(result.confidence);

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-8 pb-12 animate-in slide-in-from-bottom-4 duration-700">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-indigo-600 transition-colors shadow-sm font-semibold text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          NEW INVESTIGATION
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-widest">
            Claim ID
          </span>
          <span className="font-mono text-slate-700 bg-white px-3 py-1 rounded border border-slate-200 shadow-sm text-sm">
            {typeof result.claim_id === 'string' ? result.claim_id.substring(0, 18) + '...' : result.claim_id}
          </span>
        </div>
      </div>

      {/* Submitted Claim Banner */}
      {userClaim && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex items-start gap-4">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg shrink-0">
            <Quote className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block mb-1">
              Submitted Statement
            </span>
            <p className="text-base font-semibold text-slate-800 leading-relaxed">
              "{userClaim}"
            </p>
          </div>
        </div>
      )}

      {/* Intelligence Dossier Header */}
      <div className="bg-slate-900 rounded-2xl shadow-2xl overflow-hidden relative border border-slate-800">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>

        <div className="px-8 py-6 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between relative z-10">
          <div className="flex items-center gap-3">
            <Search className="w-5 h-5 text-indigo-400" />
            <h1 className="text-xl font-bold text-white tracking-tight">Intelligence Brief</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
              Analysis Complete
            </span>
          </div>
        </div>

        <div className="p-8 md:p-12 flex flex-col md:flex-row md:items-center justify-between gap-10 relative z-10">
          <div className="flex-1">
            <span className="text-[11px] font-black tracking-widest text-slate-400 uppercase mb-4 flex items-center gap-2">
              <Crosshair className="w-4 h-4 text-slate-500" />
              Primary Grounded Assessment
            </span>
            <VerdictBadge verdict={result.verdict} size="lg" />
          </div>

          <div className="hidden md:block w-px h-24 bg-slate-800 relative z-10"></div>
          <div className="md:hidden h-px w-full bg-slate-800 relative z-10"></div>

          <div className="flex-1 md:text-center">
            <span className="text-[11px] font-black tracking-widest text-slate-400 uppercase mb-4 flex items-center md:justify-center gap-2">
              <Fingerprint className="w-4 h-4 text-slate-500" />
              Synthesis Confidence
            </span>
            <div className="flex items-baseline md:justify-center gap-1">
              <span className="text-6xl font-black text-white tracking-tighter leading-none">
                {confidencePct}
              </span>
              <span className="text-2xl font-bold text-slate-500">%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Uncertainty & Nuance Alert if present */}
      {result.uncertainty && result.uncertainty.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 shadow-sm flex items-start gap-4">
          <div className="p-2 bg-white rounded-lg border border-amber-100 text-amber-600 shrink-0">
            <AlertCircle className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="text-xs font-black text-amber-900 uppercase tracking-widest mb-2">
              Assessment Nuances & Uncertainty Notes
            </h3>
            <ul className="list-disc list-inside space-y-1.5 text-sm text-amber-800 font-medium">
              {result.uncertainty.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Analysis Modules */}
      <div className="grid grid-cols-1 gap-10 mt-2">
        {/* 1. Atomic Claims */}
        <ClaimBreakdown claims={result.atomic_claims} />

        {/* 2. Media Forensics (if media was attached) */}
        {result.media_analysis && <MediaForensics analysis={result.media_analysis} />}

        {/* 3. Evidence Provenance Graph */}
        <EvidenceGraph claims={result.atomic_claims} evidence={result.evidence} />

        {/* 4. Retrieved Evidence Corpus */}
        <EvidencePanel evidence={result.evidence} />

        {/* 5. Optional Analyst Feedback Section */}
        <div className="mt-6 border-t-2 border-dashed border-slate-200 pt-10">
          <AnalystReview verificationId={result.claim_id} />
        </div>
      </div>
    </div>
  );
}
