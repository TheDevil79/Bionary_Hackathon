import { AtomicClaim, EvidenceItem, Relationship } from '../api/types';
import { Network } from 'lucide-react';
import { clsx } from 'clsx';

interface EvidenceGraphProps {
  claims: AtomicClaim[];
  evidence: EvidenceItem[];
}

export default function EvidenceGraph({ claims, evidence }: EvidenceGraphProps) {
  if (!claims || claims.length === 0 || !evidence || evidence.length === 0) {
    return null;
  }

  // Create links between claims and retrieved evidence
  // Each evidence item links to claims or demonstrates the provenance chain
  const edges: {
    claim: AtomicClaim;
    evidence: EvidenceItem;
    type: Relationship;
  }[] = [];

  claims.forEach((claim) => {
    evidence.forEach((ev) => {
      edges.push({
        claim,
        evidence: ev,
        type: ev.relationship,
      });
    });
  });

  if (edges.length === 0) return null;

  const getEdgeStyles = (type: Relationship) => {
    switch (type) {
      case 'SUPPORTS':
        return {
          line: 'bg-emerald-200 group-hover:bg-emerald-400',
          badge: 'border-emerald-300 text-emerald-700 bg-emerald-50',
          bar: 'bg-emerald-500',
        };
      case 'CONTRADICTS':
        return {
          line: 'bg-rose-200 group-hover:bg-rose-400',
          badge: 'border-rose-300 text-rose-700 bg-rose-50',
          bar: 'bg-rose-500',
        };
      case 'CONTEXT_MISMATCH':
      default:
        return {
          line: 'bg-amber-200 group-hover:bg-amber-400',
          badge: 'border-amber-300 text-amber-700 bg-amber-50',
          bar: 'bg-amber-500',
        };
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Network className="w-5 h-5 text-indigo-600" />
          <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">
            Evidence Provenance Graph
          </h2>
        </div>
        <span className="text-[11px] font-mono text-slate-400">Claim ↔ Evidence Mapping</span>
      </div>

      <div className="p-8 overflow-x-auto bg-[#FAFAFA]">
        <div className="flex flex-col gap-8 min-w-[700px] py-2">
          {edges.map((edge, idx) => {
            const styles = getEdgeStyles(edge.type);
            return (
              <div
                key={`${edge.claim.id}-${edge.evidence.id}-${idx}`}
                className="flex items-center justify-between gap-6 group"
              >
                {/* Source Node (Claim) */}
                <div className="w-[40%] bg-white border border-slate-200 rounded-xl p-5 shadow-sm relative hover:border-indigo-400 hover:shadow-md transition-all z-10">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-500"></div>
                    <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">
                      {edge.claim.id || `Claim ${idx + 1}`}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-slate-800 line-clamp-3 leading-relaxed">
                    {edge.claim.text}
                  </p>
                  <div className="absolute -right-3 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-indigo-300 group-hover:border-indigo-500 transition-colors z-20"></div>
                </div>

                {/* Edge Connector */}
                <div className="flex-1 flex flex-col items-center justify-center relative">
                  <div
                    className={clsx(
                      'w-full h-[2px] absolute top-1/2 -z-10 transition-colors duration-300',
                      styles.line
                    )}
                  ></div>
                  <div
                    className={clsx(
                      'px-3 py-1 rounded text-[10px] font-black tracking-widest uppercase border shadow-sm flex items-center gap-1 z-10 transition-colors',
                      styles.badge
                    )}
                  >
                    {edge.type.replace('_', ' ')}
                  </div>
                </div>

                {/* Target Node (Evidence) */}
                <div className="w-[40%] bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-all z-10 overflow-hidden relative">
                  <div className={clsx('absolute top-0 left-0 w-1.5 h-full transition-colors', styles.bar)} />
                  <div className="absolute -left-3 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-slate-300 z-20"></div>

                  <div className="pl-3">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                      <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">
                        Evidence Source
                      </span>
                    </div>
                    <p className="text-sm font-bold text-slate-900 line-clamp-2 mb-1.5 leading-snug">
                      {edge.evidence.title || 'Corpus Source'}
                    </p>
                    {edge.evidence.publisher && (
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                        {edge.evidence.publisher}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
