import { ClaimResult, EvidenceItem } from '../api/types';
import { Network } from 'lucide-react';
import { clsx } from 'clsx';

interface EvidenceGraphProps {
  claims: ClaimResult[];
}

export default function EvidenceGraph({ claims }: EvidenceGraphProps) {
  if (!claims || claims.length === 0) return null;

  // Flatten the relationships into edges for the graph visualization
  const edges: { claim: ClaimResult; evidence: EvidenceItem; type: 'SUPPORTS' | 'CONTRADICTS' }[] = [];
  
  claims.forEach(claim => {
    claim.supporting_evidence.forEach(ev => edges.push({ claim, evidence: ev, type: 'SUPPORTS' }));
    claim.contradicting_evidence.forEach(ev => edges.push({ claim, evidence: ev, type: 'CONTRADICTS' }));
  });

  if (edges.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 flex items-center gap-2">
        <Network className="w-5 h-5 text-slate-500" />
        <h2 className="text-lg font-semibold text-slate-800">Evidence Graph</h2>
      </div>
      <div className="p-8 overflow-x-auto">
        <div className="flex flex-col gap-8 min-w-[600px]">
          {edges.map((edge, idx) => (
            <div key={`${edge.claim.id}-${edge.evidence.id}-${idx}`} className="flex items-center justify-between gap-4">
              {/* Source Node (Claim) */}
              <div className="w-1/3 bg-slate-100 border border-slate-300 rounded-lg p-4 shadow-sm relative">
                <span className="text-xs font-bold text-slate-400 uppercase mb-1 block">Claim Node</span>
                <p className="text-sm font-medium text-slate-800 line-clamp-3">
                  {edge.claim.text}
                </p>
              </div>

              {/* Edge */}
              <div className="w-1/3 flex flex-col items-center justify-center relative">
                <div className="w-full h-px bg-slate-300 absolute top-1/2 -z-10"></div>
                <div className={clsx(
                  "px-3 py-1 rounded-full text-xs font-bold bg-white border shadow-sm flex items-center gap-1",
                  edge.type === 'SUPPORTS' ? 'border-green-300 text-green-700' : 'border-red-300 text-red-700'
                )}>
                  {edge.type}
                </div>
              </div>

              {/* Target Node (Evidence) */}
              <div className="w-1/3 bg-slate-50 border border-slate-200 rounded-lg p-4 shadow-sm border-l-4" style={{ 
                borderLeftColor: edge.type === 'SUPPORTS' ? '#22c55e' : '#ef4444' 
              }}>
                <span className="text-xs font-bold text-slate-400 uppercase mb-1 block">Source Node</span>
                <p className="text-sm font-medium text-slate-800 line-clamp-2 mb-1">
                  {edge.evidence.title || 'Unknown Source'}
                </p>
                <span className="text-xs text-slate-500">{edge.evidence.publisher}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
