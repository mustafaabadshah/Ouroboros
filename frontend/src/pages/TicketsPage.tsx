import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Check,
  X,
  Edit3,
  Save,
  RotateCcw,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  ArrowRight,
  Shield,
  FileCode,
  Tag,
  AlertCircle,
  AlertTriangle,
  Play
} from 'lucide-react';
import { api, fallbackData } from '../services/api';
import { Ticket, Repository } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { TabType } from '../components/Sidebar';

interface TicketsPageProps {
  onSelectRun: (runId: string) => void;
  setCurrentTab: (tab: TabType) => void;
  initialPrompt?: string;
  onClearInitialPrompt?: () => void;
}

const PRESET_CHIPS = [
  { label: '⚡ API Validation', prompt: 'API boundary validation and defensive HTTP 400/404/422 status handlers in games and moves API' },
  { label: '♟️ Chess Board Invariants', prompt: 'Chess board state invariants, FEN parser boundary checks, and move notation validation in board_manager.py' },
  { label: '⏱️ Stockfish Engine Latency', prompt: 'Stockfish engine subprocess timeout recovery, bounds checking, and latency metrics in stockfish.py' },
  { label: '🏆 Tournament & Forfeits', prompt: 'Tournament round forfeit tracking and match failure telemetry in tournament.py' },
  { label: '📊 Agent Telemetry Counters', prompt: 'Groq agent fallback move counters and structured error logging in groq_agent.py' },
];

const CACHE_KEY_TICKETS = 'ouroboros_cached_tickets';

export const TicketsPage: React.FC<TicketsPageProps> = ({ onSelectRun, setCurrentTab, initialPrompt, onClearInitialPrompt }) => {
  const [tickets, setTickets] = useState<Ticket[]>(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY_TICKETS);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // ignore
    }
    return (fallbackData.tickets as Ticket[]) || [];
  });
  const [repositories, setRepositories] = useState<Repository[]>(() => (fallbackData.repositories as Repository[]) || []);
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY_TICKETS);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed[0];
      }
    } catch {
      // ignore
    }
    return ((fallbackData.tickets as Ticket[])[0]) || null;
  });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [showGenModal, setShowGenModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // In-line ticket editing state
  const [isEditing, setIsEditing] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editProblem, setEditProblem] = useState('');
  const [editCurrent, setEditCurrent] = useState('');
  const [editDesired, setEditDesired] = useState('');
  const [editCriteria, setEditCriteria] = useState('');

  useEffect(() => {
    loadRepositories();
    loadTickets();
  }, []);

  useEffect(() => {
    if (initialPrompt) {
      setCustomPrompt(initialPrompt);
      setShowGenModal(true);
      onClearInitialPrompt?.();
    }
  }, [initialPrompt]);

  const loadRepositories = async () => {
    try {
      const repos = await api.getRepositories();
      if (Array.isArray(repos) && repos.length > 0) {
        setRepositories(repos);
        if (!selectedRepoId) {
          setSelectedRepoId(repos[0].id);
        }
      }
    } catch (e) {
      console.error('Error loading repositories:', e);
    }
  };

  const loadTickets = async () => {
    try {
      if (tickets.length === 0) setLoading(true);
      const data = await api.getTickets();
      if (Array.isArray(data) && data.length > 0) {
        setTickets(data);
        localStorage.setItem(CACHE_KEY_TICKETS, JSON.stringify(data));
        if (!selectedTicket) {
          setSelectedTicket(data[0]);
        }
      }
    } catch (e) {
      console.error('Error loading tickets:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateTicket = async () => {
    try {
      setGenerating(true);
      const targetRepo = selectedRepoId || (repositories.length > 0 ? repositories[0].id : 'agent_chess');
      const newTicket = await api.generateTicket(targetRepo, customPrompt);
      setShowGenModal(false);
      setCustomPrompt('');
      await loadTickets();
      setSelectedTicket(newTicket);
      setIsEditing(false);
    } catch (e) {
      alert(`Ticket generation failed: ${e}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async (ticketId: string) => {
    try {
      await api.approveTicket(ticketId);
      const run = await api.startRun(ticketId, 'SUPERVISED', false);
      onSelectRun(run.id);
      setCurrentTab('runs');
    } catch (e) {
      alert(`Approval failed: ${e}`);
    }
  };

  const handleReject = async (ticketId: string) => {
    try {
      await api.rejectTicket(ticketId);
      await loadTickets();
    } catch (e) {
      alert(`Reject failed: ${e}`);
    }
  };

  const handleResetStatus = async (ticketId: string, newStatus: string = 'PROPOSED') => {
    try {
      const updated = await api.updateTicket(ticketId, { status: newStatus });
      setSelectedTicket(updated);
      await loadTickets();
    } catch (e) {
      alert(`Status update failed: ${e}`);
    }
  };

  const startEdit = (t: Ticket) => {
    setEditTitle(t.title);
    setEditProblem(t.problem_statement);
    setEditCurrent(t.current_behavior);
    setEditDesired(t.desired_behavior);
    setEditCriteria(t.acceptance_criteria.join('\n'));
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (!selectedTicket) return;
    try {
      setSavingEdit(true);
      const updated = await api.updateTicket(selectedTicket.id, {
        title: editTitle,
        problem_statement: editProblem,
        current_behavior: editCurrent,
        desired_behavior: editDesired,
        acceptance_criteria: editCriteria.split('\n').map((s) => s.trim()).filter(Boolean),
      });
      setSelectedTicket(updated);
      setTickets(tickets.map((t) => (t.id === updated.id ? updated : t)));
      setIsEditing(false);
    } catch (e) {
      alert(`Failed to save ticket edits: ${e}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const selectTicketItem = (t: Ticket) => {
    setSelectedTicket(t);
    setIsEditing(false);
  };

  const filteredTickets = tickets.filter((t) => {
    const matchesSearch =
      t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.problem_statement.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              SPECIFICATION FREEZE
            </span>
            <span className="text-zinc-500 text-xs font-mono">•</span>
            <span className="text-zinc-400 text-xs font-mono">DETERMINISTIC JIRA TICKETS</span>
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-zinc-100 flex items-center gap-2">
            Engineering Feature Tickets
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Bounded technical debt, missing telemetry, and deterministic test proposals generated by the Architect Agent.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowGenModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 text-zinc-950 hover:bg-emerald-400 transition shadow-lg shadow-emerald-500/20"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Ticket (Architect)</span>
          </button>
          <button
            onClick={loadTickets}
            className="p-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition shadow-sm"
            title="Refresh Tickets"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="glass-panel rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tickets by ID, title, problem..."
            className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 font-mono outline-none focus:border-emerald-500 transition"
          />
        </div>

        <div className="flex items-center gap-1 text-[11px] font-mono overflow-x-auto w-full sm:w-auto">
          <Filter className="w-3.5 h-3.5 text-zinc-500 mr-1" />
          {['ALL', 'PROPOSED', 'APPROVED', 'IMPLEMENTING', 'COMPLETED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-lg border transition ${
                statusFilter === st
                  ? 'bg-emerald-500/10 border-emerald-500 text-emerald-300 font-bold'
                  : 'border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ticket List */}
        <div className="glass-panel rounded-xl overflow-hidden divide-y divide-zinc-800/80 max-h-[750px] flex flex-col">
          <div className="p-3 bg-zinc-900/60 border-b border-zinc-800 flex items-center justify-between">
            <span className="font-mono text-xs font-semibold text-zinc-300">Available Tickets</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-zinc-800 text-zinc-400">
              {filteredTickets.length} / {tickets.length}
            </span>
          </div>

          <div className="divide-y divide-zinc-800/60 overflow-y-auto flex-1">
            {filteredTickets.length === 0 ? (
              <div className="p-8 text-center text-xs text-zinc-500 font-mono space-y-2">
                <Clock className="w-8 h-8 mx-auto text-zinc-600 mb-2 opacity-50" />
                <p>No matching tickets found.</p>
                <p className="text-[11px] text-zinc-600">Click 'Generate Ticket' to synthesize a new proposal.</p>
              </div>
            ) : (
              filteredTickets.map((t) => {
                const isSelected = t.id === selectedTicket?.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => selectTicketItem(t)}
                    className={`p-4 cursor-pointer transition relative group ${
                      isSelected
                        ? 'bg-zinc-900/90 border-l-4 border-emerald-500 shadow-inner'
                        : 'hover:bg-zinc-900/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-xs font-bold text-zinc-200 group-hover:text-emerald-400 transition">
                        {t.id}
                      </span>
                      <StatusBadge status={t.status} size="sm" />
                    </div>
                    <h3 className="text-xs font-semibold text-zinc-100 line-clamp-1">{t.title}</h3>
                    <p className="text-[11px] text-zinc-400 line-clamp-2 mt-1 leading-relaxed">
                      {t.problem_statement}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-zinc-500">
                      <span className="flex items-center gap-1">
                        <Shield className="w-3 h-3 text-amber-400" />
                        Risk: {t.risk_level || 'STANDARD'}
                      </span>
                      <span>•</span>
                      <span>Complexity: {t.expected_complexity || 'O(1)'}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Ticket Review Panel */}
        {selectedTicket && (
          <div className="lg:col-span-2 glass-panel rounded-xl p-6 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-zinc-800 pb-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-mono text-xs text-zinc-400">{selectedTicket.id}</span>
                  <StatusBadge status={selectedTicket.status} />
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/80 text-zinc-300">
                    Risk: {selectedTicket.risk_level?.toUpperCase() || 'STANDARD'}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/80 text-zinc-300">
                    Repo: {selectedTicket.repo_id}
                  </span>
                </div>
                {isEditing ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-bold text-zinc-100 font-sans outline-none focus:border-emerald-500 mt-1"
                    placeholder="Ticket Title"
                  />
                ) : (
                  <h2 className="text-lg font-bold text-zinc-100">{selectedTicket.title}</h2>
                )}
              </div>

              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={handleSaveEdit}
                      disabled={savingEdit}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition disabled:opacity-50 shadow-md shadow-emerald-500/20"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>{savingEdit ? 'Saving...' : 'Save Changes'}</span>
                    </button>
                    <button
                      onClick={() => setIsEditing(false)}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Cancel</span>
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => startEdit(selectedTicket)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
                      title="Edit Ticket"
                    >
                      <Edit3 className="w-3.5 h-3.5 text-zinc-400" />
                      <span>Edit Ticket</span>
                    </button>
                    {selectedTicket.status === 'PROPOSED' && (
                      <>
                        <button
                          onClick={() => handleApprove(selectedTicket.id)}
                          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition shadow-lg shadow-emerald-500/20"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Approve & Launch Run</span>
                        </button>
                        <button
                          onClick={() => handleReject(selectedTicket.id)}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-mono rounded-lg border border-rose-800 bg-rose-950/60 text-rose-300 hover:bg-rose-900 transition"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Reject</span>
                        </button>
                      </>
                    )}
                    {selectedTicket.status === 'FAILED' && (
                      <>
                        <button
                          onClick={() => handleResetStatus(selectedTicket.id, 'PROPOSED')}
                          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 transition shadow-lg shadow-amber-500/20"
                          title="Reset ticket to PROPOSED so it can be re-evaluated cleanly"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          <span>Reset to Proposed</span>
                        </button>
                        <button
                          onClick={() => handleReject(selectedTicket.id)}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Archive / Reject</span>
                        </button>
                      </>
                    )}
                    {selectedTicket.status === 'APPROVED' && (
                      <>
                        <button
                          onClick={() => handleApprove(selectedTicket.id)}
                          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition shadow-lg shadow-emerald-500/20"
                        >
                          <Play className="w-3.5 h-3.5" />
                          <span>Launch Run</span>
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>

            {selectedTicket.status === 'FAILED' && (
              <div className="flex items-center gap-2.5 p-3.5 bg-rose-950/40 border border-rose-800/80 rounded-xl text-rose-200 text-xs font-mono">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>
                  <strong>Prior Run Failed:</strong> Repair attempts were exhausted on this ticket. You can edit the criteria, click <strong>Reset to Proposed</strong>, or generate a new ticket.
                </span>
              </div>
            )}

            {/* Sections */}
            <div className="space-y-4 text-xs">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                    Problem Statement
                  </h4>
                </div>
                {isEditing ? (
                  <textarea
                    rows={3}
                    value={editProblem}
                    onChange={(e) => setEditProblem(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-zinc-200 font-sans outline-none focus:border-emerald-500"
                  />
                ) : (
                  <p className="text-zinc-200 bg-zinc-900/60 p-3.5 rounded-lg border border-zinc-800/80 leading-relaxed font-sans shadow-inner">
                    {selectedTicket.problem_statement}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] mb-1">
                    Current Behavior
                  </h4>
                  {isEditing ? (
                    <textarea
                      rows={3}
                      value={editCurrent}
                      onChange={(e) => setEditCurrent(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-zinc-300 font-sans outline-none focus:border-emerald-500"
                    />
                  ) : (
                    <p className="text-zinc-400 bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-800/60 leading-relaxed min-h-[70px]">
                      {selectedTicket.current_behavior}
                    </p>
                  )}
                </div>
                <div>
                  <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] mb-1">
                    Desired Behavior
                  </h4>
                  {isEditing ? (
                    <textarea
                      rows={3}
                      value={editDesired}
                      onChange={(e) => setEditDesired(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-zinc-200 font-sans outline-none focus:border-emerald-500"
                    />
                  ) : (
                    <p className="text-zinc-300 bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-800/60 leading-relaxed min-h-[70px]">
                      {selectedTicket.desired_behavior}
                    </p>
                  )}
                </div>
              </div>

              {/* Acceptance Criteria */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Deterministic Acceptance Criteria
                  </h4>
                  {isEditing && (
                    <span className="text-[10px] text-zinc-500 font-mono">One criterion per line</span>
                  )}
                </div>
                {isEditing ? (
                  <textarea
                    rows={4}
                    value={editCriteria}
                    onChange={(e) => setEditCriteria(e.target.value)}
                    placeholder="Enter each acceptance criterion on a new line..."
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-zinc-200 font-mono text-[11px] outline-none focus:border-emerald-500"
                  />
                ) : (
                  <ul className="space-y-1.5 font-mono text-[11px]">
                    {selectedTicket.acceptance_criteria.map((ac, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-zinc-300 bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-800/60">
                        <span className="text-emerald-400 font-bold">[{idx + 1}]</span>
                        <span className="leading-relaxed">{ac}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Candidate Files Scope */}
              <div>
                <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] mb-1.5 flex items-center gap-1.5">
                  <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                  Allowed Target Files
                </h4>
                <div className="flex flex-wrap gap-2">
                  {selectedTicket.candidate_files.map((f, i) => (
                    <span key={i} className="font-mono text-xs px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-700 text-cyan-300 flex items-center gap-1">
                      <Tag className="w-3 h-3 opacity-60" />
                      {f}
                    </span>
                  ))}
                </div>
              </div>

              {/* Proposed Test Plan */}
              {selectedTicket.proposed_tests.length > 0 && (
                <div>
                  <h4 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-[11px] mb-1.5">
                    Proposed Pytest Assertions
                  </h4>
                  <div className="space-y-1 font-mono text-[11px]">
                    {selectedTicket.proposed_tests.map((t, i) => (
                      <div key={i} className="text-zinc-400 bg-zinc-900/30 p-2.5 rounded-lg border border-zinc-800/50">
                        {t}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Auto-Synthesized Acceptance Test Template */}
              {selectedTicket.acceptance_test_template && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <h4 className="font-mono text-emerald-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      AST-Grounded Acceptance Test Template
                    </h4>
                    <span className="text-[10px] font-mono text-zinc-500">Auto-Synthesized from Caller Graph</span>
                  </div>
                  <pre className="p-3.5 bg-zinc-950/90 border border-emerald-500/30 rounded-lg text-emerald-300 font-mono text-xs overflow-x-auto leading-relaxed shadow-inner">
                    <code>{selectedTicket.acceptance_test_template}</code>
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Generate Ticket Modal */}
      {showGenModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="glass-panel border border-zinc-700/80 rounded-2xl p-6 max-w-lg w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold font-mono text-zinc-100">Generate Bounded Feature Ticket</h3>
              </div>
              <button
                onClick={() => setShowGenModal(false)}
                className="text-zinc-400 hover:text-zinc-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              The Architect Agent will analyze Meta-Graph AST summaries and synthesize a structured Jira ticket with frozen deterministic criteria.
            </p>

            {/* Target Repository Selector */}
            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">Target Repository:</label>
              <select
                value={selectedRepoId}
                onChange={(e) => setSelectedRepoId(e.target.value)}
                className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono outline-none focus:border-emerald-500"
              >
                {repositories.length > 0 ? (
                  repositories.map((repo) => (
                    <option key={repo.id} value={repo.id}>
                      {repo.name} ({repo.id})
                    </option>
                  ))
                ) : (
                  <option value="agent_chess">Agent Chess (agent_chess)</option>
                )}
              </select>
            </div>

            {/* Quick Focus Preset Chips */}
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">Quick Focus Presets:</label>
              <div className="flex flex-wrap gap-1.5">
                {PRESET_CHIPS.map((chip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setCustomPrompt(chip.prompt)}
                    className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/80 text-zinc-300 hover:text-emerald-400 transition"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">Focus or Direction (Optional):</label>
              <textarea
                rows={2}
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Leave blank for automatic domain rotation or pick a preset above..."
                className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono outline-none focus:border-emerald-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button
                onClick={() => setShowGenModal(false)}
                className="px-3.5 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 text-zinc-300 hover:bg-zinc-900 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateTicket}
                disabled={generating}
                className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition disabled:opacity-50 shadow-lg shadow-emerald-500/20"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{generating ? 'Architect Synthesizing...' : 'Generate Ticket'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
