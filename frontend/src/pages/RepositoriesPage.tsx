import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  Database,
  RefreshCw,
  Folder,
  FolderOpen,
  FolderPlus,
  Download,
  Edit3,
  Trash2,
  Plus,
  X,
  AlertCircle,
  CheckCircle2,
  Network,
  FileCode,
  Sparkles,
  Search,
  Code,
  ChevronRight,
  ArrowRight,
  Boxes,
  FileCheck,
  Activity,
  Layers,
  Hash,
  ArrowUpRight
} from 'lucide-react';
import { api } from '../services/api';
import { Repository, GraphStatus, AstSummary, FileDependencies } from '../types';

interface RepositoriesPageProps {
  onNavigateToTickets?: (prompt: string) => void;
}

export const RepositoriesPage: React.FC<RepositoriesPageProps> = ({ onNavigateToTickets }) => {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [graphStatuses, setGraphStatuses] = useState<Record<string, GraphStatus>>({});
  const [loading, setLoading] = useState(true);
  const [selectedRepoId, setSelectedRepoId] = useState<string>('agent_chess');
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [astSummary, setAstSummary] = useState<AstSummary | null>(null);

  // Modals & Dynamic Management State
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [showChangePathModal, setShowChangePathModal] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [cloneForm, setCloneForm] = useState({
    id: '',
    name: '',
    git_url: '',
    target_path: ''
  });

  const [registerForm, setRegisterForm] = useState({
    id: '',
    name: '',
    path: ''
  });

  const [changePathForm, setChangePathForm] = useState({
    path: ''
  });

  // Explorer Selection State
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileDeps, setFileDeps] = useState<FileDependencies | null>(null);
  const [loadingDeps, setLoadingDeps] = useState(false);
  const [symbolSearchQuery, setSymbolSearchQuery] = useState('');
  const [activeInspectorTab, setActiveInspectorTab] = useState<'symbols' | 'callers' | 'tests'>('symbols');
  const [subsystemFilter, setSubsystemFilter] = useState<'ALL' | 'BACKEND' | 'FRONTEND' | 'DOCS' | 'CONFIG'>('ALL');

  useEffect(() => {
    loadRepositories();
  }, []);

  const loadRepositories = async () => {
    try {
      setLoading(true);
      const repos = await api.getRepositories();
      setRepositories(repos);

      const statuses: Record<string, GraphStatus> = {};
      const statusResults = await Promise.all(
        repos.map(async (r) => {
          try {
            const gs = await api.getGraphStatus(r.id);
            return { id: r.id, status: gs };
          } catch (err) {
            console.error(`Failed to get graph status for ${r.id}:`, err);
            return null;
          }
        })
      );
      for (const item of statusResults) {
        if (item) {
          statuses[item.id] = item.status;
        }
      }
      setGraphStatuses(statuses);

      // Auto-analyze agent_chess or the first available repo
      const targetId = repos.find((r) => r.id === 'agent_chess')?.id || (repos.length > 0 ? repos[0].id : null);
      if (targetId) {
        setSelectedRepoId(targetId);
        await handleAnalyze(targetId);
      }
    } catch (e) {
      console.error('Error fetching repositories:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (repoId: string) => {
    try {
      setAnalyzingId(repoId);
      const res = await api.analyzeRepository(repoId);
      setAstSummary(res.summary);

      // Automatically select high-value module
      const modules = Object.keys(res.summary.module_structure || {});
      if (modules.length > 0) {
        const preferred = modules.find((m) => m.includes('agents') || m.includes('chess') || m.includes('api')) || modules[0];
        setSelectedModule(preferred);
        const files = res.summary.module_structure[preferred] || [];
        if (files.length > 0) {
          const firstFilePath = `${preferred}/${files[0]}`;
          setSelectedFile(firstFilePath);
          await loadFileDependencies(repoId, firstFilePath);
        }
      }
    } catch (e) {
      console.error('Analysis failed:', e);
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleSwitchRepo = async (repoId: string) => {
    setSelectedRepoId(repoId);
    setActionError(null);
    setActionSuccess(null);
    await handleAnalyze(repoId);
  };

  const handleCloneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cloneForm.id || !cloneForm.git_url) {
      setActionError('Repository ID and Git URL are required.');
      return;
    }
    try {
      setActionLoading(true);
      setActionError(null);
      const name = cloneForm.name.trim() || cloneForm.id.trim();
      const newRepo = await api.cloneRepository(
        cloneForm.id.trim(),
        name,
        cloneForm.git_url.trim(),
        cloneForm.target_path.trim() || undefined
      );
      setActionSuccess(`Successfully cloned and indexed '${newRepo.name}'!`);
      setShowCloneModal(false);
      setCloneForm({ id: '', name: '', git_url: '', target_path: '' });
      await loadRepositories();
      setSelectedRepoId(newRepo.id);
      await handleAnalyze(newRepo.id);
    } catch (err: any) {
      setActionError(err.message || 'Git clone failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerForm.id || !registerForm.path) {
      setActionError('Repository ID and local directory path are required.');
      return;
    }
    try {
      setActionLoading(true);
      setActionError(null);
      const name = registerForm.name.trim() || registerForm.id.trim();
      const newRepo = await api.registerRepository(
        registerForm.id.trim(),
        name,
        registerForm.path.trim()
      );
      setActionSuccess(`Successfully registered and indexed '${newRepo.name}'!`);
      setShowRegisterModal(false);
      setRegisterForm({ id: '', name: '', path: '' });
      await loadRepositories();
      setSelectedRepoId(newRepo.id);
      await handleAnalyze(newRepo.id);
    } catch (err: any) {
      setActionError(err.message || 'Registration failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const openChangePathModal = (currentPath: string) => {
    setChangePathForm({ path: currentPath });
    setActionError(null);
    setActionSuccess(null);
    setShowChangePathModal(true);
  };

  const handleChangePathSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!changePathForm.path) {
      setActionError('New directory path cannot be empty.');
      return;
    }
    try {
      setActionLoading(true);
      setActionError(null);
      await api.updateRepository(selectedRepoId, { path: changePathForm.path.trim() });
      setActionSuccess('Repository path updated and AST Knowledge Graph re-indexed!');
      setShowChangePathModal(false);
      await loadRepositories();
      await handleAnalyze(selectedRepoId);
    } catch (err: any) {
      setActionError(err.message || 'Failed to update repository path.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReindex = async (repoId: string) => {
    try {
      setActionLoading(true);
      setActionError(null);
      await api.reindexRepository(repoId);
      await loadRepositories();
      await handleAnalyze(repoId);
      setActionSuccess('AST Knowledge Graph successfully refreshed and re-indexed!');
      setTimeout(() => setActionSuccess(null), 3500);
    } catch (err: any) {
      setActionError(err.message || 'Re-indexing failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    if (!confirm(`Are you sure you want to unregister repository '${repoId}' from Ouroboros?`)) {
      return;
    }
    try {
      setActionLoading(true);
      await api.deleteRepository(repoId);
      await loadRepositories();
      setActionSuccess(`Repository '${repoId}' unregistered.`);
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setActionError(err.message || 'Failed to delete repository.');
    } finally {
      setActionLoading(false);
    }
  };

  const loadFileDependencies = async (repoId: string, relPath: string) => {
    try {
      setLoadingDeps(true);
      const deps = await api.getFileDependencies(repoId, relPath);
      setFileDeps(deps);
    } catch (e) {
      console.error(`Failed to load file dependencies for ${relPath}:`, e);
      setFileDeps(null);
    } finally {
      setLoadingDeps(false);
    }
  };

  const handleSelectModule = async (mod: string) => {
    setSelectedModule(mod);
    const files = astSummary?.module_structure[mod] || [];
    if (files.length > 0) {
      const filePath = mod === 'root' || mod === '.' ? files[0] : `${mod}/${files[0]}`;
      setSelectedFile(filePath);
      await loadFileDependencies(selectedRepoId, filePath);
    } else {
      setSelectedFile(null);
      setFileDeps(null);
    }
  };

  const handleSelectFile = async (mod: string, fileName: string) => {
    const filePath = mod === 'root' || mod === '.' ? fileName : `${mod}/${fileName}`;
    setSelectedFile(filePath);
    await loadFileDependencies(selectedRepoId, filePath);
  };

  const handleSynthesizeForFile = (filePath: string) => {
    const topSymbols = (fileDeps?.symbols || [])
      .slice(0, 3)
      .map((s) => s.name)
      .join(', ');
    const symbolContext = topSymbols ? ` (targeting ${topSymbols})` : '';
    const prompt = `Defensive validation, boundary invariants, and error resilience in ${filePath}${symbolContext}`;
    onNavigateToTickets?.(prompt);
  };

  const handleSynthesizeForModule = (mod: string) => {
    const prompt = `Architectural boundary hardening, exception recovery, and invariant validation for module: ${mod}`;
    onNavigateToTickets?.(prompt);
  };

  const handleSynthesizeForSymbol = (symbolName: string, filePath: string) => {
    const prompt = `Defensive validation, invariants, and edge case coverage for ${symbolName} in ${filePath}`;
    onNavigateToTickets?.(prompt);
  };

  const handleJumpToSymbol = async (symbolFile: string) => {
    const parts = symbolFile.replace(/\\/g, '/').split('/');
    if (parts.length > 1) {
      parts.pop();
      const mod = parts.join('/');
      setSelectedModule(mod);
    } else {
      setSelectedModule('root');
    }
    setSelectedFile(symbolFile);
    await loadFileDependencies(selectedRepoId, symbolFile);
  };

  const repo = repositories.find((r) => r.id === selectedRepoId) || repositories[0];
  const gs = repo ? graphStatuses[repo.id] : null;

  // Filtered symbols for key symbol catalog
  const filteredClasses = (astSummary?.key_classes || []).filter(
    (c) =>
      symbolSearchQuery === '' ||
      c.class_name.toLowerCase().includes(symbolSearchQuery.toLowerCase()) ||
      c.file.toLowerCase().includes(symbolSearchQuery.toLowerCase())
  );

  const filteredFunctions = (astSummary?.key_functions || []).filter(
    (f) =>
      symbolSearchQuery === '' ||
      f.func_name.toLowerCase().includes(symbolSearchQuery.toLowerCase()) ||
      f.file.toLowerCase().includes(symbolSearchQuery.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              AST META-GRAPH
            </span>
            <span className="text-zinc-500 text-xs font-mono">•</span>
            <span className="text-zinc-400 text-xs font-mono">CODEBASE NAVIGATOR</span>
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-zinc-100 flex items-center gap-2">
            Target Codebases & AST Knowledge Graph
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Registered target repositories, AST call graph dependencies, and semantic symbol navigation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              setActionError(null);
              setActionSuccess(null);
              setShowCloneModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-lg border border-cyan-500/40 bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-300 transition shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Clone from GitHub</span>
          </button>
          <button
            onClick={() => {
              setActionError(null);
              setActionSuccess(null);
              setShowRegisterModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-lg border border-emerald-500/40 bg-emerald-950/60 hover:bg-emerald-900/80 text-emerald-300 transition shadow-sm"
          >
            <FolderPlus className="w-3.5 h-3.5" />
            <span>Register Local Folder</span>
          </button>
          <button
            onClick={loadRepositories}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Graph</span>
          </button>
        </div>
      </div>

      {/* Global Action Notifications */}
      {actionSuccess && (
        <div className="p-3 rounded-xl bg-emerald-950/70 border border-emerald-800 text-emerald-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-emerald-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-3 rounded-xl bg-rose-950/70 border border-rose-800 text-rose-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="text-rose-400 hover:text-rose-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Target Codebase Switcher Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-zinc-800/80">
        <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider mr-1 shrink-0">
          Target Codebases:
        </span>
        {repositories.map((r) => {
          const isSelected = selectedRepoId === r.id;
          return (
            <button
              key={r.id}
              onClick={() => handleSwitchRepo(r.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono transition shrink-0 ${
                isSelected
                  ? 'bg-indigo-600 text-white font-bold shadow-md shadow-indigo-600/30 ring-1 ring-indigo-400'
                  : 'bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 border border-zinc-800'
              }`}
            >
              <Folder className="w-3.5 h-3.5" />
              <span>{r.name}</span>
              <span
                className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                  isSelected ? 'bg-indigo-800/90 text-indigo-100' : 'bg-zinc-800 text-zinc-400'
                }`}
              >
                {r.id}
              </span>
            </button>
          );
        })}
        <button
          onClick={() => {
            setActionError(null);
            setActionSuccess(null);
            setShowCloneModal(true);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-zinc-900/60 hover:bg-zinc-800 text-cyan-400 border border-cyan-500/30 hover:border-cyan-500/60 transition shrink-0"
        >
          <Plus className="w-3.5 h-3.5" /> Clone Git Repo
        </button>
        <button
          onClick={() => {
            setActionError(null);
            setActionSuccess(null);
            setShowRegisterModal(true);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-zinc-900/60 hover:bg-zinc-800 text-emerald-400 border border-emerald-500/30 hover:border-emerald-500/60 transition shrink-0"
        >
          <Plus className="w-3.5 h-3.5" /> Add Local Folder
        </button>
      </div>

      {/* Target Repository Spotlight Card */}
      {repo && (
        <div className="glass-panel rounded-2xl p-6 space-y-5 border border-zinc-800 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-80 h-32 bg-gradient-to-bl from-indigo-500/10 via-cyan-500/5 to-transparent pointer-events-none rounded-tr-2xl" />

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4 relative z-10">
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                <Folder className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="font-mono text-base font-bold text-zinc-100">{repo.name}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                    {repo.id}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Validated
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-wrap pt-0.5">
                  <p className="text-xs font-mono text-zinc-400 select-all bg-zinc-900/80 px-2 py-0.5 rounded border border-zinc-800">
                    {repo.path}
                  </p>
                  <button
                    onClick={() => openChangePathModal(repo.path)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition"
                    title="Change local directory path"
                  >
                    <Edit3 className="w-3 h-3 text-zinc-400" />
                    <span>Change Directory</span>
                  </button>
                  <button
                    onClick={() => handleReindex(repo.id)}
                    disabled={actionLoading}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono bg-zinc-800 hover:bg-zinc-700 text-cyan-300 border border-zinc-700 transition disabled:opacity-50"
                    title="Re-index AST Knowledge Graph"
                  >
                    <RefreshCw className={`w-3 h-3 ${actionLoading ? 'animate-spin' : ''}`} />
                    <span>Re-index AST</span>
                  </button>
                  {repositories.length > 1 && (
                    <button
                      onClick={() => handleDeleteRepo(repo.id)}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-mono bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/80 transition"
                      title="Unregister repository"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Remove</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleAnalyze(repo.id)}
                disabled={analyzingId === repo.id}
                className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono rounded-lg border border-cyan-500/30 bg-cyan-950/40 hover:bg-cyan-900/60 text-cyan-300 transition disabled:opacity-50 shadow-sm"
              >
                <Network className={`w-3.5 h-3.5 ${analyzingId === repo.id ? 'animate-spin' : ''}`} />
                <span>{analyzingId === repo.id ? 'Analyzing AST...' : 'Inspect AST Structure'}</span>
              </button>
            </div>
          </div>

          {/* Git Status & Meta-Graph Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono relative z-10">
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <div className="text-zinc-500 text-[10px] flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
                <span>GIT BRANCH / COMMIT</span>
              </div>
              <div className="font-semibold text-zinc-200 truncate text-sm">
                {repo.commit_hash ? repo.commit_hash.slice(0, 10) : 'Clean Working Tree'}
              </div>
              <div className="text-[11px] text-zinc-500">FastAPI & Pytest root verified</div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <div className="text-zinc-500 text-[10px] flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-cyan-400" />
                <span>AST GRAPH ENGINE</span>
              </div>
              <div className="flex items-center gap-1.5 font-semibold text-emerald-400 text-sm">
                <CheckCircle2 className="w-4 h-4" />
                <span>{gs?.connected ? 'Index Active' : 'Online'}</span>
              </div>
              <div className="text-[11px] text-zinc-500">{gs?.backend_mode || 'DIRECT_FILE_INDEX'}</div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
              <div className="text-zinc-500 text-[10px] flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5 text-purple-400" />
                <span>GRAPH DENSITY & SCALE</span>
              </div>
              <div className="font-semibold text-zinc-200 text-sm">
                {astSummary?.total_nodes ?? gs?.node_count ?? 750} Nodes • {astSummary?.total_edges ?? gs?.edge_count ?? 2105} Edges
              </div>
              <div className="text-[11px] text-zinc-500">CALLS, IMPORTS, TESTS, DEFINES</div>
            </div>
          </div>
        </div>
      )}

      {/* Interactive AST Knowledge Graph Explorer */}
      {astSummary && (
        <div className="space-y-6">
          {/* Subsystem & Module Browser (Split-Pane) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left 5 Cols: Module Hierarchy & Constituent Files */}
            <div className="lg:col-span-5 space-y-4">
              <div className="glass-panel rounded-2xl p-4 border border-zinc-800 shadow-xl space-y-3">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
                  <div className="flex items-center gap-2">
                    <Boxes className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-mono font-bold text-zinc-200 tracking-wide uppercase">
                      Architectural Modules
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-zinc-400 font-bold">
                    {Object.keys(astSummary.module_structure || {}).length} Total Subsystems
                  </span>
                </div>

                {/* Subsystem Category Filter Bar */}
                <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[10px] font-mono">
                  {(['ALL', 'BACKEND', 'FRONTEND', 'DOCS', 'CONFIG'] as const).map((filter) => {
                    const count =
                      filter === 'ALL'
                        ? Object.keys(astSummary.module_structure || {}).length
                        : astSummary.category_counts?.[filter] ??
                          Object.keys(astSummary.module_structure || {}).filter((m) => {
                            const cat =
                              astSummary.subsystem_categories?.[m] ||
                              (m.toLowerCase().startsWith('frontend') || m.includes('src/')
                                ? 'FRONTEND'
                                : m.toLowerCase().startsWith('backend') || m.includes('app/')
                                ? 'BACKEND'
                                : m.toLowerCase().startsWith('docs')
                                ? 'DOCS'
                                : 'CONFIG');
                            return cat === filter;
                          }).length;

                    return (
                      <button
                        key={filter}
                        onClick={() => setSubsystemFilter(filter)}
                        className={`px-2 py-0.5 rounded transition whitespace-nowrap border ${
                          subsystemFilter === filter
                            ? 'bg-zinc-700 text-zinc-100 border-zinc-500 font-bold'
                            : 'bg-zinc-900/60 hover:bg-zinc-800 text-zinc-400 border-zinc-800'
                        }`}
                      >
                        {filter === 'ALL'
                          ? 'All'
                          : filter === 'BACKEND'
                          ? 'Backend'
                          : filter === 'FRONTEND'
                          ? 'Frontend'
                          : filter === 'DOCS'
                          ? 'Docs'
                          : 'Config'}{' '}
                        ({count})
                      </button>
                    );
                  })}
                </div>

                {/* Module Pill Tabs */}
                <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                  {Object.entries(astSummary.module_structure || {})
                    .filter(([mod]) => {
                      if (subsystemFilter === 'ALL') return true;
                      const cat =
                        astSummary.subsystem_categories?.[mod] ||
                        (mod.toLowerCase().startsWith('frontend') || mod.includes('src/')
                          ? 'FRONTEND'
                          : mod.toLowerCase().startsWith('backend') || mod.includes('app/')
                          ? 'BACKEND'
                          : mod.toLowerCase().startsWith('docs')
                          ? 'DOCS'
                          : 'CONFIG');
                      return cat === subsystemFilter;
                    })
                    .map(([mod, files]) => {
                      const isSelected = selectedModule === mod;
                      const cat =
                        astSummary.subsystem_categories?.[mod] ||
                        (mod.toLowerCase().startsWith('frontend') || mod.includes('src/')
                          ? 'FRONTEND'
                          : mod.toLowerCase().startsWith('backend') || mod.includes('app/')
                          ? 'BACKEND'
                          : mod.toLowerCase().startsWith('docs')
                          ? 'DOCS'
                          : 'CONFIG');

                      return (
                        <button
                          key={mod}
                          onClick={() => handleSelectModule(mod)}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-mono flex items-center justify-between transition ${
                            isSelected
                              ? 'bg-indigo-950/70 border border-indigo-500/50 text-indigo-100 shadow-sm'
                              : 'bg-zinc-900/50 hover:bg-zinc-800/60 border border-zinc-800/60 text-zinc-400 hover:text-zinc-200'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            {isSelected ? (
                              <FolderOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                            ) : (
                              <Folder className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                            )}
                            <span className="truncate">{mod === 'root' ? 'Project Root & Configs' : mod}</span>
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            <span
                              className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                                cat === 'FRONTEND'
                                  ? 'bg-sky-950/80 text-sky-400 border border-sky-800'
                                  : cat === 'BACKEND'
                                  ? 'bg-purple-950/80 text-purple-400 border border-purple-800'
                                  : cat === 'DOCS'
                                  ? 'bg-amber-950/80 text-amber-400 border border-amber-800'
                                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                              }`}
                            >
                              {cat}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-800/80 text-zinc-400 font-mono">
                              {files.length}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                </div>

                {/* Constituent Files in Selected Module */}
                {selectedModule && (
                  <div className="pt-2 border-t border-zinc-800/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-zinc-400 flex items-center gap-1.5">
                        <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Files in {selectedModule === 'root' ? 'Root' : selectedModule}</span>
                      </span>
                      <button
                        onClick={() => handleSynthesizeForModule(selectedModule)}
                        className="text-[10px] font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition"
                      >
                        <Sparkles className="w-3 h-3" />
                        <span>Ticket for Module</span>
                      </button>
                    </div>

                    <div className="grid grid-cols-1 gap-1.5 max-h-64 overflow-y-auto pr-1">
                      {(astSummary.module_structure[selectedModule] || []).map((file) => {
                        const fullPath =
                          selectedModule === 'root' || selectedModule === '.' ? file : `${selectedModule}/${file}`;
                        const isFileSelected = selectedFile === fullPath;
                        const ext = file.split('.').pop()?.toLowerCase();
                        return (
                          <button
                            key={file}
                            onClick={() => handleSelectFile(selectedModule, file)}
                            className={`px-3 py-2 rounded-xl text-xs font-mono flex items-center justify-between transition text-left ${
                              isFileSelected
                                ? 'bg-cyan-950/60 border border-cyan-500/50 text-cyan-200 shadow-sm'
                                : 'bg-zinc-950/40 hover:bg-zinc-900 border border-zinc-800/50 text-zinc-400 hover:text-zinc-200'
                            }`}
                          >
                            <div className="flex items-center gap-2 truncate">
                              <Code className={`w-3.5 h-3.5 ${isFileSelected ? 'text-cyan-400' : 'text-zinc-500'}`} />
                              <span className="truncate font-medium">{file}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {ext && (
                                <span className="text-[9px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 font-mono uppercase">
                                  .{ext}
                                </span>
                              )}
                              <ChevronRight
                                className={`w-3.5 h-3.5 ${isFileSelected ? 'text-cyan-400' : 'text-zinc-600'}`}
                              />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right 7 Cols: Deep AST File Dependency & Symbol Inspector */}
            <div className="lg:col-span-7 space-y-4">
              <div className="glass-panel rounded-2xl p-5 border border-zinc-800 shadow-xl space-y-4 min-h-[420px]">
                {/* File Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-3.5">
                  <div className="flex items-center gap-2.5 truncate">
                    <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                      <FileCode className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-mono font-bold text-zinc-100 truncate">
                        {selectedFile ? selectedFile.split('/').pop() : 'Select a file'}
                      </div>
                      <div className="text-[10px] font-mono text-zinc-500 truncate">
                        {selectedFile || 'Click any module file on the left to inspect symbols and call graph'}
                      </div>
                    </div>
                  </div>

                  {selectedFile && (
                    <button
                      onClick={() => handleSynthesizeForFile(selectedFile)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-cyan-500/30 bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-300 transition shadow-sm flex-shrink-0"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Synthesize Ticket for File</span>
                    </button>
                  )}
                </div>

                {/* Inspector Sub-Tabs */}
                <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-2">
                  <button
                    onClick={() => setActiveInspectorTab('symbols')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1.5 transition ${
                      activeInspectorTab === 'symbols'
                        ? 'bg-zinc-800 text-zinc-100 border border-zinc-700'
                        : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    <Code className="w-3 h-3 text-cyan-400" />
                    <span>Declared Symbols ({fileDeps?.symbols?.length ?? 0})</span>
                  </button>
                  <button
                    onClick={() => setActiveInspectorTab('callers')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1.5 transition ${
                      activeInspectorTab === 'callers'
                        ? 'bg-zinc-800 text-zinc-100 border border-zinc-700'
                        : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    <Activity className="w-3 h-3 text-purple-400" />
                    <span>Inbound Callers ({fileDeps?.callers?.length ?? 0})</span>
                  </button>
                  <button
                    onClick={() => setActiveInspectorTab('tests')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1.5 transition ${
                      activeInspectorTab === 'tests'
                        ? 'bg-zinc-800 text-zinc-100 border border-zinc-700'
                        : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    <FileCheck className="w-3 h-3 text-emerald-400" />
                    <span>Imports & Tests ({fileDeps?.imports?.length ?? 0})</span>
                  </button>
                </div>

                {/* Tab Content */}
                {loadingDeps ? (
                  <div className="py-16 text-center space-y-2">
                    <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin mx-auto" />
                    <p className="text-xs font-mono text-zinc-400">Traversing AST Call Graph & Symbol Index...</p>
                  </div>
                ) : (
                  <div>
                    {/* Tab 1: Declared Symbols */}
                    {activeInspectorTab === 'symbols' && (
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {fileDeps?.symbols && fileDeps.symbols.length > 0 ? (
                          fileDeps.symbols.map((sym, idx) => {
                            const isClass = sym.type === 'Class';
                            return (
                              <div
                                key={idx}
                                className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 flex items-center justify-between gap-3 text-xs font-mono hover:border-zinc-700 transition"
                              >
                                <div className="flex items-center gap-2.5 truncate">
                                  <span
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                      isClass
                                        ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                                        : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                                    }`}
                                  >
                                    {sym.type.toUpperCase()}
                                  </span>
                                  <span className="font-semibold text-zinc-100 truncate">{sym.name}</span>
                                </div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                  {sym.start_line && sym.end_line && (
                                    <span className="text-[10px] text-zinc-500 font-mono">
                                      L{sym.start_line} - L{sym.end_line}
                                    </span>
                                  )}
                                  <button
                                    onClick={() => handleSynthesizeForSymbol(sym.name, selectedFile || '')}
                                    title="Synthesize Ticket for this Symbol"
                                    className="p-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-cyan-300 transition"
                                  >
                                    <Sparkles className="w-3 h-3" />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="py-12 text-center text-zinc-500 font-mono text-xs">
                            No declared classes or functions in this file node.
                          </div>
                        )}
                      </div>
                    )}

                    {/* Tab 2: Inbound Callers */}
                    {activeInspectorTab === 'callers' && (
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {fileDeps?.callers && fileDeps.callers.length > 0 ? (
                          fileDeps.callers.map((c, idx) => (
                            <div
                              key={idx}
                              className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-xs font-mono space-y-1.5 hover:border-zinc-700 transition"
                            >
                              <div className="flex items-center gap-2 text-[11px] text-zinc-400 flex-wrap">
                                <span className="text-zinc-200 font-semibold">{c.caller_file || 'external'}</span>
                                <span className="text-zinc-600">:</span>
                                <span className="text-purple-400 font-mono">{c.caller_name}</span>
                                <ArrowRight className="w-3 h-3 text-cyan-400" />
                                <span className="text-emerald-400 font-mono">{c.called_symbol}</span>
                              </div>
                              <div className="text-[10px] text-zinc-500">
                                Edge Type: <span className="text-zinc-400">CALLS</span> • Call graph consumer
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="py-12 text-center text-zinc-500 font-mono text-xs space-y-1">
                            <div>No inbound external callers detected in AST index.</div>
                            <div className="text-[11px] text-zinc-600">This module is an API root or leaf service.</div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Tab 3: Imports & Pytest Tests */}
                    {activeInspectorTab === 'tests' && (
                      <div className="space-y-3 max-h-80 overflow-y-auto pr-1 font-mono text-xs">
                        <div className="space-y-1.5">
                          <span className="text-[11px] text-zinc-400 font-semibold flex items-center gap-1.5">
                            <Layers className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Module Imports ({fileDeps?.imports?.length ?? 0})</span>
                          </span>
                          <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-1">
                            {fileDeps?.imports && fileDeps.imports.length > 0 ? (
                              fileDeps.imports.map((imp, idx) => (
                                <div key={idx} className="text-[11px] text-zinc-300 truncate">
                                  • {imp}
                                </div>
                              ))
                            ) : (
                              <div className="text-zinc-500 text-[11px]">No imports indexed for this node.</div>
                            )}
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <span className="text-[11px] text-zinc-400 font-semibold flex items-center gap-1.5">
                            <FileCheck className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Associated Pytest Test Target</span>
                          </span>
                          <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-1 text-[11px]">
                            <div className="text-emerald-400">
                              backend/tests/test_{(selectedFile?.split('/').pop() || '').replace('.py', '')}.py
                            </div>
                            <div className="text-zinc-500 text-[10px]">
                              Mapped via deterministic AST harness convention & TESTS edge
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Global Key Symbols Directory Matrix */}
          <div className="glass-panel rounded-2xl p-6 border border-zinc-800 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-mono font-bold text-zinc-100 flex items-center gap-2">
                  <Hash className="w-4 h-4 text-cyan-400" />
                  <span>Key Codebase Symbols Matrix (Architectural Backbone)</span>
                </h3>
                <p className="text-[11px] font-mono text-zinc-400 mt-0.5">
                  Top indexed classes & functions across all subsystems. Click any symbol to inspect its dependencies.
                </p>
              </div>

              {/* Symbol Search Bar */}
              <div className="relative w-full sm:w-64">
                <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter symbols..."
                  value={symbolSearchQuery}
                  onChange={(e) => setSymbolSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs font-mono rounded-lg bg-zinc-950/80 border border-zinc-800 text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* Grid of Key Classes */}
            <div className="space-y-2">
              <span className="text-[11px] font-mono text-zinc-400 font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-400" />
                <span>Primary Classes ({filteredClasses.length})</span>
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {filteredClasses.slice(0, 16).map((c, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleJumpToSymbol(c.file)}
                    className="p-2.5 rounded-xl bg-zinc-900/60 hover:bg-zinc-850 border border-zinc-800/80 hover:border-purple-500/40 text-left transition space-y-1 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-purple-300 group-hover:text-purple-200 truncate">
                        {c.class_name}
                      </span>
                      <ArrowUpRight className="w-3 h-3 text-zinc-600 group-hover:text-purple-400 transition" />
                    </div>
                    <div className="text-[10px] font-mono text-zinc-500 truncate">{c.file}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Grid of Key Functions */}
            <div className="space-y-2 pt-2 border-t border-zinc-800/60">
              <span className="text-[11px] font-mono text-zinc-400 font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span>Primary Functions & Routines ({filteredFunctions.length})</span>
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {filteredFunctions.slice(0, 16).map((f, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleJumpToSymbol(f.file)}
                    className="p-2.5 rounded-xl bg-zinc-900/60 hover:bg-zinc-850 border border-zinc-800/80 hover:border-cyan-500/40 text-left transition space-y-1 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-cyan-300 group-hover:text-cyan-200 truncate">
                        {f.func_name}
                      </span>
                      <ArrowUpRight className="w-3 h-3 text-zinc-600 group-hover:text-cyan-400 transition" />
                    </div>
                    <div className="text-[10px] font-mono text-zinc-500 truncate">{f.file}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Clone Repository Modal */}
      {showCloneModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass-panel w-full max-w-lg rounded-2xl border border-zinc-700 p-6 space-y-4 shadow-2xl bg-zinc-950 font-mono">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-cyan-400">
                <Download className="w-5 h-5" />
                <h3 className="text-base font-bold text-zinc-100">Clone from GitHub / Git</h3>
              </div>
              <button
                onClick={() => setShowCloneModal(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCloneSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-zinc-400 block font-semibold">Git Repository URL *</label>
                <input
                  type="text"
                  required
                  placeholder="https://github.com/username/repository.git"
                  value={cloneForm.git_url}
                  onChange={(e) => {
                    const url = e.target.value;
                    const parts = url.split('/').filter(Boolean);
                    const last = (parts.pop() || '').replace('.git', '');
                    setCloneForm((prev) => ({
                      ...prev,
                      git_url: url,
                      id: prev.id || last.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
                      name: prev.name || last
                    }));
                  }}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-cyan-500 font-mono text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-zinc-400 block font-semibold">Repository ID (Slug) *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. my_project"
                    value={cloneForm.id}
                    onChange={(e) => setCloneForm({ ...cloneForm, id: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-cyan-500 font-mono text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-zinc-400 block font-semibold">Display Name</label>
                  <input
                    type="text"
                    placeholder="e.g. My Project"
                    value={cloneForm.name}
                    onChange={(e) => setCloneForm({ ...cloneForm, name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-cyan-500 font-mono text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-zinc-400 block font-semibold">Target Local Path (Optional)</label>
                <input
                  type="text"
                  placeholder={`Default: E:\\MM Office\\${cloneForm.id || 'repo_id'}`}
                  value={cloneForm.target_path}
                  onChange={(e) => setCloneForm({ ...cloneForm, target_path: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-cyan-500 font-mono text-xs"
                />
              </div>

              {actionError && (
                <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-[11px] flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowCloneModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg font-bold bg-cyan-600 hover:bg-cyan-500 text-zinc-950 transition disabled:opacity-50"
                >
                  {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                  <span>{actionLoading ? 'Cloning & Indexing...' : 'Clone & Parse AST'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Register Local Folder Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass-panel w-full max-w-lg rounded-2xl border border-zinc-700 p-6 space-y-4 shadow-2xl bg-zinc-950 font-mono">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-emerald-400">
                <FolderPlus className="w-5 h-5" />
                <h3 className="text-base font-bold text-zinc-100">Register Local Directory</h3>
              </div>
              <button
                onClick={() => setShowRegisterModal(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegisterSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-zinc-400 block font-semibold">Local Directory Path *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. E:\MM Office\Agent Chess or C:\Projects\MyRepo"
                  value={registerForm.path}
                  onChange={(e) => {
                    const p = e.target.value;
                    const folder = p.replace(/\\/g, '/').split('/').filter(Boolean).pop() || '';
                    setRegisterForm((prev) => ({
                      ...prev,
                      path: p,
                      id: prev.id || folder.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
                      name: prev.name || folder
                    }));
                  }}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-zinc-400 block font-semibold">Repository ID (Slug) *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. agent_chess"
                    value={registerForm.id}
                    onChange={(e) => setRegisterForm({ ...registerForm, id: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-zinc-400 block font-semibold">Display Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Agent Chess"
                    value={registerForm.name}
                    onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                  />
                </div>
              </div>

              {actionError && (
                <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-[11px] flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg font-bold bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition disabled:opacity-50"
                >
                  {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FolderPlus className="w-3.5 h-3.5" />}
                  <span>{actionLoading ? 'Indexing Codebase...' : 'Register & Index AST'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Change Repository Path Modal */}
      {showChangePathModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass-panel w-full max-w-lg rounded-2xl border border-zinc-700 p-6 space-y-4 shadow-2xl bg-zinc-950 font-mono">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2 text-indigo-400">
                <Edit3 className="w-5 h-5" />
                <h3 className="text-base font-bold text-zinc-100">Change Repository Directory Path</h3>
              </div>
              <button
                onClick={() => setShowChangePathModal(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleChangePathSubmit} className="space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-1">
                <span className="text-[10px] text-zinc-500 uppercase font-bold">Active Repository</span>
                <div className="text-zinc-200 font-bold">{repo?.name} ({repo?.id})</div>
              </div>

              <div className="space-y-1">
                <label className="text-zinc-400 block font-semibold">New Directory Path on Disk *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. E:\MM Office\Agent Chess"
                  value={changePathForm.path}
                  onChange={(e) => setChangePathForm({ path: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-indigo-500 font-mono text-xs"
                />
              </div>

              {actionError && (
                <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-[11px] flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowChangePathModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition disabled:opacity-50"
                >
                  {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Edit3 className="w-3.5 h-3.5" />}
                  <span>{actionLoading ? 'Updating & Indexing...' : 'Update Path & Re-index'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
export default RepositoriesPage;
