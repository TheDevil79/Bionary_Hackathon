import { ClaimResult } from '../api/types';
import VerdictBadge from './VerdictBadge';
import { FileText } from 'lucide-react';

interface ClaimBreakdownProps {
  claims: ClaimResult[];
}

export default function ClaimBreakdown({ claims }: ClaimBreakdownProps) {
  if (!claims || claims.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center gap-3">
        <FileText className="w-5 h-5 text-indigo-600" />
        <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">Claim Breakdown</h2>
      </div>
      <div className="divide-y divide-slate-100">
        {claims.map((claim, index) => (
          <div key={claim.id} className="p-6 md:p-8 flex flex-col md:flex-row md:items-start justify-between gap-8 hover:bg-slate-50/50 transition-colors group">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className="bg-indigo-100 text-indigo-800 text-[10px] font-black tracking-widest uppercase px-2 py-0.5 rounded">
                  Claim 0{index + 1}
                </span>
                <span className="text-[10px] font-mono text-slate-400">ID: {claim.id}</span>
              </div>
              <p className="text-slate-900 font-medium text-xl leading-relaxed border-l-2 border-indigo-200 pl-4">
                {claim.text}
              </p>
            </div>
            <div className="flex flex-col items-start md:items-end gap-4 shrink-0 w-full md:w-auto bg-slate-50 md:bg-transparent p-5 md:p-0 rounded-lg md:rounded-none border border-slate-100 md:border-none">
              <VerdictBadge verdict={claim.verdict} size="md" />
              <div className="text-xs text-slate-500 font-bold uppercase tracking-wider flex items-center gap-2">
                Confidence: <span className="text-slate-900 font-black text-lg bg-white px-2 py-0.5 rounded border border-slate-200">{Math.round(claim.confidence * 100)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
