import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, AlertCircle, Loader2, FileVideo, Image as ImageIcon, ScanText, Crosshair } from 'lucide-react';
import { verify } from '../api/verification';

const LOADING_STATES = [
  "Extracting claims from input...",
  "Searching evidence database...",
  "Analyzing media forensics...",
  "Building verification graph..."
];

export default function LandingPage() {
  const [claimText, setClaimText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  const [status, setStatus] = useState<'IDLE' | 'SUBMITTING' | 'SUCCESS' | 'ERROR'>('IDLE');
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  
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
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
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
      const result = await verify({ text: claimText, file: file || undefined });
      setStatus('SUCCESS');
      navigate('/results', { state: { result } });
    } catch (err: any) {
      setError(err?.message || 'Failed to connect to the verification server. Please try again.');
      setStatus('ERROR');
    }
  };

  const isImage = file?.type.startsWith('image/');
  const isVideo = file?.type.startsWith('video/');

  return (
    <div className="max-w-5xl mx-auto mt-4">
      {/* Sophisticated Hero Section */}
      <div className="text-center mb-12 space-y-5">
        <h1 className="text-5xl md:text-6xl font-black text-slate-900 tracking-tighter">
          Verify Claims with{' '}
          <span className="relative inline-block">
            <span className="relative z-10 text-indigo-700 bg-clip-text bg-gradient-to-b from-indigo-600 to-indigo-900 text-transparent">Confidence</span>
            <span className="absolute bottom-1.5 left-0 w-full h-3 bg-indigo-200/60 -z-10 skew-x-12"></span>
          </span>
        </h1>
        <p className="text-lg text-slate-500 max-w-2xl mx-auto font-medium leading-relaxed">
          Upload a social media post, text claim, or media file. EvidenceLens will analyze provenance, detect manipulation, and source corroborating evidence.
        </p>
      </div>

      {/* Verification Workspace */}
      <div className="bg-white rounded-xl shadow-2xl shadow-slate-200/50 ring-1 ring-slate-200 overflow-hidden flex flex-col">
        {/* Workspace Header */}
        <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScanText className="w-5 h-5 text-slate-400" />
            <span className="text-xs font-bold uppercase tracking-widest text-slate-500">New Investigation</span>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>SYS.RDY</span>
            <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col">
          
          {error && status === 'ERROR' && (
            <div className="bg-rose-50 border-b border-rose-100 p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
              <p className="text-sm font-semibold text-rose-800">{error}</p>
            </div>
          )}

          {/* Split Content Area */}
          <div className="flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-slate-100">
            
            {/* Left: Claim Input */}
            <div className="flex-1 p-8 flex flex-col group relative">
              <label htmlFor="claimText" className="flex items-center justify-between mb-4">
                <span className="text-xs font-black uppercase tracking-widest text-slate-800 flex items-center gap-2">
                  <span className="text-indigo-600 font-mono">01.</span> Claim Text
                </span>
                <span className="text-[10px] font-mono text-slate-400 opacity-0 group-focus-within:opacity-100 transition-opacity">Press Cmd+Enter</span>
              </label>
              <textarea
                id="claimText"
                value={claimText}
                onChange={(e) => setClaimText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    handleSubmit(e);
                  }
                }}
                className="flex-1 w-full min-h-[200px] text-lg text-slate-800 placeholder:text-slate-300 bg-transparent resize-none outline-none leading-relaxed transition-all"
                placeholder="Paste the statement, article excerpt, or social media post here..."
                disabled={status === 'SUBMITTING'}
              />
              <div className="absolute left-0 bottom-0 w-1 h-0 bg-indigo-500 transition-all duration-300 group-focus-within:h-full"></div>
            </div>

            {/* Right: Media Upload */}
            <div className="flex-1 p-8 bg-slate-50/30 flex flex-col">
              <span className="text-xs font-black uppercase tracking-widest text-slate-800 flex items-center gap-2 mb-4">
                <span className="text-indigo-600 font-mono">02.</span> Image / Video Attachment <span className="text-slate-400 font-normal ml-1">(Optional)</span>
              </span>
              
              <div 
                className={`flex-1 relative border-2 border-dashed rounded-lg flex flex-col items-center justify-center text-center transition-all duration-200 min-h-[200px] ${
                  status === 'SUBMITTING' ? 'opacity-50 cursor-not-allowed bg-slate-100 border-slate-200' :
                  isDragging ? 'border-indigo-400 bg-indigo-50/50 scale-[1.02]' :
                  file ? 'border-slate-300 bg-white cursor-pointer hover:border-indigo-400 shadow-sm' : 
                  'border-slate-200 bg-slate-50 cursor-pointer hover:bg-slate-100 hover:border-slate-300'
                }`}
                onClick={() => status !== 'SUBMITTING' && fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
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
                  <div className="flex flex-col items-center gap-3 animate-in zoom-in-95 duration-300">
                    <div className="text-indigo-600">
                      {isVideo ? <FileVideo className="w-10 h-10" /> : isImage ? <ImageIcon className="w-10 h-10" /> : <Upload className="w-10 h-10" />}
                    </div>
                    <div className="flex flex-col items-center px-4">
                      <span className="font-bold text-slate-800 break-all line-clamp-1">{file.name}</span>
                      <span className="text-xs text-slate-500 font-medium mt-1 font-mono bg-slate-100 px-2 py-0.5 rounded">Change File</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-slate-400 flex flex-col items-center gap-3 px-6">
                    <div className="p-3 bg-white rounded-full shadow-sm ring-1 ring-slate-900/5 group-hover:text-indigo-500 transition-colors">
                      <Upload className="w-6 h-6" />
                    </div>
                    <div className="flex flex-col items-center gap-1.5">
                      <span className="font-semibold text-slate-700 text-sm">Drop image/video or click to browse</span>
                      <span className="text-[10px] font-mono text-slate-400 tracking-widest uppercase">JPG, PNG, MP4, WEBM (Max 50MB)</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Bottom Action Bar */}
          <div className="bg-slate-900 p-6 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-slate-400 text-xs font-mono hidden md:block">
              {status === 'SUBMITTING' ? 'PROCESSING_DATA...' : 'AWAITING_INPUT'}
            </div>
            <button
              type="submit"
              disabled={status === 'SUBMITTING'}
              className="w-full md:w-auto px-10 py-4 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.98] text-white font-bold tracking-wide rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-80 disabled:cursor-not-allowed disabled:active:scale-100 flex items-center justify-center gap-3 shadow-lg shadow-indigo-900/50"
            >
              {status === 'SUBMITTING' ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin text-indigo-200" />
                  <span>{LOADING_STATES[loadingIndex]}</span>
                </>
              ) : (
                <>
                  <Crosshair className="w-5 h-5 text-indigo-200" />
                  <span>Execute Verification</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
