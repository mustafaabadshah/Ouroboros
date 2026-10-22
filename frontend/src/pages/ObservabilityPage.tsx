import React, { useState, useEffect, useRef } from 'react';
import { Activity, Cpu, ShieldAlert, DollarSign, Clock, RefreshCw, ExternalLink, Radio, Layers, Terminal, Search } from 'lucide-react';
import { api } from '../services/api';
import { MetricsOverview } from '../types';

interface PhoenixSpan {
  id: string;
  trace_id: string;
  otel_trace_id?: string;
  otel_span_id?: string;
  parent_span_id?: string;
  phoenix_url?: string;
  name: string;
  span_kind: string;
  role: string;
  model_name: string;
  duration_ms: number;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  status: string;
  error_message?: string;
  ticket_id?: string;
  run_id?: string;
  timestamp: string;
  input?: string;
  output?: string;
  attributes: Record<string, any>;
}

interface PhoenixStatus {
  enabled: boolean;
  active: boolean;
  ui_url: string;
  dashboard_url?: string;
  is_cloud?: boolean;
  port: number;
  project_name: string;
  collector_endpoint: string;
  total_recorded_spans: number;
  recent_spans: PhoenixSpan[];
}

interface SystemLog {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  formatted: string;
}

export const ObservabilityPage: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [phoenix, setPhoenix] = useState<PhoenixStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSpan, setSelectedSpan] = useState<PhoenixSpan | null>(null);
  const [spanFilter, setSpanFilter] = useState<string>('ALL');
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'spans' | 'logs'>('spans');
  const [systemLogs, setSystemLogs] = useState<SystemLog[]>([]);
  const [logSearch, setLogSearch] = useState<string>('');
  const [logFilterLevel, setLogFilterLevel] = useState<string>('ALL');
  const [autoScrollLogs, setAutoScrollLogs] = useState<boolean>(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const copyToClipboard = (text: string, section: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(section);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  useEffect(() => {
    loadData(true);
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadData(false);
      }
    }, 6000);

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadData(false);
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (autoScrollLogs && logsEndRef.current && activeTab === 'logs') {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [systemLogs, activeTab, autoScrollLogs]);

  const loadData = async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      const [metricsData, phoenixData, logsData] = await Promise.all([
        api.getMetricsOverview(),
        api.getPhoenixStatus().catch(() => null),
        api.getSystemLogs(150).catch(() => ({ logs: [] })),
      ]);
      setMetrics(metricsData);
      if (phoenixData) {
        setPhoenix(phoenixData);
      }
      if (logsData?.logs) {
        setSystemLogs(logsData.logs);
      }
    } catch (e) {
      console.error('Error fetching metrics/phoenix/logs:', e);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  const filteredSpans = (phoenix?.recent_spans || []).filter((s) => {
    if (spanFilter === 'ALL') return true;
    if (spanFilter === 'AGENT') return s.span_kind === 'AGENT';
    if (spanFilter === 'EVALUATOR') return s.span_kind === 'EVALUATOR';
    if (spanFilter === 'ERROR') return s.status !== 'OK';
    return true;
  });

  const filteredLogs = systemLogs.filter((log) => {
    if (logFilterLevel !== 'ALL' && log.level !== logFilterLevel) return false;
    if (logSearch.trim()) {
      const q = logSearch.toLowerCase();
      const matchMsg = (log.message || log.formatted || '').toLowerCase().includes(q);
      const matchLvl = (log.level || '').toLowerCase().includes(q);
      const matchLogger = (log.logger || '').toLowerCase().includes(q);
      return matchMsg || matchLvl || matchLogger;
    }
    return true;
  });

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
          onClick={() => loadData(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {/* Arize Phoenix AI Observability Section */}
      <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${phoenix?.active ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></div>
            <h3 className="text-sm font-bold font-mono text-zinc-100">
              ARIZE PHOENIX AI OBSERVABILITY & TRACING
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 font-bold">
              OTLP HTTP/PROTOBUF
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-400">
              {phoenix?.active ? 'COLLECTOR ACTIVE' : 'COLLECTOR OFFLINE'}
            </span>
          </div>
          {(() => {
            const dashUrl = phoenix?.dashboard_url || phoenix?.ui_url || 'https://ouroboros-backend-i9x2.onrender.com/phoenix';
            return (
              <a
                href={dashUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition shadow-sm"
                title="Open Arize Phoenix AI Observability & Live Logs Web Dashboard"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open Phoenix Web Dashboard</span>
              </a>
            );
          })()}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">PROJECT NAME</span>
            <div className="text-zinc-200 font-bold">{phoenix?.project_name || 'ouroboros-swarm'}</div>
            <div className="text-[10px] text-zinc-500">OpenTelemetry Project</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">COLLECTOR ENDPOINT</span>
            <div className="text-emerald-400 font-bold truncate">{phoenix?.collector_endpoint || 'https://ouroboros-backend-i9x2.onrender.com/api/observability/phoenix/status'}</div>
            <div className="text-[10px] text-zinc-500">HTTP/protobuf Cloud Ingest</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">RECORDED SPANS</span>
            <div className="text-zinc-100 font-bold text-base">{phoenix?.total_recorded_spans || 0} Spans</div>
            <div className="text-[10px] text-zinc-500">OpenInference Spans in Buffer</div>
          </div>
          <div className="p-3 rounded bg-zinc-900/50 border border-zinc-800 space-y-1">
            <span className="text-zinc-500">TRACING INSTRUMENTATION</span>
            <div className="text-zinc-200 font-bold">Root Chain + Agent + Evaluator</div>
            <div className="text-[10px] text-zinc-500">Hierarchical OpenInference</div>
          </div>
        </div>

        {/* Tab Switcher: Spans Stream vs Live Server & Swarm Logs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-zinc-800 pb-2 pt-2 gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('spans')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded transition ${
                activeTab === 'spans'
                  ? 'bg-zinc-800 text-zinc-100 border border-zinc-600'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent'
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-purple-400" />
              <span>OpenInference Spans ({filteredSpans.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded transition ${
                activeTab === 'logs'
                  ? 'bg-zinc-800 text-zinc-100 border border-zinc-600'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent'
              }`}
            >
              <Terminal className="w-3.5 h-3.5 text-emerald-400" />
              <span>Live Server & Swarm Logs ({systemLogs.length})</span>
            </button>
          </div>

          {activeTab === 'spans' ? (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Filter:</span>
              <div className="flex gap-1.5 text-[10px] font-mono">
                {['ALL', 'AGENT', 'EVALUATOR', 'ERROR'].map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setSpanFilter(filter)}
                    className={`px-2 py-0.5 rounded border ${
                      spanFilter === filter
                        ? 'bg-zinc-700 text-zinc-100 border-zinc-500'
                        : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-xs font-mono">
              <div className="flex items-center gap-1 text-[10px]">
                {['ALL', 'INFO', 'WARNING', 'ERROR'].map((level) => (
                  <button
                    key={level}
                    onClick={() => setLogFilterLevel(level)}
                    className={`px-2 py-0.5 rounded border ${
                      logFilterLevel === level
                        ? 'bg-zinc-700 text-zinc-100 border-zinc-500'
                        : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800'
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-1.5 text-[10px] text-zinc-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoScrollLogs}
                  onChange={(e) => setAutoScrollLogs(e.target.checked)}
                  className="rounded bg-zinc-800 border-zinc-700 text-emerald-500 focus:ring-0"
                />
                Auto-scroll
              </label>
            </div>
          )}
        </div>

        {/* Live Logs Terminal View */}
        {activeTab === 'logs' && (
          <div className="space-y-3 font-mono">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-500" />
                <input
                  type="text"
                  placeholder="Filter logs by keyword, module, or error message..."
                  value={logSearch}
                  onChange={(e) => setLogSearch(e.target.value)}
                  className="w-full bg-zinc-900/80 border border-zinc-800 rounded px-8 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
                />
              </div>
              <button
                onClick={() => loadData(false)}
                className="px-2.5 py-1.5 text-xs rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 flex items-center gap-1 transition"
                title="Fetch latest log entries"
              >
                <RefreshCw className="w-3 h-3" /> Refresh Logs
              </button>
            </div>

            <div className="border border-zinc-800 rounded-lg bg-zinc-950 p-3 h-96 overflow-y-auto text-[11px] leading-relaxed divide-y divide-zinc-900/60 shadow-inner">
              {filteredLogs.length === 0 ? (
                <div className="p-8 text-center text-zinc-500">
                  No log entries matching filter. Trigger autonomous swarm runs or navigate to stream live logs.
                </div>
              ) : (
                filteredLogs.map((log, i) => (
                  <div key={i} className="py-1 flex items-start gap-2 text-zinc-300 hover:bg-zinc-900/40 px-1 rounded transition">
                    <span className="text-zinc-600 text-[10px] select-none flex-shrink-0 pt-0.5">{log.timestamp || '00:00:00'}</span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-bold flex-shrink-0 ${
                        log.level === 'ERROR'
                          ? 'bg-rose-950 text-rose-400 border border-rose-800'
                          : log.level === 'WARNING'
                          ? 'bg-amber-950 text-amber-400 border border-amber-800'
                          : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      }`}
                    >
                      {log.level}
                    </span>
                    {log.logger && (
                      <span className="text-zinc-500 text-[10px] flex-shrink-0 font-semibold">[{log.logger}]</span>
                    )}
                    <span className="break-all whitespace-pre-wrap flex-1">{log.message || log.formatted}</span>
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>

            <div className="flex justify-between items-center text-[10px] text-zinc-500 pt-1">
              <span>Displaying {filteredLogs.length} of {systemLogs.length} buffered log lines</span>
              <a
                href={phoenix?.dashboard_url || phoenix?.ui_url || 'https://ouroboros-backend-i9x2.onrender.com/phoenix'}
                target="_blank"
                rel="noreferrer"
                className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-bold transition"
              >
                Open Fullscreen Phoenix & Logs Web Dashboard <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        )}

        {/* Recent Spans Stream View */}
        {activeTab === 'spans' && (
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Live OpenInference Span Stream ({filteredSpans.length})
            </h4>
          </div>

          <div className="border border-zinc-800/80 rounded bg-zinc-900/30 overflow-x-auto divide-y divide-zinc-800/60 max-h-72 overflow-y-auto font-mono">
            {filteredSpans.length === 0 ? (
              <div className="p-4 text-center text-zinc-500 text-[11px]">
                No spans recorded matching filter. Trigger a ticket generation or swarm run to stream live spans.
              </div>
            ) : (
              filteredSpans.map((span) => (
                <div
                  key={span.id}
                  onClick={() => setSelectedSpan(span)}
                  className={`p-2.5 flex items-center justify-between text-[11px] cursor-pointer hover:bg-zinc-900/80 transition ${
                    selectedSpan?.id === span.id ? 'bg-zinc-900/90 border-l-2 border-emerald-400' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {span.parent_span_id ? (
                      <span className="text-zinc-600 font-bold text-xs" title={`Child of ${span.parent_span_id}`}>↳</span>
                    ) : (
                      <span className="text-emerald-500 font-bold text-xs" title="Root Span">●</span>
                    )}
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
                    {span.parent_span_id && (
                      <span className="text-[9px] text-zinc-500 bg-zinc-900 px-1 rounded border border-zinc-800">
                        child:{span.parent_span_id.slice(0, 6)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-zinc-400 text-[10px]">
                    <span>{span.duration_ms} ms</span>
                    {span.total_tokens > 0 && <span>{span.total_tokens} tok</span>}
                    <span className={span.status === 'OK' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {span.status}
                    </span>
                    {span.otel_trace_id && phoenix?.ui_url && (
                      <a
                        href={`http://127.0.0.1:${phoenix.port}/?project=${phoenix.project_name}`}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        title="View trace in Arize Phoenix UI"
                        className="text-emerald-400 hover:text-emerald-300"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Span Detail Inspection Modal/Panel with Full Agent I/O */}
          {selectedSpan && (
            <div className="mt-3 p-4 border border-zinc-800 rounded bg-zinc-900/70 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950 text-sky-400 border border-sky-800">
                    {selectedSpan.role || selectedSpan.span_kind}
                  </span>
                  <span className="font-bold text-zinc-200 text-sm">{selectedSpan.name}</span>
                  <span className="text-[10px] text-zinc-500">Span ID: {selectedSpan.otel_span_id || selectedSpan.id}</span>
                </div>
                <button
                  onClick={() => setSelectedSpan(null)}
                  className="text-zinc-500 hover:text-zinc-300 text-xs px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 transition"
                >
                  Close
                </button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-[11px] bg-zinc-950/60 p-3 rounded border border-zinc-800">
                <div>
                  <span className="text-zinc-500 block">ROLE / AGENT</span>
                  <span className="text-zinc-200 font-bold font-mono">
                    {selectedSpan.role || 'System'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block">AI MODEL</span>
                  <span className="text-zinc-300 font-mono">
                    {selectedSpan.model_name || 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block">RUN / TICKET</span>
                  <span className="text-zinc-300">
                    {selectedSpan.ticket_id || selectedSpan.run_id || 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block">TOKENS (IN / OUT)</span>
                  <span className="text-zinc-300">
                    {selectedSpan.tokens_in} in / {selectedSpan.tokens_out} out ({selectedSpan.total_tokens} total)
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 block">EXECUTION STATUS</span>
                  <span className={selectedSpan.status === 'OK' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {selectedSpan.status} ({selectedSpan.duration_ms} ms)
                  </span>
                </div>
              </div>

              {selectedSpan.error_message && (
                <div className="p-3 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-[11px]">
                  <strong>Execution Error:</strong> {selectedSpan.error_message}
                </div>
              )}

              {/* Agent Input Prompt Section */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400 text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-sky-400"></span> Agent Input / Prompt
                  </span>
                  {(selectedSpan.input || selectedSpan.attributes?.['input.value'] || selectedSpan.attributes?.['llm.input_messages.0.message.content']) && (
                    <button
                      onClick={() =>
                        copyToClipboard(
                          selectedSpan.input ||
                            selectedSpan.attributes?.['input.value'] ||
                            selectedSpan.attributes?.['llm.input_messages.0.message.content'] ||
                            '',
                          'input'
                        )
                      }
                      className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
                    >
                      {copiedSection === 'input' ? 'Copied!' : 'Copy Prompt'}
                    </button>
                  )}
                </div>
                <div className="bg-zinc-950 p-3 rounded border border-zinc-800/90 max-h-48 overflow-y-auto">
                  <pre className="text-zinc-300 text-[11px] whitespace-pre-wrap font-mono leading-relaxed select-text">
                    {selectedSpan.input ||
                      selectedSpan.attributes?.['input.value'] ||
                      selectedSpan.attributes?.['llm.input_messages.0.message.content'] ||
                      '[No input prompt captured for this span]'}
                  </pre>
                </div>
              </div>

              {/* Agent Output / Response Section */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400 text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span> Agent Output / Result
                  </span>
                  {(selectedSpan.output || selectedSpan.attributes?.['output.value'] || selectedSpan.attributes?.['llm.output_messages.0.message.content']) && (
                    <button
                      onClick={() =>
                        copyToClipboard(
                          selectedSpan.output ||
                            selectedSpan.attributes?.['output.value'] ||
                            selectedSpan.attributes?.['llm.output_messages.0.message.content'] ||
                            '',
                          'output'
                        )
                      }
                      className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
                    >
                      {copiedSection === 'output' ? 'Copied!' : 'Copy Output'}
                    </button>
                  )}
                </div>
                <div className="bg-zinc-950 p-3 rounded border border-zinc-800/90 max-h-56 overflow-y-auto">
                  <pre className="text-emerald-300 text-[11px] whitespace-pre-wrap font-mono leading-relaxed select-text">
                    {selectedSpan.output ||
                      selectedSpan.attributes?.['output.value'] ||
                      selectedSpan.attributes?.['llm.output_messages.0.message.content'] ||
                      '[No output content captured for this span]'}
                  </pre>
                </div>
              </div>

              {selectedSpan.attributes && Object.keys(selectedSpan.attributes).length > 0 && (
                <div className="space-y-1 pt-1">
                  <span className="text-zinc-500 text-[10px] uppercase font-bold">OpenInference & OTel Attributes</span>
                  <div className="bg-zinc-950 p-2.5 rounded border border-zinc-800 text-[11px] overflow-x-auto max-h-32 overflow-y-auto">
                    <pre className="text-zinc-400 text-[10px] leading-relaxed">
                      {JSON.stringify(selectedSpan.attributes, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        )}
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
