import { MediaAnalysis } from '../api/types';
import { Image as ImageIcon, AlertTriangle, Calendar, FileSearch } from 'lucide-react';

export default function MediaForensics({ analysis }: { analysis: MediaAnalysis | null }) {
  if (!analysis) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 flex items-center gap-2">
        <ImageIcon className="w-5 h-5 text-slate-500" />
        <h2 className="text-lg font-semibold text-slate-800">Media Forensics</h2>
      </div>
      <div className="p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="w-full lg:w-1/3 bg-slate-100 border border-slate-200 rounded-xl aspect-video flex items-center justify-center relative overflow-hidden">
             {/* Placeholder for uploaded image */}
             <div className="text-slate-400 flex flex-col items-center gap-2">
               <ImageIcon className="w-10 h-10 opacity-50" />
               <span className="text-sm font-medium">Analyzed Media</span>
             </div>
          </div>
          <div className="w-full lg:w-2/3 flex flex-col gap-4 justify-center">
            
            {analysis.similarity_score !== undefined && (
              <div className="flex items-center justify-between p-4 bg-indigo-50 border border-indigo-100 rounded-xl">
                <div className="flex items-center gap-3">
                  <FileSearch className="w-6 h-6 text-indigo-600" />
                  <span className="font-semibold text-indigo-900">Image Match Found</span>
                </div>
                <span className="text-2xl font-bold text-indigo-700">{analysis.similarity_score}% <span className="text-sm font-medium text-indigo-500">similarity</span></span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {analysis.previous_occurrence_date && (
                <div className="border border-slate-200 p-4 rounded-xl flex flex-col gap-1">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Previous Appearance</span>
                  <div className="flex items-center gap-2 text-slate-800 font-medium">
                    <Calendar className="w-4 h-4 text-slate-500" />
                    {analysis.previous_occurrence_date}
                  </div>
                </div>
              )}
              {analysis.metadata?.location && (
                <div className="border border-slate-200 p-4 rounded-xl flex flex-col gap-1">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Original Location</span>
                  <div className="text-slate-800 font-medium">
                    {analysis.metadata.location}
                  </div>
                </div>
              )}
            </div>

            {analysis.possible_context_mismatch && (
              <div className="mt-2 bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-bold text-amber-800 mb-1">Possible Context Mismatch</h4>
                  <p className="text-sm text-amber-700">{analysis.possible_context_mismatch}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
