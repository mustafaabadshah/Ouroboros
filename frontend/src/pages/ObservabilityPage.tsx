import React, { useState, useEffect } from 'react';
import { Activity, Cpu, ShieldAlert, DollarSign, Clock, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { MetricsOverview } from '../types';

export const ObservabilityPage: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 4000);
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    try {
      const data = await api.getMetricsOverview();
      setMetrics(data);
    } catch (e) {
      console.error('Error fetching metrics:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">System Telemetry & Resource Guardrails</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time memory allocation watchdog, CPU load, token telemetry, and execution latency.
          </p>
        </div>
        <button
          onClick={loadMetrics}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {metrics && (
        <div className="space-y-6 font-mono text-xs">
          {/* Main Gauges */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* RAM Guardrail Meter */}
            <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-300">SYSTEM RAM ALLOCATION</span>
                <span className={metrics.free_ram_mb < 1500 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                  {metrics.free_ram_mb < 1500 ? 'LOW MEMORY' : 'OPTIMAL'}
                </span>
              </div>
              <div className="text-2xl font-bold text-zinc-100">
                {metrics.free_ram_mb} MB <span className="text-xs text-zinc-500 font-normal">Free / {metrics.total_ram_mb} MB Total</span>
              </div>
              <div className="w-full bg-zinc-800 h-2.5 rounded-full overflow-hidden">
                <div
                  className={`h-full ${metrics.free_ram_mb < 1500 ? 'bg-rose-500' : 'bg-emerald-500'}`}
                  style={{ width: `${Math.round(((metrics.total_ram_mb - metrics.free_ram_mb) / metrics.total_ram_mb) * 100)}%` }}
                ></div>
              </div>
              <div className="text-[11px] text-zinc-500 flex justify-between">
                <span>Used: {metrics.total_ram_mb - metrics.free_ram_mb} MB</span>
                <span>Warning Threshold: 1500 MB</span>
              </div>
            </div>

            {/* CPU Load */}
            <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-300">INTEL CPU CORE LOAD</span>
                <span className="text-zinc-400">Integrated HD 620</span>
              </div>
              <div className="text-2xl font-bold text-zinc-100">{metrics.cpu_percent}%</div>
              <div className="w-full bg-zinc-800 h-2.5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-500"
                  style={{ width: `${Math.min(metrics.cpu_percent, 100)}%` }}
                ></div>
              </div>
              <div className="text-[11px] text-zinc-500">
                Zero GPU dependencies enforced. Single-inference process lock active.
              </div>
            </div>

            {/* Acceptance & Run Metrics */}
            <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-300">AVERAGE RUN DURATION</span>
                <Clock className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="text-2xl font-bold text-zinc-100">{metrics.avg_run_duration_sec}s</div>
              <div className="text-[11px] text-zinc-400 pt-1">
                Total Runs: <span className="text-zinc-200 font-bold">{metrics.total_runs}</span> | Success:{' '}
                <span className="text-emerald-400 font-bold">{metrics.successful_runs}</span>
              </div>
              <div className="text-[11px] text-zinc-500">
                Failed Runs: <span className="text-rose-400 font-bold">{metrics.failed_runs}</span>
              </div>
            </div>
          </div>

          {/* Telemetry Architecture Overview */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-200">RUNTIME GUARDRAIL STATUS</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
                <span className="text-zinc-500">CONCURRENCY LIMIT</span>
                <div className="text-zinc-200 font-bold">1 Local Request Max</div>
                <div className="text-[10px] text-zinc-500">Prevents memory thrashing</div>
              </div>

              <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
                <span className="text-zinc-500">PYTEST WORKERS</span>
                <div className="text-zinc-200 font-bold">1 Process Max</div>
                <div className="text-[10px] text-zinc-500">Subprocess isolation lock</div>
              </div>

              <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
                <span className="text-zinc-500">SANDBOX CONTAINER</span>
                <div className={metrics.docker_available ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                  {metrics.docker_available ? 'Docker Active' : 'Restricted Local Worktree'}
                </div>
                <div className="text-[10px] text-zinc-500">Zero privilege escalation</div>
              </div>

              <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
                <span className="text-zinc-500">COST PRICING</span>
                <div className="text-zinc-200 font-bold">Published Groq Tier</div>
                <div className="text-[10px] text-zinc-500">Estimated based on token usage</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
