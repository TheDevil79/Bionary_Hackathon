import React from 'react';
import { ShieldCheck, Database } from 'lucide-react';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#F4F4F5] text-slate-900 font-sans flex flex-col selection:bg-indigo-200 selection:text-indigo-900 relative">
      {/* Subtle technical background pattern */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-20" 
           style={{ backgroundImage: 'radial-gradient(#CBD5E1 1px, transparent 1px)', backgroundSize: '24px 24px' }}></div>
      
      {/* Dark Professional Header */}
      <header className="relative z-50 bg-slate-900 border-b border-slate-800 shadow-lg text-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3 group cursor-default">
            <div className="bg-indigo-500/20 p-1.5 rounded-md border border-indigo-500/30 group-hover:bg-indigo-500/30 transition-colors">
              <ShieldCheck className="w-5 h-5 text-indigo-400" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white">
              Evidence<span className="text-indigo-400 font-light">Lens</span>
            </span>
          </div>
          <nav className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-800/50 px-3 py-1.5 rounded border border-slate-700">
              <Database className="w-3.5 h-3.5" />
              <span>LIVE</span>
            </div>
            <span className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-[10px] font-bold tracking-widest uppercase rounded shadow-sm">
              Analyst Workbench
            </span>
          </nav>
        </div>
      </header>

      <main className="flex-1 relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 w-full animate-in fade-in duration-700">
        {children}
      </main>

      <footer className="relative z-10 border-t border-slate-200/60 bg-white/50 backdrop-blur-sm py-6 text-center">
        <p className="text-xs font-mono text-slate-400 uppercase tracking-widest">
          EvidenceLens &copy; 2026 // Provenance & Verification Engine
        </p>
      </footer>
    </div>
  );
}
