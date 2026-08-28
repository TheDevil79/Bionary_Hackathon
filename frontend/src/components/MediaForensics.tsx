import { MediaAnalysis } from '../api/types';
import { Image as ImageIcon, AlertTriangle, Calendar, FileSearch, ScanLine, Info } from 'lucide-react';

export default function MediaForensics({ analysis }: { analysis: MediaAnalysis | null }) {
  if (!analysis) return null;

  return (
    <div className="bg-white rounded-xl shadow-lg shadow-slate-200/40 ring-1 ring-slate-900/5 overflow-hidden">
      <div className="border-b border-slate-200/80 bg-slate-50 px-6 py-4 flex items-center gap-3">
        <ScanLine className="w-5 h-5 text-indigo-600" />
        <h2 className="text-sm font-bold text-slate-900 tracking-widest uppercase">Media Forensics</h2>
      </div>
      <div className="p-6 md:p-8 bg-[#FAFAFA]">
        <div className="flex flex-col lg:flex-row gap-8">
          
          {/* Forensic Image Preview */}
          <div className="w-full lg:w-1/3 bg-slate-900 border border-slate-800 rounded-xl aspect-video flex items-center justify-center relative overflow-hidden group shadow-inner">
             {/* Tech Grid */}
             <div className="absolute inset-0 z-0 opacity-20" style={{ backgroundImage: 'linear-gradient(#334155 1px, transparent 1px), linear-gradient(90deg, #334155 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
             
             {/* Scanning Line */}
             <div className="absolute top-0 left-0 w-full h-1 bg-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.8)] animate-[scan_4s_ease-in-out_infinite] z-10"></div>
             
             <div className="text-slate-500 flex flex-col items-center gap-3 relative z-10 transition-transform group-hover:scale-105 duration-700">
               <ImageIcon className="w-12 h-12 opacity-80 text-indigo-400" />
               <span className="text-[10px] font-mono font-bold tracking-widest uppercase text-indigo-300/80 bg-slate-900/80 px-2 py-1 rounded">Subject_Media.bin</span>
             </div>

             <div className="absolute bottom-2 left-2 flex items-center gap-1.5 text-[9px] font-mono text-slate-500 uppercase tracking-widest bg-slate-900/80 px-2 py-0.5 rounded">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                Scanned
             </div>
          </div>
          
          {/* Forensic Data Points */}
          <div className="w-full lg:w-2/3 flex flex-col gap-4 justify-center">
            
            {analysis.similarity_score !== undefined && (
              <div className="flex items-center justify-between p-5 bg-white border border-slate-200 rounded-xl shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-50 text-indigo-600 rounded">
                    <FileSearch className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="block text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">Database Query</span>
                    <span className="font-black text-slate-800 tracking-tight text-lg">Image Match Found</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-4xl font-black text-indigo-600 tracking-tighter">{analysis.similarity_score}%</span>
                  <span className="block text-[10px] font-bold uppercase tracking-widest text-slate-400">similarity</span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {analysis.previous_occurrence_date && (
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm flex flex-col gap-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Calendar className="w-3 h-3" /> Previous Appearance
                  </span>
                  <div className="font-mono font-bold text-lg text-slate-800">
                    {analysis.previous_occurrence_date}
                  </div>
                </div>
              )}
              {analysis.metadata?.location && (
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm flex flex-col gap-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Info className="w-3 h-3" /> Original Location
                  </span>
                  <div className="font-bold text-lg text-slate-800">
                    {analysis.metadata.location}
                  </div>
                </div>
              )}
            </div>

            {analysis.possible_context_mismatch && (
              <div className="mt-2 bg-amber-50 border border-amber-200 p-5 rounded-xl flex items-start gap-4 shadow-sm">
                <div className="p-2 bg-white rounded-lg shadow-sm text-amber-600 flex-shrink-0 border border-amber-100">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-black text-amber-900 uppercase tracking-widest mb-1.5">Possible Context Mismatch</h4>
                  <p className="text-sm font-medium text-amber-800 leading-relaxed">{analysis.possible_context_mismatch}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
