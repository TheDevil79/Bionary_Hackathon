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
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center gap-3">
        <Network className="w-5 h-5 text-indigo-600" />
        <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">Evidence Graph</h2>
      </div>
      
      <div className="p-8 overflow-x-auto bg-[#FAFAFA]">
        <div className="flex flex-col gap-12 min-w-[700px] py-4">
          {edges.map((edge, idx) => (
            <div key={`${edge.claim.id}-${edge.evidence.id}-${idx}`} className="flex items-center justify-between gap-6 group">
              
              {/* Source Node (Claim) */}
              <div className="w-[40%] bg-white border border-slate-200 rounded-xl p-6 shadow-sm relative hover:border-indigo-400 hover:shadow-md transition-all z-10">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                  <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">Claim Node</span>
                </div>
                <p className="text-sm font-semibold text-slate-800 line-clamp-3 leading-relaxed">
                  {edge.claim.text}
                </p>
                <div className="absolute -right-3 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-indigo-200 group-hover:border-indigo-400 transition-colors z-20"></div>
              </div>

              {/* Edge */}
              <div className="flex-1 flex flex-col items-center justify-center relative">
                <div className={clsx(
                  "w-full h-[2px] absolute top-1/2 -z-10 transition-colors duration-300",
                  edge.type === 'SUPPORTS' ? 'bg-emerald-200 group-hover:bg-emerald-400' : 'bg-rose-200 group-hover:bg-rose-400'
                )}></div>
                <div className={clsx(
                  "px-3 py-1.5 rounded text-[10px] font-black tracking-widest uppercase bg-white border shadow-sm flex items-center gap-1 z-10 transition-colors",
                  edge.type === 'SUPPORTS' ? 'border-emerald-300 text-emerald-700' : 'border-rose-300 text-rose-700'
                )}>
                  {edge.type}
                </div>
              </div>

              {/* Target Node (Evidence) */}
              <div className="w-[40%] bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-all z-10 overflow-hidden relative">
                <div className={clsx(
                  "absolute top-0 left-0 w-1.5 h-full transition-colors",
                  edge.type === 'SUPPORTS' ? 'bg-emerald-500' : 'bg-rose-500'
                )} />
                <div className="absolute -left-3 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-slate-300 z-20"></div>
                
                <div className="pl-3">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                    <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">Evidence Node</span>
                  </div>
                  <p className="text-sm font-bold text-slate-900 line-clamp-2 mb-2 leading-snug">
                    {edge.evidence.title || 'Unknown Source'}
                  </p>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 bg-slate-100 px-2 py-0.5 rounded">{edge.evidence.publisher}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
