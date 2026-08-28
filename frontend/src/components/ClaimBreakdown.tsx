import { ClaimResult } from '../api/types';
import VerdictBadge from './VerdictBadge';
import { ShieldAlert } from 'lucide-react';

interface ClaimBreakdownProps {
  claims: ClaimResult[];
}

export default function ClaimBreakdown({ claims }: ClaimBreakdownProps) {
  if (!claims || claims.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 flex items-center gap-2">
        <ShieldAlert className="w-5 h-5 text-slate-500" />
        <h2 className="text-lg font-semibold text-slate-800">Claim Breakdown</h2>
      </div>
      <div className="divide-y divide-slate-100">
        {claims.map((claim, index) => (
          <div key={claim.id} className="p-6 flex flex-col md:flex-row md:items-start justify-between gap-4 hover:bg-slate-50/50 transition-colors">
            <div className="flex-1">
              <span className="text-xs font-bold text-slate-400 tracking-wider uppercase mb-1 block">Claim {index + 1}</span>
              <p className="text-slate-900 font-medium text-lg">"{claim.text}"</p>
            </div>
            <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
              <VerdictBadge verdict={claim.verdict} size="md" />
              <div className="text-sm text-slate-500 font-medium">
                Confidence: <span className="text-slate-900">{Math.round(claim.confidence * 100)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
