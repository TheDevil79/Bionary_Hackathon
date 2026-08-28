import { clsx } from 'clsx';
import { CheckCircle, XCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import { Verdict } from '../api/types';

interface VerdictBadgeProps {
  verdict: Verdict;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export default function VerdictBadge({ verdict, size = 'md', showIcon = true }: VerdictBadgeProps) {
  const config = {
    'SUPPORTED': { icon: CheckCircle, colors: 'bg-green-100 text-green-800 border-green-200' },
    'CONTRADICTED': { icon: XCircle, colors: 'bg-red-100 text-red-800 border-red-200' },
    'MIXED': { icon: AlertTriangle, colors: 'bg-amber-100 text-amber-800 border-amber-200' },
    'INSUFFICIENT EVIDENCE': { icon: HelpCircle, colors: 'bg-slate-100 text-slate-800 border-slate-200' },
    'INSUFFICIENT': { icon: HelpCircle, colors: 'bg-slate-100 text-slate-800 border-slate-200' },
  };

  const { icon: Icon, colors } = config[verdict] || config['INSUFFICIENT'];
  
  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base font-semibold',
  };

  return (
    <div className={clsx('inline-flex items-center gap-1.5 rounded-full border', colors, sizeClasses[size])}>
      {showIcon && <Icon className={clsx(size === 'lg' ? 'w-5 h-5' : 'w-4 h-4')} />}
      <span>{verdict === 'INSUFFICIENT' ? 'INSUFFICIENT EVIDENCE' : verdict}</span>
    </div>
  );
}
