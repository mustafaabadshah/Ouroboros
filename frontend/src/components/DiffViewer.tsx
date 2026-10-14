import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface DiffViewerProps {
  diffText: string;
  maxHeight?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ diffText, maxHeight = 'max-h-[500px]' }) => {
  const [copied, setCopied] = useState(false);

  if (!diffText || !diffText.trim()) {
    return (
      <div className="p-6 text-center text-zinc-500 font-mono text-sm border border-zinc-800 rounded bg-zinc-950/50">
        No candidate diff available.
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(diffText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = diffText.split('\n');

  return (
    <div className="relative border border-zinc-800 rounded bg-zinc-950 font-mono text-xs overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/70 text-zinc-400">
        <span className="font-semibold text-zinc-300">Unified Patch Diff</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy Diff'}
        </button>
      </div>

      <div className={`overflow-auto p-3 font-mono leading-relaxed select-text ${maxHeight}`}>
        {lines.map((line, idx) => {
          let lineBg = 'hover:bg-zinc-900/60 text-zinc-400';
          if (line.startsWith('+++') || line.startsWith('---')) {
            lineBg = 'text-zinc-500 font-bold bg-zinc-900/40';
          } else if (line.startsWith('@@')) {
            lineBg = 'text-cyan-400 bg-cyan-950/20';
          } else if (line.startsWith('+')) {
            lineBg = 'text-emerald-400 bg-emerald-950/30';
          } else if (line.startsWith('-')) {
            lineBg = 'text-rose-400 bg-rose-950/30';
          }

          return (
            <div key={idx} className={`flex py-0.5 px-1 rounded-sm ${lineBg}`}>
              <span className="w-10 text-right pr-3 select-none text-zinc-600 shrink-0">{idx + 1}</span>
              <span className="whitespace-pre">{line}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
