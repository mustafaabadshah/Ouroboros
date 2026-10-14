import React, { useState, useEffect } from 'react';
import { Activity, Cpu, ShieldAlert, DollarSign, Clock, RefreshCw, ExternalLink, Radio, Layers } from 'lucide-react';
import { api } from '../services/api';
import { MetricsOverview } from '../types';

interface PhoenixSpan {
  id: string;
  trace_id: string;
  name: string;
  span_kind: string;
  role: string;
  model_name: string;
  duration_ms: number;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  status: string;
  timestamp: string;
  attributes: Record<string, any>;
}

interface PhoenixStatus {
  enabled: boolean;
  active: boolean;
  ui_url: string;
  port: number;
  project_name: string;
  collector_endpoint: string;
  total_recorded_spans: number;
  recent_spans: PhoenixSpan[];
}

export const ObservabilityPage: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [phoenix, setPhoenix] = useState<PhoenixStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [metricsData, phoenixData] = await Promise.all([
        api.getMetricsOverview(),
        api.getPhoenixStatus().catch(() => null),
      ]);
      setMetrics(metricsData);
      if (phoenixData) {
        setPhoenix(phoenixData);
      }
    } catch (e) {
      console.error('Error fetching metrics/phoenix:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">System Telemetry & AI Observability</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time memory allocation watchdog, Arize Phoenix OpenTelemetry tracing, and execution latency.
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {/* Arize Phoenix AI Observability Section */}
      <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></div>
            <h3 className="text-sm font-bold font-mono text-zinc-100">
              ARIZE PHOENIX AI OBSERVABILITY & TRACING
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 font-bold">
              OPENINFERENCE OTEL
            </span>
          </div>
          {phoenix?.ui_url && (
            <a
              href={phoenix.ui_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Open Phoenix UI (Port {phoenix.port})
            </a>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">PROJECT NAME</span>
            <div className="text-zinc-200 font-bold">{phoenix?.project_name || 'ouroboros-swarm'}</div>
            <div className="text-[10px] text-zinc-500">OpenTelemetry Project</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">COLLECTOR ENDPOINT</span>
            <div className="text-emerald-400 font-bold truncate">{phoenix?.collector_endpoint || 'http://localhost:6006'}</div>
            <div className="text-[10px] text-zinc-500">OTLP HTTP Transport</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">RECORDED SPANS</span>
            <div className="text-zinc-100 font-bold text-base">{phoenix?.total_recorded_spans || 0} Spans</div>
            <div className="text-[10px] text-zinc-500">In-memory ring buffer</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">TRACING INSTRUMENTATION</span>
            <div className="text-zinc-200 font-bold">Agent + Evaluator + LLM</div>
            <div className="text-[10px] text-zinc-500">Semantic Conventions</div>
          </div>
        </div>

        {/* Recent Spans Stream */}
        <div className="space-y-2 pt-2">
          <h4 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
            Live OpenInference Span Stream
          </h4>
          <div className="border border-zinc-800/80 rounded bg-zinc-900/30 overflow-x-auto divide-y divide-zinc-800/60 max-h-60 overflow-y-auto font-mono">
            {!phoenix?.recent_spans || phoenix.recent_spans.length === 0 ? (
              <div className="p-4 text-center text-zinc-500 text-[11px]">
                No spans recorded yet. Trigger a ticket generation or swarm run to stream live spans.
              </div>
            ) : (
              phoenix.recent_spans.map((span) => (
                <div key={span.id} className="p-2.5 flex items-center justify-between text-[11px] hover:bg-zinc-900/60 transition">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        span.span_kind === 'AGENT'
                          ? 'bg-sky-950 text-sky-400 border border-sky-800'
                          : span.span_kind === 'EVALUATOR'
                          ? 'bg-amber-950 text-amber-400 border border-amber-800'
                          : 'bg-purple-950 text-purple-400 border border-purple-800'
                      }`}
                    >
                      {span.span_kind}
                    </span>
                    <span className="font-semibold text-zinc-200">{span.name}</span>
                    <span className="text-zinc-500 text-[10px]">({span.model_name})</span>
                  </div>
                  <div className="flex items-center gap-4 text-zinc-400 text-[10px]">
                    <span>{span.duration_ms} ms</span>
                    <span>{span.total_tokens} tok</span>
                    <span className={span.status === 'OK' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {span.status}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
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
