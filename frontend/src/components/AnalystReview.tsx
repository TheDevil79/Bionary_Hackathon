import React, { useState } from 'react';
import { submitFeedback } from '../api/verification';
import { Check, Edit3, Send, ShieldAlert, Cpu } from 'lucide-react';

export default function AnalystReview({ verificationId }: { verificationId: string }) {
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [note, setNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isCorrect === null) return;
    
    setIsSubmitting(true);
    try {
      await submitFeedback({
        verification_id: verificationId,
        is_correct: isCorrect,
        correction_note: note
      });
      setSubmitted(true);
    } catch (err) {
      console.error(err);
      alert('Failed to submit feedback');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 flex items-center justify-center gap-4 shadow-xl">
        <div className="p-3 bg-emerald-500/20 rounded-xl border border-emerald-500/30 text-emerald-400">
          <Check className="w-6 h-6" />
        </div>
        <span className="font-bold text-white text-lg tracking-tight">Review recorded in system log.</span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 text-white rounded-xl shadow-xl shadow-slate-900/20 border border-slate-800 overflow-hidden relative font-sans">
      {/* Decorative dark tech background */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-500/5 rounded-full blur-3xl -mr-40 -mt-40 pointer-events-none"></div>
      
      <div className="border-b border-slate-800/80 bg-slate-900/50 px-8 py-5 flex items-center justify-between relative z-10">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-slate-800 rounded border border-slate-700">
            <Edit3 className="w-4 h-4 text-indigo-400" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 tracking-widest uppercase">Analyst Override</h2>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
          <Cpu className="w-3.5 h-3.5" />
          MANUAL_INPUT_REQ
        </div>
      </div>
      
      <form onSubmit={handleSubmit} className="p-8 flex flex-col gap-8 relative z-10">
        <div className="flex flex-col gap-4">
          <label className="font-bold text-slate-300 tracking-wide flex items-center gap-2 text-sm uppercase">
            <ShieldAlert className="w-4 h-4 text-slate-500" />
            Validate System Verdict
          </label>
          <div className="flex flex-wrap gap-4">
            <button
              type="button"
              onClick={() => setIsCorrect(true)}
              className={`px-8 py-4 rounded-lg font-bold transition-all border text-sm uppercase tracking-widest ${
                isCorrect === true 
                  ? 'bg-emerald-600 border-emerald-500 text-white shadow-[0_0_15px_rgba(5,150,105,0.4)]' 
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
              }`}
            >
              Verify Accurate
            </button>
            <button
              type="button"
              onClick={() => setIsCorrect(false)}
              className={`px-8 py-4 rounded-lg font-bold transition-all border text-sm uppercase tracking-widest ${
                isCorrect === false 
                  ? 'bg-rose-600 border-rose-500 text-white shadow-[0_0_15px_rgba(225,29,72,0.4)]' 
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
              }`}
            >
              Flag Correction
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <label htmlFor="correctionNote" className="font-bold text-slate-300 tracking-wide text-sm uppercase">
            Analyst Justification Log
          </label>
          <textarea
            id="correctionNote"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-900/50 p-5 text-slate-200 focus:bg-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all placeholder-slate-600 font-mono text-sm resize-none shadow-inner"
            placeholder="> Enter justification for override or verification notes here..."
          />
        </div>

        <div className="flex justify-end pt-6 border-t border-slate-800/80">
          <button
            type="submit"
            disabled={isCorrect === null || isSubmitting}
            className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-bold tracking-widest uppercase text-xs rounded-lg transition-all shadow-md hover:shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting ? 'Transmitting...' : (
              <>
                <Send className="w-4 h-4" /> Record Decision
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
