import React, { useState, useEffect, useRef } from 'react';
import {
  StopCircle,
  RefreshCw,
  Terminal,
  Activity,
  Clock,
  ShieldCheck,
  Brain,
  FileCode,
  Sparkles,
  AlertTriangle,
  ExternalLink,
  Copy,
  Check,
  CheckCircle2,
  Trash2,
  Layers,
  GitBranch,
  Flame,
  Radio,
  XCircle,
  Bug,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { api, BASE_URL, fallbackData } from '../services/api';
import { Run, FailureTrajectory, TestResult } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { TabType } from '../components/Sidebar';

interface AgentRunsPageProps {
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  setCurrentTab: (tab: TabType) => void;
}

interface StepInfo {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const LIFECYCLE_STEPS: StepInfo[] = [
  { key: 'IDLE', label: 'Idle / Init', icon: Clock, description: 'Queued for execution' },
  { key: 'BASELINE_VALIDATION', label: 'Baseline', icon: ShieldCheck, description: 'Verify unpatched test baseline' },
  { key: 'PLANNING', label: 'Architect Plan', icon: Brain, description: 'AST & Criteria Freeze' },
  { key: 'CODING', label: 'LocalCoder', icon: FileCode, description: 'Autonomous synthesis in worktree' },
  { key: 'PATCH_VALIDATION', label: 'Patch Validation', icon: Layers, description: 'Syntax & import validation' },
  { key: 'ACCEPTANCE_TESTS', label: 'Acceptance', icon: CheckCircle2, description: 'Target regression assertion' },
  { key: 'REGRESSION_TESTS', label: 'Full Regression', icon: Activity, description: 'Zero unintended collateral breakage' },
  { key: 'AWAITING_APPROVAL', label: 'Human Gate', icon: AlertTriangle, description: 'Awaiting operator signature' },
  { key: 'COMPLETED', label: 'Completed', icon: Sparkles, description: 'Verified release candidate' },
];

const CACHE_KEY_RUNS = 'ouroboros_cached_runs';

export const AgentRunsPage: React.FC<AgentRunsPageProps> = ({
  selectedRunId,
  onSelectRun,
  setCurrentTab,
}) => {
  const [runs, setRuns] = useState<Run[]>(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY_RUNS);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // ignore
    }
    return (fallbackData.runs as Run[]) || [];
  });
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [logFilter, setLogFilter] = useState<'ALL' | 'EVENTS' | 'ERRORS'>('ALL');
  const [copiedLogs, setCopiedLogs] = useState(false);
  const [failureTrajectories, setFailureTrajectories] = useState<FailureTrajectory[]>([]);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [expandedAttempt, setExpandedAttempt] = useState<number | null>(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const terminalBottomRef = useRef<HTMLDivElement | null>(null);

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
      const r = runs.find((run) => run.id === selectedRunId);
      loadRunDiagnostics(selectedRunId, r?.ticket_id);
    }
  }, [selectedRunId, runs]);

  useEffect(() => {
    if (terminalBottomRef.current) {
      terminalBottomRef.current.scrollTop = terminalBottomRef.current.scrollHeight;
    }
  }, [logs]);

  const loadRunDiagnostics = async (runId: string, ticketId?: string) => {
    try {
      setLoadingDiagnostics(true);
      const [resData, failData] = await Promise.all([
        api.getRunResults(runId).catch(() => []),
        api.getFailures(ticketId, runId).catch(() => []),
      ]);
      const results = (Array.isArray(resData) && resData.length > 0)
        ? resData
        : (fallbackData.testResults as TestResult[]).filter((r) => r.run_id === runId);
      setTestResults(results);

      const failures = (Array.isArray(failData) && failData.length > 0)
        ? failData
        : (fallbackData.failureTrajectories as FailureTrajectory[]).filter((f) => f.run_id === runId);
      const matchingFailures = failures.filter((f) => f.run_id === runId);
      setFailureTrajectories(matchingFailures);
      if (matchingFailures.length > 0) {
        setExpandedAttempt(matchingFailures[matchingFailures.length - 1].attempt);
      }
    } catch (err) {
      console.error('Error loading diagnostics:', err);
    } finally {
      setLoadingDiagnostics(false);
    }
  };

  const loadRuns = async () => {
    try {
      if (runs.length === 0) setLoading(true);
      const data = await api.getRuns();
      if (Array.isArray(data) && data.length > 0) {
        setRuns(data);
        localStorage.setItem(CACHE_KEY_RUNS, JSON.stringify(data));
        if (!selectedRunId) {
          onSelectRun(data[0].id);
        }
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
    const es = new EventSource(`${BASE_URL}/runs/${runId}/events`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString();
        if (payload.event_type === 'FAIL_FAST_TRIGGERED') {
          setLogs((prev) => [
            ...prev,
            `[${timestamp}] ⚡ [FAIL-FAST GATE] ${payload.data.test_file || 'Impact test'} failed in ${payload.data.duration_ms || 2100}ms. Regression suite bypassed -> Repair Agent triggered immediately.`
          ]);
        } else {
          setLogs((prev) => [...prev, `[${timestamp}] [${payload.event_type}] ${JSON.stringify(payload.data)}`]);
        }
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

  const handleCopyLogs = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    setCopiedLogs(true);
    setTimeout(() => setCopiedLogs(false), 2000);
  };

  const selectedRun = runs.find((r) => r.id === selectedRunId) || runs[0];

  const filteredLogs = logs.filter((msg) => {
    if (logFilter === 'ERRORS') {
      return msg.toLowerCase().includes('error') || msg.toLowerCase().includes('fail');
    }
    if (logFilter === 'EVENTS') {
      return msg.includes('[SSE]') || msg.includes('event_type');
    }
    return true;
  });

  const getStepStatus = (stepKey: string, currentStatus: string) => {
    const stepKeys = LIFECYCLE_STEPS.map((s) => s.key);
    const currentIndex = stepKeys.indexOf(currentStatus);
    const stepIndex = stepKeys.indexOf(stepKey);

    if (currentStatus === 'COMPLETED') return 'completed';
    if (currentStatus === 'FAILED') {
      if (stepIndex === currentIndex) return 'failed';
      return stepIndex < currentIndex ? 'completed' : 'pending';
    }
    if (stepIndex === currentIndex) return 'active';
    if (stepIndex < currentIndex) return 'completed';
    return 'pending';
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              MISSION CONTROL
            </span>
            <span className="text-zinc-500 text-xs font-mono">•</span>
            <span className="text-zinc-400 text-xs font-mono">AUTONOMOUS LIFECYCLE ENGINE</span>
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-zinc-100 flex items-center gap-2">
            Autonomous Agent Runs
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Deterministic lifecycle execution stepper, isolated candidate worktree sandbox, and live telemetry feeds.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentTab('observability')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-purple-500/30 bg-purple-950/30 hover:bg-purple-900/40 text-purple-300 transition"
            title="Open Phoenix OpenInference traces, agent execution spans, and telemetry"
          >
            <Radio className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
            <span>Phoenix Telemetry</span>
            <ExternalLink className="w-3 h-3 text-purple-400" />
          </button>
          <button
            onClick={loadRuns}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs List Sidebar */}
        <div className="glass-panel rounded-xl overflow-hidden divide-y divide-zinc-800/80 max-h-[780px] flex flex-col">
          <div className="p-3 bg-zinc-900/60 border-b border-zinc-800 flex items-center justify-between">
            <span className="font-mono text-xs font-semibold text-zinc-300">Active & Past Runs</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-zinc-800 text-zinc-400">
              {runs.length} runs
            </span>
          </div>

          <div className="divide-y divide-zinc-800/60 overflow-y-auto flex-1">
            {runs.length === 0 ? (
              <div className="p-8 text-center text-xs text-zinc-500 font-mono space-y-2">
                <Clock className="w-8 h-8 mx-auto text-zinc-600 mb-2 opacity-50" />
                <p>No runs initiated yet.</p>
                <p className="text-[11px] text-zinc-600">Approve a Jira-style ticket to launch an autonomous run.</p>
              </div>
            ) : (
              runs.map((r) => {
                const isSelected = r.id === selectedRun?.id;
                const isRunning = ['CODING', 'PLANNING', 'BASELINE_VALIDATION', 'ACCEPTANCE_TESTS', 'REGRESSION_TESTS'].includes(r.state);
                return (
                  <div
                    key={r.id}
                    onClick={() => onSelectRun(r.id)}
                    className={`p-4 cursor-pointer transition relative group ${
                      isSelected
                        ? 'bg-zinc-900/90 border-l-4 border-emerald-500 shadow-inner'
                        : 'hover:bg-zinc-900/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {isRunning && (
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                        )}
                        <span className="font-mono text-xs font-bold text-zinc-200 group-hover:text-emerald-400 transition">
                          {r.id}
                        </span>
                      </div>
                      <StatusBadge status={r.state} size="sm" />
                    </div>
                    <div className="text-[11px] font-mono text-zinc-400 truncate">
                      Ticket: <span className="text-zinc-300">{r.ticket_id}</span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mt-2">
                      <span className="flex items-center gap-1">
                        <Brain className="w-3 h-3 text-indigo-400" />
                        {r.active_agent || 'Orchestrator'}
                      </span>
                      <span>Retries: {r.retry_count}/{r.max_retries}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Run Details Panel */}
        {selectedRun && (
          <div className="lg:col-span-2 space-y-6">
            {/* Run Header Card */}
            <div className="glass-panel rounded-xl p-6 space-y-5 relative overflow-hidden">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-lg font-bold text-zinc-100">{selectedRun.id}</span>
                    <StatusBadge status={selectedRun.state} />
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-800 border border-zinc-700 text-zinc-300">
                      Repo: {selectedRun.repo_id}
                    </span>
                  </div>
                  <p className="text-xs font-mono text-zinc-400 mt-1 flex items-center gap-2">
                    <span>Target Ticket: <strong className="text-zinc-200">{selectedRun.ticket_id}</strong></span>
                    {selectedRun.started_at && (
                      <>
                        <span>•</span>
                        <span className="text-zinc-500">Started: {new Date(selectedRun.started_at).toLocaleTimeString()}</span>
                      </>
                    )}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {selectedRun.state === 'AWAITING_APPROVAL' && (
                    <button
                      onClick={() => setCurrentTab('changes')}
                      className="px-3 py-1.5 text-xs font-mono rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold transition flex items-center gap-1.5 shadow-lg shadow-amber-500/20"
                    >
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>Review Patch Diff</span>
                    </button>
                  )}
                  {['CODING', 'PLANNING', 'BASELINE_VALIDATION', 'ACCEPTANCE_TESTS', 'REGRESSION_TESTS'].includes(
                    selectedRun.state
                  ) && (
                    <button
                      onClick={() => handleCancel(selectedRun.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-rose-800 bg-rose-950/60 hover:bg-rose-900 text-rose-300 transition"
                    >
                      <StopCircle className="w-3.5 h-3.5 text-rose-400" />
                      <span>Cancel Run</span>
                    </button>
                  )}
                </div>
              </div>

              {/* 9-Step Interactive Lifecycle Flow */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
                  <span className="font-semibold text-zinc-300">LIFECYCLE EXECUTION PIPELINE</span>
                  <span className="text-[11px] text-zinc-500">
                    State: <strong className="text-emerald-400">{selectedRun.state}</strong>
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-9 gap-1.5 pt-1">
                  {LIFECYCLE_STEPS.map((st) => {
                    const status = getStepStatus(st.key, selectedRun.state);
                    const Icon = st.icon;

                    let bgClass = 'bg-zinc-900/60 border-zinc-800/80 text-zinc-500';
                    let iconColor = 'text-zinc-600';

                    if (status === 'active') {
                      bgClass = 'bg-sky-950/80 border-sky-500 text-sky-200 shadow-md shadow-sky-500/20 animate-pulse';
                      iconColor = 'text-sky-400';
                    } else if (status === 'completed') {
                      bgClass = 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300';
                      iconColor = 'text-emerald-400';
                    } else if (status === 'failed') {
                      bgClass = 'bg-rose-950/60 border-rose-600 text-rose-200';
                      iconColor = 'text-rose-400';
                    }

                    return (
                      <div
                        key={st.key}
                        title={st.description}
                        className={`p-2.5 rounded-lg border text-center transition flex flex-col items-center justify-between min-h-[72px] ${bgClass}`}
                      >
                        <Icon className={`w-4 h-4 mb-1 ${iconColor}`} />
                        <span className="text-[10px] font-mono font-medium leading-tight line-clamp-2">
                          {st.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Technical Metadata Matrix */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono pt-4 border-t border-zinc-800/80">
                <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/60">
                  <div className="text-zinc-500 text-[10px]">ACTIVE AGENT ROLE</div>
                  <div className="text-zinc-200 font-bold mt-1 flex items-center gap-1.5">
                    <Brain className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{selectedRun.active_agent || 'Orchestrator'}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/60">
                  <div className="text-zinc-500 text-[10px]">CANDIDATE BRANCH</div>
                  <div className="text-zinc-200 font-bold mt-1 truncate flex items-center gap-1.5">
                    <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{selectedRun.candidate_branch || 'Isolated Worktree'}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/60">
                  <div className="text-zinc-500 text-[10px]">RETRY CYCLES</div>
                  <div className="text-zinc-200 font-bold mt-1 flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5 text-amber-400" />
                    <span>{selectedRun.retry_count} / {selectedRun.max_retries} attempts</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/60">
                  <div className="text-zinc-500 text-[10px]">VERDICT / OUTCOME</div>
                  <div className="text-zinc-200 font-bold mt-1">
                    {selectedRun.verdict ? (
                      <span className="text-emerald-400 font-mono font-bold">{selectedRun.verdict}</span>
                    ) : selectedRun.state === 'FAILED' ? (
                      <span className="text-rose-400 font-mono font-bold">FAILED</span>
                    ) : (
                      <span className="text-zinc-400 font-mono">In Progress</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Failure Diagnosis & Root Cause Analysis Panel */}
            {selectedRun.state === 'FAILED' && (
              <div className="glass-panel rounded-xl p-5 border border-rose-900/60 bg-gradient-to-b from-rose-950/30 to-zinc-950/60 space-y-4 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-rose-900/40 pb-3">
                  <div className="flex items-center gap-2.5">
                    <XCircle className="w-5 h-5 text-rose-400 shrink-0" />
                    <div>
                      <h3 className="text-sm font-bold font-mono text-rose-200 uppercase tracking-wider flex items-center gap-2">
                        <span>Run Failure Diagnosis & Root Cause Analysis</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-950 border border-rose-800 text-rose-300">
                          {selectedRun.retry_count}/{selectedRun.max_retries} Retries Exhausted
                        </span>
                      </h3>
                      <p className="text-xs text-rose-300/80 mt-0.5 font-mono">
                        Active Agent at Termination: <strong className="text-zinc-200">{selectedRun.active_agent || 'Judge'}</strong>
                      </p>
                    </div>
                  </div>
                  {selectedRun.error_message && (
                    <span className="px-3 py-1 rounded-md text-xs font-mono font-bold bg-rose-950/80 border border-rose-700 text-rose-200 shadow-sm">
                      {selectedRun.error_message}
                    </span>
                  )}
                </div>

                {/* Attempt Trajectories Breakdown */}
                <div className="space-y-3">
                  <div className="text-xs font-mono font-semibold text-zinc-300 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Bug className="w-4 h-4 text-amber-400" />
                      <span>Retry Cycle Breakdown ({failureTrajectories.length} attempts recorded)</span>
                    </span>
                    <span className="text-[11px] text-zinc-500">Persistent Failure Memory Flywheel</span>
                  </div>

                  {failureTrajectories.length === 0 ? (
                    <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 text-xs font-mono text-zinc-400 space-y-3">
                      <div className="text-rose-400 font-semibold flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                        <span>Termination Reason: {selectedRun.error_message || 'Repair attempts exhausted.'}</span>
                      </div>
                      {testResults.length > 0 && (
                        <div className="mt-2 space-y-2">
                          <div className="text-zinc-300 text-[11px] font-bold">Execution & Test Results:</div>
                          {testResults.map((tr) => (
                            <div key={tr.id} className="p-3 rounded-lg bg-black/60 border border-zinc-800 text-[11px] space-y-1">
                              <div className="flex items-center justify-between text-zinc-400">
                                <span className="font-bold text-zinc-200">
                                  [{tr.test_type.toUpperCase()}] Exit Code: {tr.exit_code}
                                </span>
                                <span>Duration: {tr.duration_ms}ms</span>
                              </div>
                              <div className="text-zinc-400 text-[10px] truncate">Command: {tr.test_command}</div>
                              {tr.stderr_excerpt && (
                                <pre className="mt-2 p-2.5 rounded bg-rose-950/40 border border-rose-900/60 text-rose-300 text-[10px] overflow-x-auto whitespace-pre-wrap">
                                  {tr.stderr_excerpt}
                                </pre>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {failureTrajectories.map((ft) => {
                        const isExpanded = expandedAttempt === ft.attempt;
                        return (
                          <div
                            key={ft.id || ft.attempt}
                            className="rounded-lg border border-zinc-800/80 bg-zinc-900/70 overflow-hidden transition"
                          >
                            <div
                              onClick={() => setExpandedAttempt(isExpanded ? null : ft.attempt)}
                              className="p-3 cursor-pointer hover:bg-zinc-800/50 flex items-center justify-between gap-3 text-xs font-mono transition"
                            >
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="px-2 py-0.5 rounded font-bold bg-amber-500/10 border border-amber-500/30 text-amber-300">
                                  Attempt #{ft.attempt}
                                </span>
                                <span className="text-zinc-400">
                                  Provider: <strong className="text-zinc-200">{ft.provider || 'AI'}</strong> ({ft.model || 'model'})
                                </span>
                                <span className="text-zinc-600">•</span>
                                <span className="px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-900/80 text-rose-300 text-[10px]">
                                  {ft.failed_tests.join(', ') || 'Validation Failure'}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-zinc-400 shrink-0">
                                <span className="text-[11px] text-zinc-500 hidden sm:inline">
                                  {isExpanded ? 'Hide Traceback' : 'View Details'}
                                </span>
                                {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              </div>
                            </div>

                            {isExpanded && (
                              <div className="p-4 pt-1 border-t border-zinc-800/60 space-y-3 bg-black/40 text-xs font-mono">
                                <div>
                                  <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mb-1">
                                    Failure Error / Traceback Excerpt:
                                  </div>
                                  <pre className="p-3 rounded-lg bg-black/90 border border-rose-950/80 text-rose-300 text-[11px] overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed select-text">
                                    {ft.traceback_excerpt || 'No traceback captured.'}
                                  </pre>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                                  {ft.root_cause_hypothesis && (
                                    <div className="p-2.5 rounded-lg bg-zinc-900/80 border border-zinc-800">
                                      <div className="text-[10px] text-amber-400 font-bold mb-1">ROOT CAUSE HYPOTHESIS</div>
                                      <div className="text-zinc-300 text-[11px]">{ft.root_cause_hypothesis}</div>
                                    </div>
                                  )}
                                  {ft.repair_hint && (
                                    <div className="p-2.5 rounded-lg bg-zinc-900/80 border border-zinc-800">
                                      <div className="text-[10px] text-emerald-400 font-bold mb-1">FEEDBACK TO REPAIR AGENT</div>
                                      <div className="text-zinc-300 text-[11px]">{ft.repair_hint}</div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Live SSE Terminal Stream */}
            <div className="glass-panel rounded-xl overflow-hidden font-mono text-xs border border-zinc-800 shadow-xl">
              <div className="flex flex-wrap items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/80">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5 mr-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block" />
                  </div>
                  <Terminal className="w-4 h-4 text-emerald-400" />
                  <span className="font-semibold text-zinc-200">Live SSE Telemetry Stream</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950/60 border border-emerald-800 text-emerald-300">
                    Active
                  </span>
                </div>

                <div className="flex items-center gap-2 mt-2 sm:mt-0">
                  {/* Filters */}
                  <div className="flex rounded-lg border border-zinc-800 bg-zinc-950 p-0.5 text-[10px]">
                    <button
                      onClick={() => setLogFilter('ALL')}
                      className={`px-2 py-0.5 rounded ${logFilter === 'ALL' ? 'bg-zinc-800 text-zinc-100 font-bold' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                      ALL
                    </button>
                    <button
                      onClick={() => setLogFilter('EVENTS')}
                      className={`px-2 py-0.5 rounded ${logFilter === 'EVENTS' ? 'bg-zinc-800 text-zinc-100 font-bold' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                      EVENTS
                    </button>
                    <button
                      onClick={() => setLogFilter('ERRORS')}
                      className={`px-2 py-0.5 rounded ${logFilter === 'ERRORS' ? 'bg-zinc-800 text-zinc-100 font-bold' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                      ERRORS
                    </button>
                  </div>

                  <button
                    onClick={handleCopyLogs}
                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition"
                  >
                    {copiedLogs ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-zinc-400" />}
                    <span>{copiedLogs ? 'Copied' : 'Copy'}</span>
                  </button>

                  <button
                    onClick={() => setLogs([])}
                    className="p-1 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded transition"
                    title="Clear Terminal"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div
                ref={terminalBottomRef}
                className="p-4 space-y-1.5 max-h-72 overflow-y-auto bg-black/80 text-zinc-300 text-[11px] leading-relaxed select-text font-mono"
              >
                {filteredLogs.length === 0 ? (
                  <div className="text-zinc-600 italic py-4 text-center">
                    Awaiting live stream messages from FastAPI event bus...
                  </div>
                ) : (
                  filteredLogs.map((msg, i) => {
                    const isErr = msg.toLowerCase().includes('error') || msg.toLowerCase().includes('failed');
                    const isEvent = msg.includes('[SSE]');
                    let lineClass = 'text-zinc-400';
                    if (isErr) lineClass = 'text-rose-400 font-semibold';
                    else if (isEvent) lineClass = 'text-indigo-400';

                    return (
                      <div key={i} className={`whitespace-pre-wrap ${lineClass}`}>
                        {msg}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
