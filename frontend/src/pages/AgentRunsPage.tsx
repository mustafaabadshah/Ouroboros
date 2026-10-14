import React, { useState, useEffect, useRef } from 'react';
import { PlayCircle, StopCircle, CheckCircle, RefreshCw, Terminal, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { Run } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { TabType } from '../components/Sidebar';

interface AgentRunsPageProps {
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  setCurrentTab: (tab: TabType) => void;
}

const LIFECYCLE_STEPS = [
  'IDLE',
  'BASELINE_VALIDATION',
  'PLANNING',
  'CODING',
  'PATCH_VALIDATION',
  'ACCEPTANCE_TESTS',
  'REGRESSION_TESTS',
  'AWAITING_APPROVAL',
  'COMPLETED'
];

export const AgentRunsPage: React.FC<AgentRunsPageProps> = ({
  selectedRunId,
  onSelectRun,
  setCurrentTab,
}) => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<string[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    loadRuns();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      attachSSE(selectedRunId);
    }
  }, [selectedRunId]);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await api.getRuns();
      setRuns(data);
      if (data.length > 0 && !selectedRunId) {
        onSelectRun(data[0].id);
      }
    } catch (e) {
      console.error('Error loading runs:', e);
    } finally {
      setLoading(false);
    }
  };

  const attachSSE = (runId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setLogs((prev) => [...prev, `[SSE] Connected to live run event stream: ${runId}`]);
    const es = new EventSource(`/api/runs/${runId}/events`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString();
        setLogs((prev) => [...prev, `[${timestamp}] [${payload.event_type}] ${JSON.stringify(payload.data)}`]);
        // Refresh run state
        loadRuns();
      } catch {
        // keepalive or raw message
      }
    };

    es.onerror = () => {
      es.close();
    };
  };

  const handleCancel = async (runId: string) => {
    if (confirm(`Are you sure you want to cancel run ${runId}?`)) {
      try {
        await api.cancelRun(runId);
        loadRuns();
      } catch (e) {
        alert(`Failed to cancel: ${e}`);
      }
    }
  };

  const selectedRun = runs.find((r) => r.id === selectedRunId) || runs[0];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Autonomous Agent Runs</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Deterministic lifecycle execution stepper, active agent tracking, and live SSE event logs.
          </p>
        </div>
        <button
          onClick={loadRuns}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Runs
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs List */}
        <div className="border border-zinc-800 rounded bg-zinc-950 divide-y divide-zinc-800/80 max-h-[700px] overflow-auto">
          {runs.length === 0 ? (
            <div className="p-6 text-center text-xs text-zinc-500 font-mono">
              No runs initiated yet. Approve a ticket to launch an autonomous run.
            </div>
          ) : (
            runs.map((r) => {
              const isSelected = r.id === selectedRun?.id;
              return (
                <div
                  key={r.id}
                  onClick={() => onSelectRun(r.id)}
                  className={`p-4 cursor-pointer transition ${
                    isSelected ? 'bg-zinc-900 border-l-2 border-emerald-500' : 'hover:bg-zinc-900/40'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-bold text-zinc-200">{r.id}</span>
                    <StatusBadge status={r.state} size="sm" />
                  </div>
                  <div className="text-[11px] font-mono text-zinc-500">Ticket: {r.ticket_id}</div>
                  <div className="text-[11px] font-mono text-zinc-400 mt-1 flex justify-between">
                    <span>Agent: {r.active_agent || 'Coordinator'}</span>
                    <span>Retries: {r.retry_count}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Selected Run Details & Live Stepper */}
        {selectedRun && (
          <div className="lg:col-span-2 space-y-6">
            <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-base font-bold text-zinc-100">{selectedRun.id}</span>
                    <StatusBadge status={selectedRun.state} />
                  </div>
                  <p className="text-xs font-mono text-zinc-500 mt-0.5">Ticket ID: {selectedRun.ticket_id}</p>
                </div>

                <div className="flex items-center gap-2">
                  {selectedRun.state === 'AWAITING_APPROVAL' && (
                    <button
                      onClick={() => setCurrentTab('changes')}
                      className="px-3 py-1.5 text-xs font-mono rounded bg-amber-500 text-zinc-950 font-bold hover:bg-amber-400 transition"
                    >
                      Review Patch Diff
                    </button>
                  )}
                  {['CODING', 'PLANNING', 'BASELINE_VALIDATION', 'ACCEPTANCE_TESTS', 'REGRESSION_TESTS'].includes(
                    selectedRun.state
                  ) && (
                    <button
                      onClick={() => handleCancel(selectedRun.id)}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-mono rounded border border-rose-800 bg-rose-950/60 text-rose-300 hover:bg-rose-900 transition"
                    >
                      <StopCircle className="w-3.5 h-3.5" /> Cancel Run
                    </button>
                  )}
                </div>
              </div>

              {/* State Stepper */}
              <div className="py-2">
                <div className="text-[11px] font-mono uppercase text-zinc-500 mb-3">Workflow State Stepper</div>
                <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-9 gap-1 text-center font-mono text-[10px]">
                  {LIFECYCLE_STEPS.map((st, i) => {
                    const isCurrent = selectedRun.state === st;
                    const isPassed =
                      LIFECYCLE_STEPS.indexOf(selectedRun.state) > i || selectedRun.state === 'COMPLETED';
                    let stepBg = 'bg-zinc-900 text-zinc-500 border-zinc-800';
                    if (isCurrent) {
                      stepBg = 'bg-sky-950/80 text-sky-300 border-sky-600 font-bold animate-pulse';
                    } else if (isPassed) {
                      stepBg = 'bg-emerald-950/50 text-emerald-400 border-emerald-800';
                    }
                    return (
                      <div key={st} className={`p-2 rounded border ${stepBg}`}>
                        <div className="truncate">{st.replace('_', ' ')}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Metadata Breakdown */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono pt-2 border-t border-zinc-800/80">
                <div>
                  <div className="text-zinc-500">ACTIVE AGENT</div>
                  <div className="text-zinc-200 mt-0.5">{selectedRun.active_agent || 'Orchestrator'}</div>
                </div>
                <div>
                  <div className="text-zinc-500">BRANCH</div>
                  <div className="text-zinc-200 mt-0.5 truncate">{selectedRun.candidate_branch || 'Isolated'}</div>
                </div>
                <div>
                  <div className="text-zinc-500">RETRIES</div>
                  <div className="text-zinc-200 mt-0.5">
                    {selectedRun.retry_count} / {selectedRun.max_retries}
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">VERDICT</div>
                  <div className="text-zinc-200 mt-0.5">{selectedRun.verdict || 'Pending'}</div>
                </div>
              </div>
            </div>

            {/* Live SSE Terminal Stream */}
            <div className="border border-zinc-800 rounded bg-zinc-950 overflow-hidden font-mono text-xs">
              <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-900/60 text-zinc-400">
                <Terminal className="w-3.5 h-3.5 text-zinc-400" />
                <span className="font-semibold text-zinc-300">Live SSE Event Stream</span>
              </div>
              <div className="p-4 space-y-1.5 max-h-60 overflow-auto bg-black/60 text-zinc-400 text-[11px] leading-relaxed">
                {logs.length === 0 ? (
                  <div className="text-zinc-600">Connecting to live SSE telemetry...</div>
                ) : (
                  logs.map((msg, i) => (
                    <div key={i} className="whitespace-pre-wrap font-mono">
                      {msg}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
