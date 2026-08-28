import { EvidenceItem } from '../api/types';
import { BookOpen, Calendar, ArrowUpRight, TrendingUp, Link2 } from 'lucide-react';
import { clsx } from 'clsx';

export default function EvidencePanel({ evidence }: { evidence: (EvidenceItem & { relationship: 'SUPPORTS' | 'CONTRADICTS' })[] }) {
  if (!evidence || evidence.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center gap-3">
        <BookOpen className="w-5 h-5 text-indigo-600" />
        <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">Source Evidence Archive</h2>
      </div>
      <div className="p-6 md:p-8 grid grid-cols-1 gap-8 bg-[#FAFAFA]">
        {evidence.map((item, idx) => (
          <div key={`${item.id}-${idx}`} className="bg-white ring-1 ring-slate-200 rounded-xl p-6 md:p-8 relative overflow-hidden flex flex-col gap-5 shadow-sm hover:shadow-md transition-all group">
            {/* Semantic Relationship Tab */}
            <div className={clsx(
              "absolute top-0 left-0 w-1.5 h-full",
              item.relationship === 'SUPPORTS' ? 'bg-emerald-500' : 'bg-rose-500'
            )} />
            
            {/* Metadata Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 pl-2 border-b border-slate-100 pb-4">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200 shadow-sm">{item.publisher}</span>
                <span className="text-slate-300">|</span>
                <span className="text-slate-500 flex items-center gap-1.5 font-mono text-xs"><Calendar className="w-3.5 h-3.5" /> {item.publication_date}</span>
                <span className="text-slate-300">|</span>
                <span className="text-slate-500 font-bold uppercase text-[10px] tracking-widest">{item.source_type}</span>
              </div>
              <div className={clsx(
                "px-3 py-1 rounded text-[10px] font-black uppercase tracking-widest ring-1 ring-inset shadow-sm",
                item.relationship === 'SUPPORTS' ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/30' : 
                'bg-rose-50 text-rose-700 ring-rose-600/30'
              )}>
                {item.relationship}
              </div>
            </div>

            {/* Content */}
            <div className="pl-2 flex flex-col gap-4">
              <h3 className="font-extrabold text-slate-900 text-xl md:text-2xl leading-tight group-hover:text-indigo-700 transition-colors">
                {item.title}
              </h3>

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-5 text-slate-700 text-base leading-relaxed relative shadow-inner">
                <p className="font-serif italic text-slate-600">"{item.excerpt}"</p>
              </div>
            </div>

            {/* Footer Metrics */}
            <div className="flex items-center justify-between mt-2 pt-4 pl-2">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                <TrendingUp className="w-4 h-4 text-indigo-500" />
                Relevance: <span className="text-slate-900 font-black text-base">{item.relevance_score}%</span>
              </div>
              {item.url && (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-600 hover:text-indigo-800 transition-colors bg-indigo-50 px-4 py-2 rounded-md hover:bg-indigo-100 ring-1 ring-indigo-500/20 shadow-sm">
                  <Link2 className="w-4 h-4" /> Source
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-70" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
