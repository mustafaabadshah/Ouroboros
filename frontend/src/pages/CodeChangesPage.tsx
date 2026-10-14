import React, { useState, useEffect } from 'react';
import { GitMerge, XCircle, CheckCircle2, ShieldAlert, FileCode, RefreshCw } from 'lucide-react';
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Candidate Code Changes</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Isolated Git worktree patch inspection, AST syntax validation, and explicit human merge gates.
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
            onClick={() => activeRunId && loadDiff(activeRunId)}
            className="p-1 rounded border border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {diffData && (
        <div className="space-y-6">
          {/* Header Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
              <div className="text-zinc-500">LINE MODIFICATIONS</div>
              <div className="text-sm font-bold text-zinc-200">
                <span className="text-emerald-400">+{diffData.lines_added}</span> /{' '}
                <span className="text-rose-400">-{diffData.lines_removed}</span>
              </div>
            </div>

            <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
              <div className="text-zinc-500">FILES MODIFIED</div>
              <div className="text-sm font-bold text-zinc-200">{diffData.changed_files.length} Files</div>
            </div>

            <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
              <div className="text-zinc-500">ATTEMPT / HASH</div>
              <div className="text-sm font-bold text-zinc-200 truncate">
                Attempt {diffData.attempt} ({diffData.diff_hash ? diffData.diff_hash.slice(0, 8) : 'N/A'})
              </div>
            </div>

            <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
              <div className="text-zinc-500">JUDGE VERDICT</div>
              <div className="text-sm font-bold text-zinc-200">
                {currentRun ? <StatusBadge status={currentRun.verdict || currentRun.state} size="sm" /> : 'None'}
              </div>
            </div>
          </div>

          {/* Protected File Warning */}
          {diffData.protected_files_affected.length > 0 && (
            <div className="p-4 rounded border border-rose-800/80 bg-rose-950/40 text-xs font-mono text-rose-300 flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
              <div>
                <span className="font-bold">CRITICAL SAFETY ALERT:</span> This patch touches protected engine files:{' '}
                {diffData.protected_files_affected.join(', ')}. Automated merge is blocked.
              </div>
            </div>
          )}

          {/* Unified Diff View */}
          <DiffViewer diffText={diffData.diff_content} maxHeight="max-h-[550px]" />

          {/* Human Review Approval Action Bar */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold font-mono text-zinc-100">HUMAN APPROVAL GATE</h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Project Ouroboros will NEVER merge candidate patches without your explicit human confirmation.
                </p>
              </div>

              {currentRun && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleRejectMerge}
                    disabled={actionInProgress}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-rose-800 bg-rose-950/60 text-rose-300 hover:bg-rose-900 transition disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" /> Reject & Discard
                  </button>
                  <button
                    onClick={handleApproveMerge}
                    disabled={actionInProgress || currentRun.state !== 'AWAITING_APPROVAL'}
                    className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono font-bold rounded bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <GitMerge className="w-4 h-4" /> Approve & Merge into Main
                  </button>
                </div>
              )}
            </div>

            <input
              type="text"
              value={approvalNotes}
              onChange={(e) => setApprovalNotes(e.target.value)}
              placeholder="Operator review notes or audit rationale (Optional)..."
              className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-200 outline-none focus:border-zinc-700"
            />
          </div>
        </div>
      )}
    </div>
  );
};
