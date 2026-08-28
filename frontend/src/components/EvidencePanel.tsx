import { EvidenceItem } from '../api/types';
import { BookOpen, Calendar, ArrowUpRight, TrendingUp, Link2, Building2, Globe2, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';

export default function EvidencePanel({ evidence }: { evidence: EvidenceItem[] }) {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 p-8 text-center">
        <BookOpen className="w-8 h-8 text-slate-300 mx-auto mb-3" />
        <h3 className="text-base font-bold text-slate-700 mb-1">No Direct Evidence Retrieved</h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          No corroborating documents met the strict relevance and reliability thresholds for this claim.
        </p>
      </div>
    );
  }

  const formatRelevance = (score: number) => {
    if (score == null) return '0%';
    const pct = score <= 1.0 ? score * 100 : score;
    return `${Math.round(pct)}%`;
  };

  const getRelationshipStyles = (rel: string) => {
    switch (rel) {
      case 'SUPPORTS':
        return {
          bar: 'bg-emerald-500',
          badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/30',
          label: 'SUPPORTS',
        };
      case 'CONTRADICTS':
        return {
          bar: 'bg-rose-500',
          badge: 'bg-rose-50 text-rose-700 ring-rose-600/30',
          label: 'CONTRADICTS',
        };
      case 'CONTEXT_MISMATCH':
      default:
        return {
          bar: 'bg-amber-500',
          badge: 'bg-amber-50 text-amber-700 ring-amber-600/30',
          label: rel.replace('_', ' '),
        };
    }
  };

  const isWebSource = (url?: string | null) => {
    if (!url) return false;
    return url.startsWith('http://') || url.startsWith('https://');
  };

  return (
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-indigo-600" />
          <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">
            Retrieved Evidence Corpus ({evidence.length})
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded font-bold">
            <Globe2 className="w-3 h-3" /> Live Web Grounding + pgvector
          </span>
        </div>
      </div>
      <div className="p-6 md:p-8 grid grid-cols-1 gap-6 bg-[#FAFAFA]">
        {evidence.map((item, idx) => {
          const styles = getRelationshipStyles(item.relationship);
          const isWeb = isWebSource(item.url);

          return (
            <div
              key={`${item.id}-${idx}`}
              className="bg-white ring-1 ring-slate-200 rounded-xl p-6 md:p-8 relative overflow-hidden flex flex-col gap-5 shadow-sm hover:shadow-md transition-all group"
            >
              {/* Semantic Relationship Indicator Bar */}
              <div className={clsx('absolute top-0 left-0 w-1.5 h-full', styles.bar)} />

              {/* Metadata Header */}
              <div className="flex flex-wrap items-center justify-between gap-4 pl-2 border-b border-slate-100 pb-4">
                <div className="flex flex-wrap items-center gap-2.5 text-sm">
                  {/* Origin Badge: WEB vs LOCAL */}
                  {isWeb ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold uppercase tracking-wider text-sky-700 bg-sky-50 border border-sky-200 px-2 py-0.5 rounded">
                      <Globe2 className="w-3 h-3" /> Web Source
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                      <ShieldCheck className="w-3 h-3" /> Verified Corpus
                    </span>
                  )}

                  {item.publisher && (
                    <span className="font-bold text-slate-800 bg-slate-100 px-2.5 py-0.5 rounded border border-slate-200 shadow-sm flex items-center gap-1.5 text-xs">
                      <Building2 className="w-3.5 h-3.5 text-slate-500" />
                      {item.publisher}
                    </span>
                  )}
                  {item.published_at && (
                    <>
                      <span className="text-slate-300">|</span>
                      <span className="text-slate-500 flex items-center gap-1.5 font-mono text-xs">
                        <Calendar className="w-3.5 h-3.5" /> {item.published_at}
                      </span>
                    </>
                  )}
                </div>
                <div
                  className={clsx(
                    'px-3 py-1 rounded text-[10px] font-black uppercase tracking-widest ring-1 ring-inset shadow-sm',
                    styles.badge
                  )}
                >
                  {styles.label}
                </div>
              </div>

              {/* Content */}
              <div className="pl-2 flex flex-col gap-3">
                <h3 className="font-extrabold text-slate-900 text-xl md:text-2xl leading-tight group-hover:text-indigo-700 transition-colors">
                  {item.title}
                </h3>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-5 text-slate-700 text-base leading-relaxed relative shadow-inner">
                  <p className="font-serif italic text-slate-700">"{item.excerpt}"</p>
                </div>
              </div>

              {/* Footer Metrics */}
              <div className="flex items-center justify-between mt-2 pt-4 pl-2">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                  <TrendingUp className="w-4 h-4 text-indigo-500" />
                  Relevance: <span className="text-slate-900 font-black text-base">{formatRelevance(item.relevance_score)}</span>
                </div>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-600 hover:text-indigo-800 transition-colors bg-indigo-50 px-4 py-2 rounded-md hover:bg-indigo-100 ring-1 ring-indigo-500/20 shadow-sm"
                  >
                    <Link2 className="w-4 h-4" /> Source Link
                    <ArrowUpRight className="w-3.5 h-3.5 opacity-70" />
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
