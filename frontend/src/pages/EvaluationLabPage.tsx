import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Terminal,
  RefreshCw,
  Play,
  Download,
  BarChart2,
  Cpu,
  Layers,
  ShieldCheck,
  Brain
} from 'lucide-react';
import { api } from '../services/api';
import { TestResult, Run } from '../types';

interface EvaluationLabPageProps {
  selectedRunId: string | null;
}

export const EvaluationLabPage: React.FC<EvaluationLabPageProps> = ({ selectedRunId }) => {
  const [activeTab, setActiveTab] = useState<'benchmarks' | 'runs'>('benchmarks');
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(selectedRunId);
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);

  // Benchmark state
  const [metrics, setMetrics] = useState<any>(null);
  const [benchmarkTasks, setBenchmarkTasks] = useState<any[]>([]);
  const [benchmarkResults, setBenchmarkResults] = useState<any>(null);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);

  useEffect(() => {
    loadRuns();
    loadEvaluationData();
  }, []);

  useEffect(() => {
    if (activeRunId) {
      loadResults(activeRunId);
    }
  }, [activeRunId]);

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
      setLoading(true);
      const res = await api.getRunResults(runId);
      setResults(res);
    } catch (e) {
      console.error('Error loading test results:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadEvaluationData = async () => {
    try {
      const [m, tasks] = await Promise.all([
        api.getEvaluationMetrics().catch(() => null),
        api.getBenchmarkTasks().catch(() => [])
      ]);
      setMetrics(m);
      setBenchmarkTasks(tasks);
    } catch (e) {
      console.error('Error loading evaluation lab data:', e);
    }
  };

  const handleRunBenchmark = async () => {
    try {
      setRunningBenchmark(true);
      const res = await api.runBenchmarkSuite(memoryEnabled);
      setBenchmarkResults(res);
      await loadEvaluationData();
    } catch (e) {
      console.error('Error running benchmark:', e);
    } finally {
      setRunningBenchmark(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Deterministic Evaluation Lab</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Standardized bug-fix benchmarks, failure memory ablation, and honest metrics.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2">
          <div className="bg-zinc-900 border border-zinc-800 rounded p-0.5 flex">
            <button
              onClick={() => setActiveTab('benchmarks')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'benchmarks' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Benchmark Suite v1.0
            </button>
            <button
              onClick={() => setActiveTab('runs')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'runs' ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Live Workflow Runs
            </button>
          </div>
          <button
            onClick={loadEvaluationData}
            className="p-1.5 rounded border border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
            title="Refresh Metrics"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {activeTab === 'benchmarks' ? (
        <div className="space-y-6">
          {/* Metrics Summary Cards */}
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-1">
                <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                  <BarChart2 className="w-3.5 h-3.5 text-emerald-400" /> Repair Success Rate
                </div>
                <div className="text-2xl font-bold font-mono text-emerald-400">
                  {(metrics.repair_success_rate * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-zinc-500">
                  {metrics.passing_runs_count} passed / {metrics.eligible_attempted_runs} attempted
                </div>
              </div>

              <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-1">
                <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" /> Regression Rate
                </div>
                <div className="text-2xl font-bold font-mono text-indigo-400">
                  {(metrics.regression_rate * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-zinc-500">
                  {metrics.runs_with_regression} regressions detected
                </div>
              </div>

              <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-1">
                <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-amber-400" /> Candidate Pass Rate
                </div>
                <div className="text-2xl font-bold font-mono text-amber-400">
                  {(metrics.candidate_test_pass_rate * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-zinc-500">
                  {metrics.passed_candidate_test_executions} / {metrics.total_candidate_test_executions} test runs
                </div>
              </div>

              <div className="p-4 rounded border border-zinc-800 bg-zinc-950 space-y-1">
                <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
                  <Brain className="w-3.5 h-3.5 text-purple-400" /> Failure Flywheel Memory
                </div>
                <div className="text-2xl font-bold font-mono text-purple-400">
                  {metrics.total_failure_trajectories_recorded}
                </div>
                <div className="text-[10px] text-zinc-500">
                  {metrics.repeated_failures_prevented} duplicate loops caught
                </div>
              </div>
            </div>
          )}

          {/* Benchmark Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border border-zinc-800 rounded bg-zinc-900/60 font-mono text-xs">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                <input
                  type="checkbox"
                  checked={memoryEnabled}
                  onChange={(e) => setMemoryEnabled(e.target.checked)}
                  className="rounded border-zinc-700 bg-zinc-950 text-indigo-500 focus:ring-0"
                />
                <span>Failure Memory Enabled (Ablation Control)</span>
              </label>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                onClick={handleRunBenchmark}
                disabled={runningBenchmark}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors disabled:opacity-50"
              >
                {runningBenchmark ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running Tasks...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" /> Run Benchmark Suite
                  </>
                )}
              </button>

              <a
                href={api.exportBenchmarkUrl(memoryEnabled)}
                download="ouroboros_benchmark_results.json"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800 transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Export JSON
              </a>
            </div>
          </div>

          {/* Benchmark Results Display */}
          {benchmarkResults && (
            <div className="p-4 border border-emerald-950/60 bg-emerald-950/20 rounded font-mono text-xs space-y-2">
              <div className="text-emerald-400 font-bold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> Benchmark Suite Execution Complete
              </div>
              <div className="text-zinc-300 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                <div>Tasks: {benchmarkResults.total_tasks}</div>
                <div className="text-emerald-400">Passed: {benchmarkResults.passed_tasks}</div>
                <div className="text-amber-400">Blocked: {benchmarkResults.blocked_tasks}</div>
                <div>Median Latency: {benchmarkResults.median_duration_ms}ms</div>
              </div>
            </div>
          )}

          {/* Benchmark Task Table */}
          <div className="border border-zinc-800 rounded bg-zinc-950 overflow-hidden font-mono text-xs">
            <div className="p-3 border-b border-zinc-800 bg-zinc-900/60 font-semibold text-zinc-300 flex items-center justify-between">
              <span>Standardized Benchmark Tasks (Suite v1.0.0)</span>
              <span className="text-[11px] text-zinc-500">{benchmarkTasks.length} tasks registered</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="border-b border-zinc-800 bg-zinc-900/30 text-[11px] text-zinc-500 uppercase">
                  <tr>
                    <th className="p-3">ID</th>
                    <th className="p-3">Task Name</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Target File</th>
                    <th className="p-3">Expected Outcome</th>
                    <th className="p-3">Repair Budget</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                  {benchmarkTasks.map((t) => (
                    <tr key={t.task_id} className="hover:bg-zinc-900/40">
                      <td className="p-3 font-bold text-indigo-400">{t.task_id}</td>
                      <td className="p-3">
                        <div className="font-semibold text-zinc-200">{t.name}</div>
                        <div className="text-[11px] text-zinc-500 truncate max-w-xs">{t.problem_statement}</div>
                      </td>
                      <td className="p-3 capitalize">{t.category}</td>
                      <td className="p-3 text-zinc-400">{t.target_file}</td>
                      <td className="p-3">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                            t.expected_initial_verdict === 'BLOCKED'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-rose-950 text-rose-400 border border-rose-800'
                          }`}
                        >
                          INITIAL: {t.expected_initial_verdict}
                        </span>
                      </td>
                      <td className="p-3 text-zinc-400">{t.max_repair_budget} attempts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Live Runs Tab */
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 p-3 bg-zinc-900/60 border border-zinc-800 rounded">
            <span className="text-xs font-mono text-zinc-400">Select Workflow Run:</span>
            <div className="flex items-center gap-2">
              <select
                value={activeRunId || ''}
                onChange={(e) => setActiveRunId(e.target.value)}
                className="bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1 text-xs font-mono text-zinc-200 outline-none"
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
