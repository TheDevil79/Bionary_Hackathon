import React, { useState } from 'react';
import { submitFeedback } from '../api/verification';
import { Check, Edit3, Send } from 'lucide-react';

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
      <div className="bg-green-50 border border-green-200 rounded-2xl p-6 flex items-center justify-center gap-3">
        <Check className="w-6 h-6 text-green-600" />
        <span className="font-semibold text-green-800">Review submitted successfully.</span>
      </div>
    );
  }

  return (
    <div className="bg-slate-800 text-white rounded-2xl shadow-sm border border-slate-700 overflow-hidden">
      <div className="border-b border-slate-700 bg-slate-900 px-6 py-4 flex items-center gap-2">
        <Edit3 className="w-5 h-5 text-slate-400" />
        <h2 className="text-lg font-semibold text-slate-100">Analyst Review</h2>
      </div>
      <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <label className="font-medium text-slate-200">Is the system's overall verdict correct?</label>
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => setIsCorrect(true)}
              className={`px-6 py-2 rounded-lg font-medium transition-colors border ${
                isCorrect === true 
                  ? 'bg-green-600 border-green-500 text-white' 
                  : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
              }`}
            >
              Yes, Accurate
            </button>
            <button
              type="button"
              onClick={() => setIsCorrect(false)}
              className={`px-6 py-2 rounded-lg font-medium transition-colors border ${
                isCorrect === false 
                  ? 'bg-red-600 border-red-500 text-white' 
                  : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
              }`}
            >
              No, Requires Correction
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="correctionNote" className="font-medium text-slate-200">
            Correction Notes / Justification
          </label>
          <textarea
            id="correctionNote"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-xl border border-slate-600 bg-slate-700 p-4 text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all placeholder-slate-400"
            placeholder="Add analyst notes or correction justification here..."
          />
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={isCorrect === null || isSubmitting}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting ? 'Submitting...' : (
              <>
                <Send className="w-4 h-4" /> Submit Review
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
