import React, { useState, useEffect } from 'react';
import {
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  History,
  GitBranch,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';
import { MetricsOverview, Run, Ticket } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { TabType } from '../components/Sidebar';

interface OverviewPageProps {
  setCurrentTab: (tab: TabType) => void;
  onSelectRun: (runId: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ setCurrentTab, onSelectRun }) => {
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [recentRuns, setRecentRuns] = useState<Run[]>([]);
  const [pendingTickets, setPendingTickets] = useState<Ticket[]>([]);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [m, r, t, a] = await Promise.all([
        api.getMetricsOverview(),
        api.getRuns(),
        api.getTickets(undefined, 'PROPOSED'),
        api.getAuditEvents(),
      ]);
      setMetrics(m);
      setRecentRuns(r.slice(0, 5));
      setPendingTickets(t.slice(0, 4));
      setAuditEvents(a.slice(0, 6));
    } catch (e) {
      console.error('Error loading overview data:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !metrics) {
    return (
      <div className="p-8 text-center text-zinc-500 font-mono text-xs">
        Loading real-time swarm telemetry...
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Metric Cards Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded border border-zinc-800 bg-zinc-900/50">
          <div className="text-zinc-500 text-xs font-mono uppercase">Total Runs</div>
          <div className="text-2xl font-bold font-mono text-zinc-100 mt-1">{metrics?.total_runs ?? 0}</div>
          <div className="text-[11px] text-zinc-500 mt-1">Autonomous lifecycles</div>
        </div>

        <div className="p-4 rounded border border-zinc-800 bg-zinc-900/50">
          <div className="text-zinc-500 text-xs font-mono uppercase">Acceptance Rate</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {metrics?.acceptance_rate ?? 0}%
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">
            {metrics?.successful_runs ?? 0} accepted / {metrics?.total_runs ?? 0} runs
          </div>
        </div>

        <div className="p-4 rounded border border-zinc-800 bg-zinc-900/50">
          <div className="text-zinc-500 text-xs font-mono uppercase">Failure Trajectories</div>
          <div className="text-2xl font-bold font-mono text-purple-400 mt-1">
            {metrics?.total_trajectories ?? 0}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Persistent repair memory</div>
        </div>

        <div className="p-4 rounded border border-zinc-800 bg-zinc-900/50">
          <div className="text-zinc-500 text-xs font-mono uppercase">System Free RAM</div>
          <div
            className={`text-2xl font-bold font-mono mt-1 ${
              (metrics?.free_ram_mb ?? 2000) < 1500 ? 'text-amber-400' : 'text-zinc-100'
            }`}
          >
            {metrics?.free_ram_mb ?? 0} MB
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">
            CPU: {metrics?.cpu_percent ?? 0}% | Limit: 8 GB
          </div>
        </div>
      </div>

      {/* Main Grid: Pending Approvals & Recent Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Runs & Pending Tickets */}
        <div className="lg:col-span-2 space-y-6">
          {/* Recent Runs */}
          <div className="border border-zinc-800 rounded bg-zinc-950">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-900/40">
              <span className="text-xs font-mono font-semibold text-zinc-300">RECENT AGENT RUNS</span>
              <button
                onClick={() => setCurrentTab('runs')}
                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 font-mono"
              >
                View all runs <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="divide-y divide-zinc-800/80">
              {recentRuns.length === 0 ? (
                <div className="p-6 text-center text-xs text-zinc-500 font-mono">
                  No active or past agent runs recorded.
                </div>
              ) : (
                recentRuns.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => {
                      onSelectRun(r.id);
                      setCurrentTab('runs');
                    }}
                    className="p-4 flex items-center justify-between hover:bg-zinc-900/50 cursor-pointer transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-zinc-200">{r.id}</span>
                        <StatusBadge status={r.state} size="sm" />
                      </div>
                      <div className="text-[11px] text-zinc-500 font-mono mt-1">
                        Ticket: {r.ticket_id} | Agent: {r.active_agent || 'Orchestrator'}
                      </div>
                    </div>
                    <div className="text-right font-mono text-[11px] text-zinc-400">
                      <div>{r.verdict ? `Verdict: ${r.verdict}` : 'In Progress'}</div>
                      <div className="text-zinc-600">Retries: {r.retry_count}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Pending Ticket Approvals */}
          <div className="border border-zinc-800 rounded bg-zinc-950">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-900/40">
              <span className="text-xs font-mono font-semibold text-zinc-300">TICKETS AWAITING REVIEW</span>
              <button
                onClick={() => setCurrentTab('tickets')}
                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 font-mono"
              >
                Browse tickets <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="divide-y divide-zinc-800/80">
              {pendingTickets.length === 0 ? (
                <div className="p-6 text-center text-xs text-zinc-500 font-mono">
                  No tickets currently awaiting review. Use the Architect Agent to generate tickets.
                </div>
              ) : (
                pendingTickets.map((t) => (
                  <div key={t.id} className="p-4 flex items-center justify-between hover:bg-zinc-900/40 transition">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-zinc-300">{t.id}</span>
                        <span className="text-xs text-zinc-200 font-medium">{t.title}</span>
                      </div>
                      <div className="text-[11px] text-zinc-500 mt-1 line-clamp-1">{t.problem_statement}</div>
                    </div>
                    <button
                      onClick={() => setCurrentTab('tickets')}
                      className="px-2.5 py-1 text-xs font-mono rounded border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition"
                    >
                      Review
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Col: System Status & Audit Events */}
        <div className="space-y-6">
          {/* Capabilities Card */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-4 space-y-3 font-mono text-xs">
            <div className="font-semibold text-zinc-300 border-b border-zinc-800 pb-2">
              ENVIRONMENT CAPABILITIES
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Target Repo:</span>
              <span className="text-zinc-200 font-semibold truncate max-w-[150px]">Agent Chess</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Meta-Graph:</span>
              <span className="text-emerald-400 font-semibold">Ready (750 nodes)</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Local Inference:</span>
              <span className="text-zinc-200">qwen2.5-coder:1.5b</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Remote Reasoning:</span>
              <span className="text-emerald-400">Groq Connected</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Sandbox Mode:</span>
              <span className="text-amber-400">Restricted Local</span>
            </div>
          </div>

          {/* Audit Stream */}
          <div className="border border-zinc-800 rounded bg-zinc-950">
            <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/40 text-xs font-mono font-semibold text-zinc-300">
              AUDIT LOG
            </div>
            <div className="divide-y divide-zinc-800/80 max-h-80 overflow-auto">
              {auditEvents.length === 0 ? (
                <div className="p-4 text-center text-xs text-zinc-500 font-mono">No recent audit events.</div>
              ) : (
                auditEvents.map((e) => (
                  <div key={e.id} className="p-3 text-[11px] font-mono">
                    <div className="flex items-center justify-between text-zinc-400">
                      <span className="font-semibold text-zinc-300">{e.event_type}</span>
                      <span className="text-zinc-600">{new Date(e.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-zinc-500 text-[10px] truncate mt-0.5">
                      Actor: {e.actor} | {JSON.stringify(e.details)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
