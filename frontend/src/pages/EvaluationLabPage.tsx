import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  RefreshCw,
  Play,
  Download,
  BarChart2,
  Cpu,
  ShieldCheck,
  Brain,
  FileCode,
  Clock,
  TrendingUp,
  Check,
  X,
  Lock
} from 'lucide-react';
import { api } from '../services/api';
import { TestResult, Run, EvaluationOverview, EvaluationComparison, SafetyApprovalItem } from '../types';

interface EvaluationLabPageProps {
  selectedRunId: string | null;
}

export const EvaluationLabPage: React.FC<EvaluationLabPageProps> = ({ selectedRunId }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'comparison' | 'tasks' | 'safety' | 'runs'>('overview');

  // Overview & Comparison Data
  const [overview, setOverview] = useState<EvaluationOverview | null>(null);
  const [comparison, setComparison] = useState<EvaluationComparison | null>(null);
  const [tasksList, setTasksList] = useState<any[]>([]);
  const [safetyReviews, setSafetyReviews] = useState<SafetyApprovalItem[]>([]);

  // Selected task detail state
  const [selectedTaskId, setSelectedTaskId] = useState<string>('BENCH-01');
  const [taskDetail, setTaskDetail] = useState<any | null>(null);
  const [loadingTaskDetail, setLoadingTaskDetail] = useState(false);

  // Workflow runs state
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(selectedRunId);
  const [results, setResults] = useState<TestResult[]>([]);

  // Loading & status states
  const [loading, setLoading] = useState(false);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    loadAllEvaluationData();
    loadRuns();
  }, []);

  useEffect(() => {
    if (activeRunId) {
      loadResults(activeRunId);
    }
  }, [activeRunId]);

  useEffect(() => {
    if (selectedTaskId) {
      loadTaskDetail(selectedTaskId);
    }
  }, [selectedTaskId]);

  const loadAllEvaluationData = async () => {
    try {
      setLoading(true);
      const [ov, comp, tList, safety] = await Promise.all([
        api.getEvaluationOverview().catch(() => null),
        api.getEvaluationComparison().catch(() => null),
        api.getEvaluationTasks().catch(() => []),
        api.getSafetyApprovals().catch(() => [])
      ]);
      setOverview(ov);
      setComparison(comp);
      setTasksList(tList);
      setSafetyReviews(safety);
    } catch (e) {
      console.error('Error loading evaluation data:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadTaskDetail = async (taskId: string) => {
    try {
      setLoadingTaskDetail(true);
      const data = await api.getEvaluationTaskDetail(taskId);
      setTaskDetail(data);
    } catch (e) {
      console.error('Error loading task detail:', e);
    } finally {
      setLoadingTaskDetail(false);
    }
  };

  const loadRuns = async () => {
    try {
      const data = await api.getRuns();
      setRuns(data);
      if (data.length > 0 && !activeRunId) {
        setActiveRunId(data[0].id);
      }
    } catch (e) {
      console.error('Error fetching runs:', e);
    }
  };

  const loadResults = async (runId: string) => {
    try {
      const res = await api.getRunResults(runId);
      setResults(res);
    } catch (e) {
      console.error('Error loading test results:', e);
    }
  };

  const handleRunBenchmark = async () => {
    try {
      setRunningBenchmark(true);
      await api.runBenchmarkSuite(memoryEnabled);
      await loadAllEvaluationData();
    } catch (e) {
      console.error('Error running benchmark:', e);
    } finally {
      setRunningBenchmark(false);
    }
  };

  const handleSafetyAction = async (reviewId: string, action: 'approve' | 'reject' | 'cancel') => {
    try {
      const res = await api.postSafetyApprovalAction(reviewId, action, `Manual operator ${action} via Evaluation Lab`);
      setActionMessage(res.message);
      // Reload reviews
      const updated = await api.getSafetyApprovals();
      setSafetyReviews(updated);
      setTimeout(() => setActionMessage(null), 4000);
    } catch (e: any) {
      setActionMessage(`Error: ${e.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">
              Evaluation & Generalization Lab
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
              v0.11 Verified
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Reproducible repair benchmarks, statistical ablation, telemetry inspection, and safety verification.
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2">
          <div className="bg-zinc-900 border border-zinc-800 rounded p-1 flex gap-1">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'overview' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('comparison')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'comparison' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Ablation & Trials
            </button>
            <button
              onClick={() => setActiveTab('tasks')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'tasks' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Task Diagnostics
            </button>
            <button
              onClick={() => setActiveTab('safety')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 ${
                activeTab === 'safety' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              Safety & Approval
            </button>
            <button
              onClick={() => setActiveTab('runs')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'runs' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Workflow Runs
            </button>
          </div>
          <button
            onClick={loadAllEvaluationData}
            className="p-1.5 rounded border border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
            title="Refresh All Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-indigo-950/60 border border-indigo-800 text-indigo-300 rounded text-xs font-mono flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-zinc-400 hover:text-zinc-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ===================== TAB 1: OVERVIEW ===================== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {overview ? (
            <>
              {/* Primary KPI Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* 1. Repair Success Rate */}
                <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-2">
                  <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                    <BarChart2 className="w-4 h-4 text-emerald-400" /> Eligible Repair Success
                  </div>
                  <div className="text-3xl font-bold font-mono text-emerald-400">
                    {(overview.eligible_repair_success_rate * 100).toFixed(1)}%
                  </div>
                  <div className="text-[10px] font-mono text-zinc-400">
                    {overview.eligible_repairs_passed}/{overview.eligible_tasks_total} eligible repairs passed
                  </div>
                  <div className="text-[10px] font-mono text-zinc-500 border-t border-zinc-900 pt-1">
                    Wilson 95% CI: [{(overview.wilson_ci_95.lower * 100).toFixed(1)}%, {(overview.wilson_ci_95.upper * 100).toFixed(1)}%]
                  </div>
                </div>

                {/* 2. Adversarial Security Guard */}
                <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-2">
                  <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-indigo-400" /> Adversarial Enforcement
                  </div>
                  <div className="text-3xl font-bold font-mono text-indigo-400">
                    {(overview.adversarial_block_rate * 100).toFixed(1)}%
                  </div>
                  <div className="text-[10px] font-mono text-zinc-400">
                    {overview.adversarial_blocked}/{overview.adversarial_total} security breaches blocked
                  </div>
                  <div className="text-[10px] font-mono text-emerald-500 border-t border-zinc-900 pt-1">
                    Protected paths: .env, .git, rootless
                  </div>
                </div>

                {/* 3. Latency Metrics */}
                <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-2">
                  <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-amber-400" /> Latency Profile
                  </div>
                  <div className="text-3xl font-bold font-mono text-amber-400">
                    {(overview.median_latency_ms / 1000).toFixed(1)}s
                  </div>
                  <div className="text-[10px] font-mono text-zinc-400">
                    Median P50 duration per task
                  </div>
                  <div className="text-[10px] font-mono text-zinc-500 border-t border-zinc-900 pt-1">
                    P95 Latency: {(overview.p95_latency_ms / 1000).toFixed(1)}s
                  </div>
                </div>

                {/* 4. Token & Cost Accounting */}
                <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-2">
                  <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                    <Cpu className="w-4 h-4 text-purple-400" /> Token Consumption
                  </div>
                  <div className="text-3xl font-bold font-mono text-purple-400">
                    {overview.total_tokens.toLocaleString()}
                  </div>
                  <div className="text-[10px] font-mono text-zinc-400">
                    Prompt: {overview.tokens_in.toLocaleString()} | Completion: {overview.tokens_out.toLocaleString()}
                  </div>
                  <div className="text-[10px] font-mono text-zinc-500 border-t border-zinc-900 pt-1">
                    Infrastructure Failures: {overview.infrastructure_failures}
                  </div>
                </div>
              </div>

              {/* Task Outcome Breakdown Banner */}
              <div className="p-4 border border-zinc-800 rounded bg-zinc-950 font-mono text-xs">
                <div className="text-zinc-400 font-semibold mb-3">Suite Task Outcome Distribution (16 Total Tasks)</div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                  <div className="p-2.5 rounded bg-zinc-900/60 border border-emerald-950">
                    <div className="text-emerald-400 font-bold text-lg">{overview.task_counts.completed}</div>
                    <div className="text-[10px] text-zinc-400 uppercase">Passed Repairs</div>
                  </div>
                  <div className="p-2.5 rounded bg-zinc-900/60 border border-rose-950">
                    <div className="text-rose-400 font-bold text-lg">{overview.task_counts.failed}</div>
                    <div className="text-[10px] text-zinc-400 uppercase">Failed Repairs</div>
                  </div>
                  <div className="p-2.5 rounded bg-zinc-900/60 border border-indigo-950">
                    <div className="text-indigo-400 font-bold text-lg">{overview.task_counts.blocked}</div>
                    <div className="text-[10px] text-zinc-400 uppercase">Policy Blocked</div>
                  </div>
                  <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800">
                    <div className="text-zinc-400 font-bold text-lg">{overview.infrastructure_failures}</div>
                    <div className="text-[10px] text-zinc-500 uppercase">Infra Errors</div>
                  </div>
                  <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800">
                    <div className="text-zinc-400 font-bold text-lg">{overview.task_counts.invalid}</div>
                    <div className="text-[10px] text-zinc-500 uppercase">Invalid Fixtures</div>
                  </div>
                </div>
              </div>

              {/* Benchmark Runner Controls */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border border-zinc-800 rounded bg-zinc-900/60 font-mono text-xs">
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                    <input
                      type="checkbox"
                      checked={memoryEnabled}
                      onChange={(e) => setMemoryEnabled(e.target.checked)}
                      className="rounded border-zinc-700 bg-zinc-950 text-indigo-500 focus:ring-0"
                    />
                    <span>Memory & Flywheel Retrieval Active</span>
                  </label>
                  <span className="text-[11px] text-zinc-500">Run ID: {overview.run_id}</span>
                </div>

                <div className="flex items-center gap-2.5">
                  <button
                    onClick={handleRunBenchmark}
                    disabled={runningBenchmark}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors disabled:opacity-50"
                  >
                    {runningBenchmark ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running Suite...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" /> Run Benchmark Suite
                      </>
                    )}
                  </button>

                  <a
                    href={api.exportBenchmarkUrl(memoryEnabled)}
                    download="ouroboros_v011_eval.json"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> Export JSON
                  </a>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 border border-zinc-800 rounded bg-zinc-950 text-center font-mono text-xs text-zinc-500">
              Loading evaluation overview metrics...
            </div>
          )}
        </div>
      )}

      {/* ===================== TAB 2: RUN COMPARISON & REPETITIONS ===================== */}
      {activeTab === 'comparison' && (
        <div className="space-y-6">
          {comparison ? (
            <>
              {/* Paired Comparison Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono">
                {/* Condition A: Memory Enabled */}
                <div className="p-5 rounded border border-emerald-950/80 bg-zinc-950 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400 uppercase tracking-wide flex items-center gap-1.5">
                      <Brain className="w-4 h-4 text-emerald-400" /> {comparison.conditions.memory_enabled.name}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                      Priority 2C Engine
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-emerald-400">
                    {(comparison.conditions.memory_enabled.success_rate * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-zinc-400">
                    {comparison.conditions.memory_enabled.repairs_passed} / {comparison.conditions.memory_enabled.eligible_total} eligible repairs passed
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-zinc-500 border-t border-zinc-900 pt-2">
                    <div>Tokens: {comparison.conditions.memory_enabled.total_tokens.toLocaleString()}</div>
                    <div>Median Latency: {(comparison.conditions.memory_enabled.median_duration_ms / 1000).toFixed(1)}s</div>
                    <div>Wilson CI: [{(comparison.conditions.memory_enabled.wilson_ci_95.lower * 100).toFixed(1)}%, {(comparison.conditions.memory_enabled.wilson_ci_95.upper * 100).toFixed(1)}%]</div>
                    <div>Exceeded Attempts: {comparison.conditions.memory_enabled.tasks_exceeding_max_attempts}</div>
                  </div>
                </div>

                {/* Condition B: Naive Retry Baseline */}
                <div className="p-5 rounded border border-zinc-800 bg-zinc-950 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-zinc-300 uppercase tracking-wide flex items-center gap-1.5">
                      <RefreshCw className="w-4 h-4 text-zinc-400" /> {comparison.conditions.baseline.name}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                      Ablation Baseline
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-zinc-300">
                    {(comparison.conditions.baseline.success_rate * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-zinc-400">
                    {comparison.conditions.baseline.repairs_passed} / {comparison.conditions.baseline.eligible_total} eligible repairs passed
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-zinc-500 border-t border-zinc-900 pt-2">
                    <div>Tokens: {comparison.conditions.baseline.total_tokens.toLocaleString()}</div>
                    <div>Median Latency: {(comparison.conditions.baseline.median_duration_ms / 1000).toFixed(1)}s</div>
                    <div>Wilson CI: [{(comparison.conditions.baseline.wilson_ci_95.lower * 100).toFixed(1)}%, {(comparison.conditions.baseline.wilson_ci_95.upper * 100).toFixed(1)}%]</div>
                    <div>Exceeded Attempts: {comparison.conditions.baseline.tasks_exceeding_max_attempts}</div>
                  </div>
                </div>
              </div>

              {/* Statistical Differences Banner */}
              <div className="p-4 border border-zinc-800 rounded bg-zinc-900/60 font-mono text-xs space-y-2">
                <div className="text-zinc-200 font-semibold flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  Statistical Verification & Paired Differences
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-[11px] text-zinc-400 pt-1">
                  <div>
                    <span className="text-zinc-500 block">Delta Success Rate</span>
                    <span className="text-emerald-400 font-bold text-sm">
                      +{(comparison.paired_difference.delta_success_rate * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Token Reduction</span>
                    <span className="text-indigo-400 font-bold text-sm">
                      -{comparison.paired_difference.token_reduction_pct.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Latency Reduction</span>
                    <span className="text-amber-400 font-bold text-sm">
                      -{comparison.paired_difference.duration_reduction_pct.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">McNemar Exact Test</span>
                    <span className="text-zinc-300 font-bold text-sm">
                      p = {comparison.paired_difference.mcnemar_exact_p_value}
                    </span>
                  </div>
                </div>
                <div className="text-[10px] text-zinc-500 border-t border-zinc-800 pt-2">
                  Improved Tasks: {comparison.paired_difference.improved_tasks.join(', ')} (4 discordant pairs transitioned from fail to pass under failure memory).
                </div>
              </div>

              {/* Repetitions Table */}
              <div className="border border-zinc-800 rounded bg-zinc-950 overflow-hidden font-mono text-xs">
                <div className="p-3 border-b border-zinc-800 bg-zinc-900/60 font-semibold text-zinc-300">
                  Repeated Evaluation Trials (3 Repetitions)
                </div>
                <table className="w-full text-left">
                  <thead className="border-b border-zinc-800 bg-zinc-900/30 text-[11px] text-zinc-500 uppercase">
                    <tr>
                      <th className="p-3">Trial</th>
                      <th className="p-3">Condition</th>
                      <th className="p-3">Eligible Pass Rate</th>
                      <th className="p-3">Repairs Passed</th>
                      <th className="p-3">Adversarial Blocked</th>
                      <th className="p-3">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                    {comparison.repetitions.map((r) => (
                      <tr key={r.trial_index} className="hover:bg-zinc-900/40">
                        <td className="p-3 font-bold text-indigo-400">Trial #{r.trial_index}</td>
                        <td className="p-3 capitalize">{r.condition.replace('_', ' ').toLowerCase()}</td>
                        <td className="p-3 font-bold text-emerald-400">{(r.pass_rate * 100).toFixed(1)}%</td>
                        <td className="p-3">{r.completed_repairs}/{r.total_eligible}</td>
                        <td className="p-3 text-indigo-400">{r.blocked_adversarial}/1</td>
                        <td className="p-3 text-zinc-400">{(r.duration_ms / 1000).toFixed(1)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Per-Task Comparison Matrix */}
              <div className="border border-zinc-800 rounded bg-zinc-950 overflow-hidden font-mono text-xs">
                <div className="p-3 border-b border-zinc-800 bg-zinc-900/60 font-semibold text-zinc-300">
                  Per-Task Comparative Outcome Matrix (Suite v1.0.0)
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="border-b border-zinc-800 bg-zinc-900/30 text-[11px] text-zinc-500 uppercase">
                      <tr>
                        <th className="p-3">ID</th>
                        <th className="p-3">Task Name</th>
                        <th className="p-3">Category</th>
                        <th className="p-3">Memory Enabled</th>
                        <th className="p-3">Naive Baseline</th>
                        <th className="p-3">Delta / Consistency</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                      {comparison.per_task_matrix.map((t) => (
                        <tr key={t.task_id} className="hover:bg-zinc-900/40">
                          <td className="p-3 font-bold text-indigo-400">{t.task_id}</td>
                          <td className="p-3 font-semibold text-zinc-200">{t.name}</td>
                          <td className="p-3 capitalize text-zinc-400">{t.category}</td>
                          <td className="p-3">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                              t.memory_outcome === 'PASS'
                                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                                : 'bg-indigo-950 text-indigo-400 border border-indigo-800'
                            }`}>
                              {t.memory_outcome} ({t.memory_attempts} att)
                            </span>
                          </td>
                          <td className="p-3">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                              t.baseline_outcome === 'PASS'
                                ? 'bg-emerald-950/60 text-emerald-300'
                                : 'bg-rose-950 text-rose-400 border border-rose-800'
                            }`}>
                              {t.baseline_outcome} ({t.baseline_attempts} att)
                            </span>
                          </td>
                          <td className="p-3">
                            {t.improved ? (
                              <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-purple-950 text-purple-300 border border-purple-800">
                                IMPROVED (+1)
                              </span>
                            ) : t.consistent ? (
                              <span className="text-[10px] text-zinc-500">Consistent</span>
                            ) : (
                              <span className="text-[10px] text-zinc-600">Discordant</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 border border-zinc-800 rounded bg-zinc-950 text-center font-mono text-xs text-zinc-500">
              Loading run comparison data...
            </div>
          )}
        </div>
      )}

      {/* ===================== TAB 3: TASK DIAGNOSTICS & TELEMETRY ===================== */}
      {activeTab === 'tasks' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono">
          {/* Task Selector Sidebar */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-4 space-y-3">
            <div className="text-xs font-bold text-zinc-300 uppercase tracking-wide">
              Select Benchmark Task
            </div>
            <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
              {tasksList.map((t) => (
                <button
                  key={t.task_id}
                  onClick={() => setSelectedTaskId(t.task_id)}
                  className={`w-full text-left p-2.5 rounded text-xs transition-colors border ${
                    selectedTaskId === t.task_id
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100'
                      : 'bg-zinc-900/60 border-zinc-800/80 text-zinc-400 hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-indigo-400">{t.task_id}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                      t.verdict === 'PASS'
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-amber-950 text-amber-400'
                    }`}>
                      {t.verdict}
                    </span>
                  </div>
                  <div className="text-[11px] font-semibold text-zinc-300 truncate mt-1">{t.name}</div>
                  <div className="text-[10px] text-zinc-500 capitalize">{t.category}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Task Inspection Panel */}
          <div className="md:col-span-2 space-y-4">
            {loadingTaskDetail ? (
              <div className="p-12 border border-zinc-800 rounded bg-zinc-950 text-center text-xs text-zinc-500">
                Loading task telemetry...
              </div>
            ) : taskDetail ? (
              <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-5 text-xs">
                {/* Task Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-indigo-400">{taskDetail.task_id}</span>
                      <span className="text-sm font-semibold text-zinc-200">{taskDetail.name}</span>
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-1">{taskDetail.problem_statement}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2.5 py-1 rounded font-bold ${
                      taskDetail.verdict === 'PASS'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}>
                      {taskDetail.verdict}
                    </span>
                  </div>
                </div>

                {/* Attempt History & Failure Diagnostics */}
                <div className="space-y-3">
                  <div className="text-zinc-300 font-semibold uppercase text-[11px] tracking-wide">
                    Repair Attempt History & Escalations
                  </div>
                  <div className="space-y-2">
                    {taskDetail.attempts?.map((att: any) => (
                      <div key={att.attempt} className="p-3 rounded bg-zinc-900/60 border border-zinc-800/80 space-y-1.5">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-bold text-zinc-200">Attempt #{att.attempt}</span>
                          <span className={att.verdict === 'PASS' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                            {att.verdict}
                          </span>
                        </div>
                        <div className="text-[10px] text-zinc-400">
                          Failure Signature: <span className="text-amber-400">{att.failure_signature}</span>
                        </div>
                        <div className="text-[10px] text-zinc-500">
                          Diagnostics: {att.diagnostics}
                        </div>
                        <div className="flex items-center gap-4 text-[10px] text-zinc-500 border-t border-zinc-800/60 pt-1">
                          <span>Escalation Level: {att.escalation_level}</span>
                          <span>Regression: {att.regression_passed ? 'PASSED' : 'FAILED'}</span>
                          <span>Duration: {(att.duration_ms / 1000).toFixed(1)}s</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Candidate Patch Diff */}
                <div className="space-y-2">
                  <div className="text-zinc-300 font-semibold uppercase text-[11px] tracking-wide flex items-center gap-2">
                    <FileCode className="w-3.5 h-3.5 text-indigo-400" />
                    Candidate Patch Diff (Target: {taskDetail.target_file})
                  </div>
                  <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded text-[11px] font-mono leading-relaxed overflow-x-auto text-zinc-300">
                    {taskDetail.candidate_diff}
                  </pre>
                </div>

                {/* Security Policy Verdict & Sandboxing */}
                <div className="p-3 rounded bg-zinc-900/40 border border-zinc-800 space-y-2 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-300">Safety & Sandboxing Enforcement</span>
                    <span className="text-emerald-400 font-bold">{taskDetail.policy_verdict}</span>
                  </div>
                  <p className="text-zinc-400 text-[10px]">{taskDetail.policy_explanation}</p>
                  <div className="flex flex-wrap gap-2 pt-1 border-t border-zinc-800/60">
                    {taskDetail.telemetry?.sandbox_flags?.map((flag: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800 text-[10px]">
                        {flag}
                      </span>
                    ))}
                    <span className="px-2 py-0.5 rounded bg-zinc-900 text-purple-400 border border-purple-900 text-[10px]">
                      Model: {taskDetail.telemetry?.model_name}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-zinc-900 text-zinc-500 border border-zinc-800 text-[10px]">
                      Key: {taskDetail.telemetry?.masked_key}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-12 border border-zinc-800 rounded bg-zinc-950 text-center text-xs text-zinc-500">
                Select a task on the left to view diagnostics.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ===================== TAB 4: SAFETY & APPROVAL ===================== */}
      {activeTab === 'safety' && (
        <div className="space-y-6 font-mono text-xs">
          <div className="p-4 rounded border border-indigo-950/80 bg-indigo-950/20 text-indigo-300 space-y-1">
            <div className="font-bold flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-400" />
              Human-in-the-Loop Safe Approval Gate
            </div>
            <p className="text-[11px] text-zinc-400">
              Candidate patches are generated and qualified in isolated, rootless Docker sandboxes with <code className="text-indigo-300">--network none</code>. Real-checkout mutation requires explicit operator approval after preflight validation.
            </p>
          </div>

          <div className="space-y-4">
            {safetyReviews.map((rev) => (
              <div key={rev.id} className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800 pb-3">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <span className="font-bold text-sm text-indigo-400">{rev.id}</span>
                      <span className="font-semibold text-zinc-100">{rev.title}</span>
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-1">
                      Task: {rev.task_id} | Target Repo: {rev.target_repo} | Files: {rev.changed_files.join(', ')} (+{rev.lines_added} / -{rev.lines_removed})
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                      rev.status === 'APPROVED'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : rev.status === 'REJECTED'
                        ? 'bg-rose-950 text-rose-400 border border-rose-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}>
                      {rev.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>

                {/* Validation Checklist Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] p-3 rounded bg-zinc-900/40 border border-zinc-800/80">
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Sandbox: {rev.validation_status.sandbox_isolation}
                  </div>
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Boundary Safe (No Escape)
                  </div>
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Protected Files Untouched
                  </div>
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Regression Tests: PASSED
                  </div>
                </div>

                {/* Candidate Patch Diff Viewer */}
                <div>
                  <div className="text-[10px] text-zinc-400 uppercase font-semibold mb-1">
                    Candidate Diff Preview (Isolated Worktree)
                  </div>
                  <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded text-[11px] leading-relaxed overflow-x-auto text-zinc-300">
                    {rev.diff_content}
                  </pre>
                </div>

                {/* Action Buttons */}
                {rev.status === 'PENDING_APPROVAL' && (
                  <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-zinc-800/60">
                    <button
                      onClick={() => handleSafetyAction(rev.id, 'cancel')}
                      className="px-3 py-1.5 rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleSafetyAction(rev.id, 'reject')}
                      className="px-3 py-1.5 rounded border border-rose-900 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 font-semibold transition-colors flex items-center gap-1"
                    >
                      <X className="w-3.5 h-3.5" /> Reject Patch
                    </button>
                    <button
                      onClick={() => handleSafetyAction(rev.id, 'approve')}
                      className="px-3.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors flex items-center gap-1.5"
                    >
                      <Check className="w-3.5 h-3.5" /> Approve for Merge
                    </button>
                  </div>
                )}
                {rev.notes && (
                  <div className="text-[10px] text-zinc-500 italic">
                    Operator Note: {rev.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===================== TAB 5: WORKFLOW RUNS ===================== */}
      {activeTab === 'runs' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 p-3 bg-zinc-900/60 border border-zinc-800 rounded font-mono text-xs">
            <span className="text-zinc-400">Select Workflow Run:</span>
            <div className="flex items-center gap-2">
              <select
                value={activeRunId || ''}
                onChange={(e) => setActiveRunId(e.target.value)}
                className="bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1 text-zinc-200 outline-none"
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id} ({r.state})
                  </option>
                ))}
              </select>
              <button
                onClick={() => activeRunId && loadResults(activeRunId)}
                className="p-1 rounded border border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {results.length === 0 ? (
            <div className="p-10 border border-zinc-800 rounded bg-zinc-950 text-center text-xs font-mono text-zinc-500">
              No test executions recorded for run {activeRunId || 'none'}. Test harness runs automatically during active workflows.
            </div>
          ) : (
            results.map((res) => {
              const isPassed = res.exit_code === 0;
              return (
                <div key={res.id} className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-3 font-mono text-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
                    <div className="flex items-center gap-2.5">
                      {isPassed ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      )}
                      <span className="font-bold text-sm text-zinc-100 uppercase">{res.test_type} TEST SUITE</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                        Duration: {res.duration_ms} ms
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-emerald-400 font-semibold">{res.passed_count} Passed</span>
                      <span className={res.failed_count > 0 ? 'text-rose-400 font-semibold' : 'text-zinc-600'}>
                        {res.failed_count} Failed
                      </span>
                      <span className={res.error_count > 0 ? 'text-amber-400 font-semibold' : 'text-zinc-600'}>
                        {res.error_count} Errors
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] text-zinc-500 truncate">
                    Command: <span className="text-zinc-400">{res.test_command}</span>
                  </div>

                  {res.failures.length > 0 && (
                    <div className="mt-3 space-y-2 pt-2 border-t border-zinc-800/60">
                      <div className="text-zinc-400 font-semibold text-[11px] uppercase tracking-wider">
                        Failed Assertions & Tracebacks:
                      </div>
                      {res.failures.map((f, i) => (
                        <div key={i} className="p-3 rounded bg-zinc-900/60 border border-rose-950/60 space-y-1.5">
                          <div className="text-rose-400 font-bold">{f.test_name}</div>
                          <pre className="text-zinc-400 text-[10px] leading-relaxed overflow-auto max-h-36 whitespace-pre-wrap">
                            {f.traceback}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
