import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, AlertCircle, Loader2 } from 'lucide-react';
import { verify } from '../api/verification';

const LOADING_STATES = [
  "Extracting claims...",
  "Searching evidence...",
  "Analyzing media...",
  "Building verification..."
];

export default function LandingPage() {
  const [claimText, setClaimText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  const [status, setStatus] = useState<'IDLE' | 'SUBMITTING' | 'SUCCESS' | 'ERROR'>('IDLE');
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (status === 'SUBMITTING') {
      setLoadingIndex(0);
      interval = setInterval(() => {
        setLoadingIndex((prev) => (prev < LOADING_STATES.length - 1 ? prev + 1 : prev));
      }, 800);
    }
    return () => clearInterval(interval);
  }, [status]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!claimText.trim() && !file) {
      setError('Please provide a claim text or upload media to verify.');
      return;
    }

    setStatus('SUBMITTING');
    setError(null);

    try {
      // For now, if a file is attached, pass a dummy media_id since the API expects an ID.
      // In reality, this would first POST to an upload endpoint and return the media_id.
      const media_id = file ? 'uploaded_media_123' : undefined;
      
      const result = await verify({
        text: claimText,
        media_id
      });
      
      setStatus('SUCCESS');
      navigate('/results', { state: { result } });
    } catch (err) {
      setError('Failed to connect to the verification server. Please try again.');
      setStatus('ERROR');
    }
  };

  return (
    <div className="max-w-3xl mx-auto mt-10">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight mb-4">
          Verify Claims with Confidence
        </h1>
        <p className="text-lg text-slate-600">
          Upload a social media post, text claim, or media file. EvidenceLens will analyze provenance, detect manipulation, and source supporting or contradicting evidence.
        </p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <form onSubmit={handleSubmit} className="p-8 flex flex-col gap-6">
          
          {error && status === 'ERROR' && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="claimText" className="text-sm font-semibold text-slate-700">
              Claim Text or Post Content
            </label>
            <textarea
              id="claimText"
              rows={4}
              value={claimText}
              onChange={(e) => setClaimText(e.target.value)}
              className="w-full rounded-xl border border-slate-300 p-4 text-slate-900 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all resize-none"
              placeholder="Paste the claim, tweet, or social media post here..."
              disabled={status === 'SUBMITTING'}
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-slate-700">Media Attachment (Optional)</span>
            
            <div 
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors ${
                status === 'SUBMITTING' ? 'opacity-50 cursor-not-allowed bg-slate-50 border-slate-200' :
                file ? 'border-indigo-500 bg-indigo-50 cursor-pointer' : 'border-slate-300 bg-slate-50 hover:bg-slate-100 cursor-pointer'
              }`}
              onClick={() => status !== 'SUBMITTING' && fileInputRef.current?.click()}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                className="hidden" 
                accept="image/*,video/*" 
                disabled={status === 'SUBMITTING'}
              />
              
              {file ? (
                <div className="text-indigo-700 font-medium flex flex-col items-center gap-2">
                  <div className="p-3 bg-white rounded-full shadow-sm">
                    <Upload className="w-6 h-6" />
                  </div>
                  <span>{file.name}</span>
                  <span className="text-xs text-indigo-500">Click or drag to replace</span>
                </div>
              ) : (
                <div className="text-slate-500 flex flex-col items-center gap-2">
                  <div className="p-3 bg-white rounded-full shadow-sm border border-slate-200">
                    <Upload className="w-6 h-6 text-slate-400" />
                  </div>
                  <span className="font-medium text-slate-700">Click to upload or drag and drop</span>
                  <span className="text-xs">Supports JPG, PNG, MP4 (Max 50MB)</span>
                </div>
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex justify-end">
            <button
              type="submit"
              disabled={status === 'SUBMITTING'}
              className="px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-colors focus:ring-4 focus:ring-indigo-200 disabled:opacity-80 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {status === 'SUBMITTING' ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>{LOADING_STATES[loadingIndex]}</span>
                </>
              ) : (
                'Start Verification'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
