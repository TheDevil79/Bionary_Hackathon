import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 text-indigo-700">
            <ShieldCheck className="w-6 h-6" />
            <span className="text-xl font-semibold tracking-tight">EvidenceLens</span>
          </div>
          <nav className="text-sm font-medium text-slate-500">
            <span className="px-3 py-1 bg-slate-100 rounded-md">Analyst Workbench</span>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        {children}
      </main>
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-sm text-slate-500">
        <p>EvidenceLens &copy; 2026. Internal use only.</p>
      </footer>
    </div>
  );
}
