import { EvidenceItem } from '../api/types';
import { BookOpen, Calendar, Link2, TrendingUp } from 'lucide-react';
import { clsx } from 'clsx';

export default function EvidencePanel({ evidence }: { evidence: (EvidenceItem & { relationship: 'SUPPORTS' | 'CONTRADICTS' })[] }) {
  if (!evidence || evidence.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-slate-500" />
        <h2 className="text-lg font-semibold text-slate-800">Source Evidence</h2>
      </div>
      <div className="p-6 grid grid-cols-1 gap-6">
        {evidence.map((item, idx) => (
          <div key={`${item.id}-${idx}`} className="border border-slate-200 rounded-xl p-5 relative overflow-hidden flex flex-col gap-3">
            <div className={clsx(
              "absolute top-0 left-0 w-1 h-full",
              item.relationship === 'SUPPORTS' ? 'bg-green-500' : 'bg-red-500'
            )} />
            
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-bold text-slate-900 bg-slate-100 px-2 py-1 rounded">{item.publisher}</span>
                <span className="text-slate-400">•</span>
                <span className="text-slate-600 flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> {item.publication_date}</span>
                <span className="text-slate-400">•</span>
                <span className="text-slate-500 italic">{item.source_type}</span>
              </div>
              <div className={clsx(
                "px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wide",
                item.relationship === 'SUPPORTS' ? 'bg-green-50 text-green-700 border border-green-200' : 
                'bg-red-50 text-red-700 border border-red-200'
              )}>
                {item.relationship}
              </div>
            </div>

            <h3 className="font-semibold text-slate-900 text-lg leading-tight mt-1">
              {item.title}
            </h3>

            <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 text-slate-700 text-sm leading-relaxed border-l-4 border-l-slate-300 italic">
              "{item.excerpt}"
            </div>

            <div className="flex items-center justify-between mt-2 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-1.5 text-sm font-medium text-slate-500">
                <TrendingUp className="w-4 h-4 text-indigo-500" />
                Relevance: <span className="text-slate-900">{item.relevance_score}%</span>
              </div>
              {item.url && (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 transition-colors">
                  <Link2 className="w-4 h-4" /> View Source
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
