import React, { useState, useEffect } from 'react';
import { History, Download, Trash2, AlertCircle, RefreshCw, Filter } from 'lucide-react';
import { api } from '../services/api';
import { FailureTrajectory } from '../types';
import { StatusBadge } from '../components/StatusBadge';

export const FailureTrajectoriesPage: React.FC = () => {
  const [trajectories, setTrajectories] = useState<FailureTrajectory[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTrajectory, setSelectedTrajectory] = useState<FailureTrajectory | null>(null);
  const [filterTicket, setFilterTicket] = useState('');

  useEffect(() => {
    loadTrajectories();
  }, []);

  const loadTrajectories = async () => {
    try {
      setLoading(true);
      const data = await api.getFailures();
      setTrajectories(data);
      if (data.length > 0 && !selectedTrajectory) {
        setSelectedTrajectory(data[0]);
      }
    } catch (e) {
      console.error('Error loading trajectories:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    window.open('/api/failures/export', '_blank');
  };

  const handleDelete = async (id: string) => {
    if (confirm(`Delete failure record ${id}?`)) {
      try {
        await api.deleteFailure(id);
        await loadTrajectories();
      } catch (e) {
        alert(`Delete failed: ${e}`);
      }
    }
  };

  const filtered = filterTicket
    ? trajectories.filter((t) => t.ticket_id.toLowerCase().includes(filterTicket.toLowerCase()))
    : trajectories;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Failure Trajectory Memory</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Persistent episodic memory of broken candidate patches, tracebacks, AST diffs, and repair hypotheses.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
          >
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
          <button
            onClick={loadTrajectories}
            className="p-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left List */}
        <div className="space-y-3">
          <div className="relative">
            <input
              type="text"
              value={filterTicket}
              onChange={(e) => setFilterTicket(e.target.value)}
              placeholder="Filter by Ticket ID..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-xs font-mono text-zinc-200 outline-none focus:border-zinc-700"
            />
          </div>

          <div className="border border-zinc-800 rounded bg-zinc-950 divide-y divide-zinc-800/80 max-h-[650px] overflow-auto">
            {filtered.length === 0 ? (
              <div className="p-6 text-center text-xs text-zinc-500 font-mono">
                No failure trajectories recorded. Broken candidates will be automatically indexed here.
              </div>
            ) : (
              filtered.map((t) => {
                const isSelected = t.id === selectedTrajectory?.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTrajectory(t)}
                    className={`p-4 cursor-pointer transition ${
                      isSelected ? 'bg-zinc-900 border-l-2 border-purple-500' : 'hover:bg-zinc-900/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-zinc-200">{t.id}</span>
                      <StatusBadge status={t.status} size="sm" />
                    </div>
                    <div className="text-[11px] font-mono text-zinc-400">
                      Ticket: {t.ticket_id} | Attempt {t.attempt}
                    </div>
                    <div className="text-[10px] font-mono text-zinc-500 truncate mt-1">
                      Failed: {t.failed_tests.join(', ') || 'Test Assertion'}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Details View */}
        {selectedTrajectory && (
          <div className="lg:col-span-2 border border-zinc-800 rounded bg-zinc-950 p-6 space-y-5 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-zinc-100">{selectedTrajectory.id}</span>
                  <StatusBadge status={selectedTrajectory.status} />
                </div>
                <div className="text-[11px] text-zinc-500 mt-0.5">
                  Ticket: {selectedTrajectory.ticket_id} | Attempt #{selectedTrajectory.attempt} | Model:{' '}
                  {selectedTrajectory.model || 'local'}
                </div>
              </div>

              <button
                onClick={() => handleDelete(selectedTrajectory.id)}
                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-rose-900/60 text-rose-400 hover:bg-rose-950/40 transition"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            </div>

            {/* Traceback Box */}
            <div className="space-y-1.5">
              <span className="text-zinc-400 font-bold uppercase text-[11px]">Failed Assertions & Traceback</span>
              <pre className="p-3.5 rounded bg-zinc-900/70 border border-zinc-800 text-zinc-300 text-[11px] leading-relaxed overflow-auto max-h-52 whitespace-pre-wrap">
                {selectedTrajectory.traceback_excerpt || 'No captured traceback.'}
              </pre>
            </div>

            {/* Root Cause Hypothesis & Repair Hint */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <span className="text-zinc-400 font-bold uppercase text-[11px]">Root-Cause Hypothesis</span>
                <p className="p-3 rounded bg-zinc-900/40 border border-zinc-800 text-zinc-300 text-[11px] leading-relaxed">
                  {selectedTrajectory.root_cause_hypothesis || 'Assertion mismatch in candidate implementation.'}
                </p>
              </div>

              <div className="space-y-1.5">
                <span className="text-zinc-400 font-bold uppercase text-[11px]">Repair Hint</span>
                <p className="p-3 rounded bg-zinc-900/40 border border-zinc-800 text-zinc-300 text-[11px] leading-relaxed">
                  {selectedTrajectory.repair_hint || 'Verify syntax and expected return types.'}
                </p>
              </div>
            </div>

            {/* Patch Hash */}
            <div className="p-3 rounded bg-zinc-900/40 border border-zinc-800 text-zinc-400 text-[11px]">
              Patch Hash: <span className="text-zinc-200">{selectedTrajectory.patch_hash || 'N/A'}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
