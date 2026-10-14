import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Terminal, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { TestResult, Run } from '../types';
import { StatusBadge } from '../components/StatusBadge';

interface EvaluationLabPageProps {
  selectedRunId: string | null;
}

export const EvaluationLabPage: React.FC<EvaluationLabPageProps> = ({ selectedRunId }) => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(selectedRunId);
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedFailure, setSelectedFailure] = useState<{ test_name: string; traceback: string } | null>(null);

  useEffect(() => {
    loadRuns();
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

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Deterministic Evaluation Lab</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Pytest baseline benchmarks, candidate acceptance runs, and regression gate verification.
          </p>
        </div>

        {/* Run Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-zinc-500">Run:</span>
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

      <div className="space-y-4">
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

                {/* Failures List */}
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
    </div>
  );
};
