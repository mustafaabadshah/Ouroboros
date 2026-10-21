import React, { useState, useEffect } from 'react';
import {
  GitMerge,
  XCircle,
  CheckCircle2,
  ShieldAlert,
  FileCode,
  RefreshCw,
  GitBranch,
  ShieldCheck,
  Check,
  Clock,
  Sparkles,
  Layers,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';
import { DiffInspection, Run } from '../types';
import { DiffViewer } from '../components/DiffViewer';
import { StatusBadge } from '../components/StatusBadge';

interface CodeChangesPageProps {
  selectedRunId: string | null;
}

export const CodeChangesPage: React.FC<CodeChangesPageProps> = ({ selectedRunId }) => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(selectedRunId);
  const [diffData, setDiffData] = useState<DiffInspection | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [approvalNotes, setApprovalNotes] = useState('');

  useEffect(() => {
    loadRuns();
  }, []);

  useEffect(() => {
    if (activeRunId) {
      loadDiff(activeRunId);
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
      console.error('Error loading runs:', e);
    }
  };

  const loadDiff = async (runId: string) => {
    try {
      setLoading(true);
      const diff = await api.getRunDiff(runId);
      setDiffData(diff);
    } catch (e) {
      console.error('Error fetching diff:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveMerge = async () => {
    if (!activeRunId) return;
    if (!confirm('Explicit Human Gate: Confirm merge of this candidate patch into the target repository main branch?')) {
      return;
    }

    try {
      setActionInProgress(true);
      const res = await api.approveMerge(activeRunId, approvalNotes);
      alert(res.message);
      await loadRuns();
      await loadDiff(activeRunId);
    } catch (e) {
      alert(`Merge failed: ${e}`);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleRejectMerge = async () => {
    if (!activeRunId) return;
    if (!confirm('Confirm rejection of this candidate patch? The isolated worktree will be safely discarded.')) {
      return;
    }

    try {
      setActionInProgress(true);
      const res = await api.rejectMerge(activeRunId, approvalNotes);
      alert(res.message);
      await loadRuns();
      await loadDiff(activeRunId);
    } catch (e) {
      alert(`Reject failed: ${e}`);
    } finally {
      setActionInProgress(false);
    }
  };

  const currentRun = runs.find((r) => r.id === activeRunId);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
              AUDIT & SAFETY GATE
            </span>
            <span className="text-zinc-500 text-xs font-mono">•</span>
            <span className="text-zinc-400 text-xs font-mono">ISOLATED WORKTREE DIFF</span>
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-zinc-100 flex items-center gap-2">
            Candidate Code Changes
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Isolated Git worktree patch inspection, AST syntax validation, and explicit human merge gates.
          </p>
        </div>

        {/* Run Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-zinc-400">Target Run:</span>
          <select
            value={activeRunId || ''}
            onChange={(e) => setActiveRunId(e.target.value)}
            className="bg-zinc-900 border border-zinc-700/80 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 outline-none focus:border-emerald-500 shadow-sm"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id} — [{r.state}] {r.verdict ? `(${r.verdict})` : ''}
              </option>
            ))}
          </select>
          <button
            onClick={() => activeRunId && loadDiff(activeRunId)}
            className="p-2 rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 transition"
            title="Refresh Diff"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {diffData ? (
        <div className="space-y-6">
          {/* Header Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div className="glass-panel p-4 rounded-xl space-y-1">
              <div className="text-zinc-500 text-[10px]">LINE MODIFICATIONS</div>
              <div className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <span className="text-emerald-400 font-mono">+{diffData.lines_added}</span>
                <span className="text-zinc-600">/</span>
                <span className="text-rose-400 font-mono">-{diffData.lines_removed}</span>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl space-y-1">
              <div className="text-zinc-500 text-[10px]">FILES MODIFIED</div>
              <div className="text-base font-bold text-zinc-200 flex items-center gap-1.5">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span>{diffData.changed_files.length} Files</span>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl space-y-1">
              <div className="text-zinc-500 text-[10px]">ATTEMPT / HASH</div>
              <div className="text-sm font-bold text-zinc-200 truncate font-mono">
                Attempt {diffData.attempt} ({diffData.diff_hash ? diffData.diff_hash.slice(0, 8) : 'clean'})
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl space-y-1">
              <div className="text-zinc-500 text-[10px]">VERDICT STATE</div>
              <div className="text-sm font-bold text-zinc-200 mt-1">
                {currentRun ? <StatusBadge status={currentRun.verdict || currentRun.state} size="sm" /> : 'None'}
              </div>
            </div>
          </div>

          {/* Protected File Warning */}
          {diffData.protected_files_affected.length > 0 && (
            <div className="p-4 rounded-xl border border-rose-800/80 bg-rose-950/40 text-xs font-mono text-rose-300 flex items-center gap-3 shadow-lg">
              <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 animate-pulse" />
              <div>
                <span className="font-bold">CRITICAL SAFETY ALERT:</span> This patch touches protected engine files:{' '}
                {diffData.protected_files_affected.join(', ')}. Automated merge is blocked.
              </div>
            </div>
          )}

          {/* Unified Diff View */}
          <div className="glass-panel rounded-xl overflow-hidden border border-zinc-800 shadow-2xl">
            <div className="px-4 py-3 bg-zinc-900/80 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-emerald-400" />
                <span className="font-mono text-xs font-bold text-zinc-200">Unified Patch Diff (Git Format)</span>
              </div>
              <span className="text-[11px] font-mono text-zinc-400">
                {diffData.changed_files.join(', ') || 'No file changes'}
              </span>
            </div>
            <div className="p-4 bg-black/90">
              <DiffViewer diffText={diffData.diff_content} maxHeight="max-h-[550px]" />
            </div>
          </div>

          {/* Human Review Approval Action Bar */}
          <div className="glass-panel rounded-xl p-6 space-y-4 border border-zinc-800 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-bold font-mono text-zinc-100">HUMAN-IN-THE-LOOP APPROVAL GATE</h3>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  Project Ouroboros will NEVER merge candidate patches without your explicit human confirmation.
                </p>
              </div>

              {currentRun && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleRejectMerge}
                    disabled={actionInProgress}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono rounded-lg border border-rose-800 bg-rose-950/60 text-rose-300 hover:bg-rose-900 transition disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Reject & Discard</span>
                  </button>
                  <button
                    onClick={handleApproveMerge}
                    disabled={actionInProgress || currentRun.state !== 'AWAITING_APPROVAL'}
                    className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/20"
                  >
                    <GitMerge className="w-4 h-4" />
                    <span>Approve & Merge into Main</span>
                  </button>
                </div>
              )}
            </div>

            <input
              type="text"
              value={approvalNotes}
              onChange={(e) => setApprovalNotes(e.target.value)}
              placeholder="Operator review notes or audit rationale (Optional)..."
              className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg px-3.5 py-2 text-xs font-mono text-zinc-200 outline-none focus:border-emerald-500 transition"
            />
          </div>
        </div>
      ) : (
        <div className="glass-panel rounded-xl p-12 text-center text-xs font-mono text-zinc-500 space-y-2">
          <Clock className="w-8 h-8 mx-auto text-zinc-600 mb-2 opacity-50" />
          <p>No candidate patch diff found for the selected run.</p>
          <p className="text-[11px] text-zinc-600">Select a run that has executed the coding stage.</p>
        </div>
      )}
    </div>
  );
};
