import { clsx } from 'clsx';
import { CheckCircle2, XCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import { Verdict } from '../api/types';

interface VerdictBadgeProps {
  verdict: Verdict;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export default function VerdictBadge({ verdict, size = 'md', showIcon = true }: VerdictBadgeProps) {
  const config: Record<string, { icon: typeof CheckCircle2; colors: string }> = {
    'SUPPORTED': { icon: CheckCircle2, colors: 'bg-emerald-500 text-white shadow-emerald-500/30' },
    'CONTRADICTED': { icon: XCircle, colors: 'bg-rose-500 text-white shadow-rose-500/30' },
    'MIXED': { icon: AlertTriangle, colors: 'bg-amber-500 text-white shadow-amber-500/30' },
    'INSUFFICIENT EVIDENCE': { icon: HelpCircle, colors: 'bg-slate-500 text-white shadow-slate-500/30' },
    'INSUFFICIENT_EVIDENCE': { icon: HelpCircle, colors: 'bg-slate-500 text-white shadow-slate-500/30' },
    'INSUFFICIENT': { icon: HelpCircle, colors: 'bg-slate-500 text-white shadow-slate-500/30' },
  };

  const { icon: Icon, colors } = config[verdict] || config['INSUFFICIENT'];
  
  const sizeClasses = {
    sm: 'px-2.5 py-1 text-[10px] uppercase tracking-widest',
    md: 'px-3 py-1.5 text-xs uppercase tracking-widest',
    lg: 'px-5 py-2.5 text-sm uppercase tracking-widest',
  };

  return (
    <div className={clsx('inline-flex items-center gap-2 rounded-md font-black shadow-lg', colors, sizeClasses[size])}>
      {showIcon && <Icon className={clsx(size === 'lg' ? 'w-5 h-5' : 'w-4 h-4', 'opacity-90')} />}
      <span>{verdict === 'INSUFFICIENT' ? 'INSUFFICIENT EVIDENCE' : verdict}</span>
    </div>
  );
}
