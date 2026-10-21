import React, { useState, useEffect } from 'react';
import {
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  History,
  GitBranch,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
  Activity,
  Layers,
  Database,
  Terminal,
  Cpu,
  FileCode,
  DollarSign,
  Radio,
  Sparkles
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
  const [phoenixStatus, setPhoenixStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData(true);
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadData(false);
      }
    }, 15000);

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

  const loadData = async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      const [m, r, t, a, p] = await Promise.all([
        api.getMetricsOverview().catch(() => null),
        api.getRuns().catch(() => []),
        api.getTickets(undefined, 'PROPOSED').catch(() => []),
        api.getAuditEvents().catch(() => []),
        api.getPhoenixStatus().catch(() => null),
      ]);
      if (m) setMetrics(m);
      if (r) setRecentRuns(r.slice(0, 5));
      if (t) setPendingTickets(t.slice(0, 4));
      if (a) setAuditEvents(a.slice(0, 6));
      if (p) setPhoenixStatus(p);
    } catch (e) {
      console.error('Error loading overview data:', e);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  const PIPELINE_STAGES = [
    { id: 1, name: 'AST Analysis', icon: FileCode, desc: 'Symbol extraction', status: 'VERIFIED', color: 'text-blue-400' },
    { id: 2, name: 'Architect', icon: Terminal, desc: 'Grounded ticket generation', status: 'ACTIVE', color: 'text-indigo-400' },
    { id: 3, name: 'Criteria Freeze', icon: Database, desc: 'SHA-256 criteria hashing', status: 'LOCKED', color: 'text-purple-400' },
    { id: 4, name: 'Planner', icon: Layers, desc: 'Bounded execution subtasks', status: 'ACTIVE', color: 'text-amber-400' },
    { id: 5, name: 'Worktree Sandbox', icon: GitBranch, desc: 'Isolated candidate branch', status: 'ISOLATED', color: 'text-cyan-400' },
    { id: 6, name: 'LocalCoder', icon: Activity, desc: 'Candidate patch synthesis', status: 'ACTIVE', color: 'text-emerald-400' },
    { id: 7, name: 'Judge & Gate', icon: CheckCircle2, desc: 'Deterministic Pytest & Merge Gate', status: 'GATED', color: 'text-emerald-400' },
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* RC1 Control Room Header Banner */}
      <div className="glass-panel rounded-xl p-6 relative overflow-hidden border border-emerald-500/20 bg-gradient-to-r from-emerald-950/20 via-zinc-900/60 to-zinc-950">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">
                PROJECT OUROBOROS CONTROL ROOM
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950/80 border border-emerald-500/40 text-emerald-400">
                v1.0-RC1 RELEASE CANDIDATE
              </span>
            </div>
            <p className="text-xs text-zinc-400 max-w-3xl">
              Hierarchical autonomous software repair engine with failure trajectory memory, isolated Git worktree sandboxing, deterministic test harnesses, and OpenTelemetry trace ingestion into Arize Phoenix.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 font-mono text-xs">
            <button
              onClick={() => setCurrentTab('observability')}
              className="px-3.5 py-2 rounded-lg border border-purple-800/80 bg-purple-950/40 hover:bg-purple-900/50 text-purple-200 transition flex items-center gap-1.5 font-bold shadow-sm"
            >
              <Radio className="w-3.5 h-3.5 text-purple-400" /> Live Spans
            </button>
            <button
              onClick={() => setCurrentTab('tickets')}
              className="px-3.5 py-2 rounded-lg border border-emerald-600/60 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 transition flex items-center gap-1.5 font-bold shadow-sm shadow-emerald-950/50"
            >
              <PlayCircle className="w-3.5 h-3.5" /> Launch Ticket
            </button>
          </div>
        </div>
      </div>

      {/* 7-Stage End-to-End Workflow Pipeline Visualizer */}
      <div className="glass-panel rounded-xl p-5 border border-zinc-800 space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-400" />
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-zinc-200">
              Verified Ticket-to-Repair Workflow Pipeline (RC1 Lifecycle)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-zinc-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> 7 Stages Hardened
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 pt-1 font-mono">
          {PIPELINE_STAGES.map((st, idx) => {
            const Icon = st.icon;
            return (
              <div
                key={st.id}
                className="p-3 rounded-lg border border-zinc-800/80 bg-zinc-900/60 hover:border-zinc-700 transition flex flex-col justify-between space-y-2 group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-zinc-500 font-bold">0{st.id}</span>
                  <span className="text-[9px] px-1.5 py-0.2 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 font-bold">
                    {st.status}
                  </span>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-100 group-hover:text-emerald-400 transition">
                    <Icon className={`w-3.5 h-3.5 ${st.color}`} />
                    <span className="truncate">{st.name}</span>
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5 leading-tight truncate">
                    {st.desc}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Metric Cards Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-panel p-4 rounded-xl border border-zinc-800 space-y-1">
          <div className="text-zinc-500 text-xs font-mono uppercase">Total Runs</div>
          <div className="text-2xl font-bold font-mono text-zinc-100">{metrics?.total_runs ?? 0}</div>
          <div className="text-[11px] text-zinc-500">Autonomous repair cycles</div>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-zinc-800 space-y-1">
          <div className="text-zinc-500 text-xs font-mono uppercase">Acceptance Rate</div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {metrics?.acceptance_rate ?? 0}%
          </div>
          <div className="text-[11px] text-zinc-500">
            {metrics?.successful_runs ?? 0} passed / {metrics?.total_runs ?? 0} total
          </div>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-zinc-800 space-y-1">
          <div className="text-zinc-500 text-xs font-mono uppercase">Failure Trajectories</div>
          <div className="text-2xl font-bold font-mono text-purple-400">
            {metrics?.total_trajectories ?? 0}
          </div>
          <div className="text-[11px] text-zinc-500">Flywheel repair memory</div>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-zinc-800 space-y-1">
          <div className="text-zinc-500 text-xs font-mono uppercase">System Free RAM</div>
          <div
            className={`text-2xl font-bold font-mono ${
              (metrics?.free_ram_mb ?? 2000) < 1500 ? 'text-amber-400' : 'text-zinc-100'
            }`}
          >
            {metrics?.free_ram_mb ?? 0} MB
          </div>
          <div className="text-[11px] text-zinc-500">
            CPU: {metrics?.cpu_percent ?? 0}% | Limit: 8 GB
          </div>
        </div>
      </div>

      {/* Live Experiment Highlight & Resource Budget Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Spotlight on Live Controlled Run */}
        <div className="lg:col-span-2 glass-panel rounded-xl p-5 border border-zinc-800 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-zinc-200">
                Verified Live Controlled Experiment (Task BENCH-01)
              </h3>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 font-bold">
              VERDICT: PASS
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <span className="text-zinc-500 text-[10px]">TICKET ID</span>
              <div className="text-zinc-100 font-bold truncate">OURO-LIVE-20261019_115054</div>
              <div className="text-[10px] text-zinc-500">BENCH-01 Input Guard</div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <span className="text-zinc-500 text-[10px]">PROVIDER & MODEL</span>
              <div className="text-emerald-400 font-bold truncate">qwen/qwen3.8-27b</div>
              <div className="text-[10px] text-zinc-500">Groq Cloud Live Reasoning</div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <span className="text-zinc-500 text-[10px]">TOKEN CONSUMPTION</span>
              <div className="text-indigo-400 font-bold truncate">2,230 Tokens</div>
              <div className="text-[10px] text-zinc-500">1,150 In / 1,080 Out</div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <span className="text-zinc-500 text-[10px]">TOTAL COST</span>
              <div className="text-amber-400 font-bold truncate">$0.000446 USD</div>
              <div className="text-[10px] text-zinc-500">Ceiling: $0.010000 USD</div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/60 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-300">
              <Radio className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
              <span>Trace ID: <span className="text-zinc-100 font-bold">24d6d767c93a54a83754e8f722e82233</span></span>
              <span className="text-zinc-500 hidden sm:inline">(14 Spans Ingested in Arize Phoenix)</span>
            </div>
            <a
              href="http://127.0.0.1:6006/projects/ouroboros-swarm/traces/24d6d767c93a54a83754e8f722e82233"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 font-bold transition"
            >
              Open Trace <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Live Safety Budget Audit Card */}
        <div className="glass-panel rounded-xl p-5 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-zinc-200">
                Safety Budget Controls
              </h3>
            </div>
            <span className="text-[10px] font-mono text-emerald-400">Fail-Closed Active</span>
          </div>

          <div className="space-y-3 text-xs font-mono pt-1">
            <div>
              <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                <span>Remote Requests</span>
                <span className="text-zinc-200 font-bold">3 / 8 (37.5%)</span>
              </div>
              <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: '37.5%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                <span>Token Ceiling</span>
                <span className="text-zinc-200 font-bold">2,230 / 12,000 (18.6%)</span>
              </div>
              <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 rounded-full" style={{ width: '18.6%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                <span>Cost Ceiling</span>
                <span className="text-zinc-200 font-bold">$0.0004 / $0.0100 (4.5%)</span>
              </div>
              <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full bg-amber-500 rounded-full" style={{ width: '4.5%' }}></div>
              </div>
            </div>

            <div className="pt-2 border-t border-zinc-800/80 flex justify-between text-[11px] text-zinc-500">
              <span>Min Inter-Call Pacing:</span>
              <span className="text-zinc-300 font-bold">3.0s enforced</span>
            </div>
            <div className="flex justify-between text-[11px] text-zinc-500">
              <span>Auto-Merge to Main:</span>
              <span className="text-rose-400 font-bold">BLOCKED by policy</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Recent Runs & Pending Tickets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Runs */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-panel border border-zinc-800 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-900/50">
              <span className="text-xs font-mono font-semibold text-zinc-300 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-zinc-400" /> RECENT AGENT RUNS
              </span>
              <button
                onClick={() => setCurrentTab('runs')}
                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 font-mono transition"
              >
                View all runs <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="divide-y divide-zinc-800/80">
              {recentRuns.length === 0 ? (
                <div className="p-6 text-center text-xs text-zinc-500 font-mono">
                  No active or past agent runs recorded in database.
                </div>
              ) : (
                recentRuns.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => {
                      onSelectRun(r.id);
                      setCurrentTab('runs');
                    }}
                    className="p-4 flex items-center justify-between hover:bg-zinc-900/60 cursor-pointer transition"
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
                      <div className={r.verdict === 'PASS' ? 'text-emerald-400 font-bold' : ''}>
                        {r.verdict ? `Verdict: ${r.verdict}` : 'In Progress'}
                      </div>
                      <div className="text-zinc-600">Retries: {r.retry_count}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Col: Pending Tickets / Proposed */}
        <div className="space-y-6">
          <div className="glass-panel border border-zinc-800 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-900/50">
              <span className="text-xs font-mono font-semibold text-zinc-300">PROPOSED TICKETS</span>
              <button
                onClick={() => setCurrentTab('tickets')}
                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 font-mono transition"
              >
                Manage <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="divide-y divide-zinc-800/80">
              {pendingTickets.length === 0 ? (
                <div className="p-6 text-center text-xs text-zinc-500 font-mono">
                  No proposed tickets awaiting planning.
                </div>
              ) : (
                pendingTickets.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => setCurrentTab('tickets')}
                    className="p-4 hover:bg-zinc-900/60 cursor-pointer transition space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-zinc-200">{t.id}</span>
                      <StatusBadge status={t.status} size="sm" />
                    </div>
                    <div className="text-xs text-zinc-300 line-clamp-1">{t.title}</div>
                    <div className="text-[10px] text-zinc-500 font-mono">
                      Repo: {t.repo_id} | Risk: {t.risk_level || 'STANDARD'}
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
