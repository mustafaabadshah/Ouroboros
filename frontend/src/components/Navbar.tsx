import React from 'react';
import { Cpu, ShieldAlert, Sparkles, Sun, Moon, Database } from 'lucide-react';

interface NavbarProps {
  freeRamMb: number;
  ramWarning: boolean;
  autonomyMode: string;
  setAutonomyMode: (mode: string) => void;
  ollamaConnected: boolean;
  groqConnected: boolean;
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  freeRamMb,
  ramWarning,
  autonomyMode,
  setAutonomyMode,
  ollamaConnected,
  groqConnected,
  isDark,
  setIsDark,
}) => {
  return (
    <header className="h-14 border-b border-zinc-800 bg-zinc-950 px-5 flex items-center justify-between select-none shrink-0 z-20">
      {/* Brand & Subtitle */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded border border-zinc-700 bg-zinc-900 flex items-center justify-center font-mono font-bold text-sm text-zinc-100 shadow-sm">
          Ω
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm tracking-wide text-zinc-100">PROJECT OUROBOROS</span>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded border border-zinc-800 bg-zinc-900 text-zinc-400">
              v0.1.0-DEV
            </span>
          </div>
          <p className="text-[11px] text-zinc-500 font-sans hidden sm:block">
            Hierarchical Software Evolution & Deterministic Repair Engine
          </p>
        </div>
      </div>

      {/* Control Badges & Actions */}
      <div className="flex items-center gap-3">
        {/* Autonomy Mode Selector */}
        <div className="hidden md:flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-xs font-mono">
          <span className="text-zinc-500">Mode:</span>
          <select
            value={autonomyMode}
            onChange={(e) => setAutonomyMode(e.target.value)}
            className="bg-transparent text-zinc-200 outline-none cursor-pointer font-medium"
          >
            <option value="OBSERVE" className="bg-zinc-900">Observe Only</option>
            <option value="SUPERVISED" className="bg-zinc-900">Supervised (Default)</option>
            <option value="BOUNDED_AUTONOMOUS" className="bg-zinc-900">Bounded Autonomous</option>
          </select>
        </div>

        {/* RAM Watchdog Guardrail */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-mono ${
            ramWarning
              ? 'bg-rose-950/60 border-rose-800 text-rose-300 animate-pulse'
              : 'bg-zinc-900 border-zinc-800 text-zinc-400'
          }`}
          title={ramWarning ? 'RAM under 1500MB safety threshold! Concurrency locked.' : 'System memory within safe bounds.'}
        >
          {ramWarning ? <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> : <Cpu className="w-3.5 h-3.5 text-zinc-400" />}
          <span>RAM: {freeRamMb} MB</span>
        </div>

        {/* Provider Indicators */}
        <div className="hidden lg:flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border ${
              ollamaConnected
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${ollamaConnected ? 'bg-emerald-400' : 'bg-zinc-600'}`}></span>
            Ollama CPU
          </span>

          <span
            className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border ${
              groqConnected
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${groqConnected ? 'bg-emerald-400' : 'bg-zinc-600'}`}></span>
            Groq API
          </span>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={() => setIsDark(!isDark)}
          className="p-1.5 rounded border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition"
          title="Toggle Dark / Light theme"
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
