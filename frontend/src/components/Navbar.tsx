import React from 'react';
import { Cpu, ShieldAlert, Sun, Moon, Radio, Activity, ExternalLink } from 'lucide-react';

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
  const ramPercent = Math.min(100, Math.max(0, Math.round(((8192 - freeRamMb) / 8192) * 100)));

  return (
    <header className="h-14 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md px-5 flex items-center justify-between select-none shrink-0 z-30 sticky top-0">
      {/* Brand & Subtitle */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg border border-emerald-500/30 bg-gradient-to-br from-emerald-500/20 to-zinc-900 flex items-center justify-center font-mono font-bold text-sm text-emerald-400 shadow-sm shadow-emerald-950/50">
          Ω
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-wider text-zinc-100 font-mono">PROJECT OUROBOROS</span>
            <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border border-emerald-500/40 bg-emerald-950/60 text-emerald-400 shadow-sm shadow-emerald-900/30">
              v1.0-RC1
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 font-sans hidden sm:block">
            Autonomous Engineering Control Room & Observability Console
          </p>
        </div>
      </div>

      {/* Control Badges & Actions */}
      <div className="flex items-center gap-3">
        {/* Autonomy Mode Selector */}
        <div className="hidden md:flex items-center gap-2 bg-zinc-900/90 border border-zinc-800 rounded-lg px-2.5 py-1 text-xs font-mono">
          <span className="text-zinc-500 flex items-center gap-1">
            <Activity className="w-3.5 h-3.5 text-indigo-400" /> Mode:
          </span>
          <select
            value={autonomyMode}
            onChange={(e) => setAutonomyMode(e.target.value)}
            className="bg-transparent text-zinc-200 outline-none cursor-pointer font-medium text-xs"
          >
            <option value="OBSERVE" className="bg-zinc-900 text-zinc-300">Observe Only</option>
            <option value="SUPERVISED" className="bg-zinc-900 text-zinc-300">Supervised (Default)</option>
            <option value="BOUNDED_AUTONOMOUS" className="bg-zinc-900 text-zinc-300">Bounded Autonomous</option>
          </select>
        </div>

        {/* Arize Phoenix Quick-Pill */}
        <a
          href={
            typeof window !== 'undefined' &&
            (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
              ? 'http://127.0.0.1:6006'
              : 'https://ouroboros-backend-i9x2.onrender.com/phoenix'
          }
          target="_blank"
          rel="noreferrer"
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-purple-800/60 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 text-xs font-mono transition"
          title="Arize Phoenix AI Observability & Live Telemetry Dashboard"
        >
          <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></span>
          <span>Phoenix Dashboard</span>
          <ExternalLink className="w-3 h-3 text-purple-400" />
        </a>

        {/* RAM Watchdog Guardrail Gauge */}
        <div
          className={`flex items-center gap-2 px-2.5 py-1 rounded-lg border text-xs font-mono transition ${
            ramWarning
              ? 'bg-rose-950/60 border-rose-800 text-rose-300 animate-pulse'
              : 'bg-zinc-900/80 border-zinc-800 text-zinc-400'
          }`}
          title={ramWarning ? 'RAM under 1500MB safety threshold! Concurrency locked at 1.' : 'System memory within safe bounds.'}
        >
          {ramWarning ? <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> : <Cpu className="w-3.5 h-3.5 text-zinc-400" />}
          <span>{freeRamMb} MB</span>
          <div className="w-12 h-1.5 bg-zinc-800 rounded-full overflow-hidden hidden sm:block">
            <div
              className={`h-full transition-all duration-500 ${ramWarning ? 'bg-rose-500' : 'bg-emerald-500'}`}
              style={{ width: `${ramPercent}%` }}
            ></div>
          </div>
        </div>

        {/* Provider Indicators */}
        <div className="hidden lg:flex items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-md border ${
              groqConnected
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
            title="Groq Remote Reasoning Provider"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${groqConnected ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-zinc-600'}`}></span>
            Groq API
          </span>

          <span
            className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-md border ${
              ollamaConnected
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
            title="Local Ollama CPU Runtime"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${ollamaConnected ? 'bg-emerald-400' : 'bg-zinc-600'}`}></span>
            Ollama CPU
          </span>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={() => setIsDark(!isDark)}
          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition"
          title="Toggle Dark / Light theme"
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
