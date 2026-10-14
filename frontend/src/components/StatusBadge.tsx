import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const s = status.toUpperCase();
  let colorStyles = 'bg-zinc-800 text-zinc-300 border-zinc-700';

  if (['PASS', 'COMPLETED', 'ACCEPTED', 'APPROVED'].includes(s)) {
    colorStyles = 'bg-emerald-950/60 text-emerald-400 border-emerald-800/60';
  } else if (['FAIL', 'FAILED', 'REJECTED'].includes(s)) {
    colorStyles = 'bg-rose-950/60 text-rose-400 border-rose-800/60';
  } else if (['AWAITING_APPROVAL', 'REPAIR_REQUIRED', 'NEEDS_HUMAN_REVIEW', 'BLOCKED'].includes(s)) {
    colorStyles = 'bg-amber-950/60 text-amber-400 border-amber-800/60';
  } else if (['CODING', 'PLANNING', 'BASELINE_VALIDATION', 'ACCEPTANCE_TESTS', 'REGRESSION_TESTS', 'IMPLEMENTING'].includes(s)) {
    colorStyles = 'bg-sky-950/60 text-sky-400 border-sky-800/60';
  } else if (['PROPOSED', 'REVIEWED'].includes(s)) {
    colorStyles = 'bg-indigo-950/60 text-indigo-400 border-indigo-800/60';
  } else if (s === 'REPEATED') {
    colorStyles = 'bg-purple-950/60 text-purple-400 border-purple-800/60';
  }

  const px = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span className={`inline-flex items-center font-mono font-medium rounded border ${px} ${colorStyles}`}>
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-75"></span>
      {status}
    </span>
  );
};
