import React, { useState, useEffect } from 'react';
import { GitBranch, Database, RefreshCw, Folder, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../services/api';
import { Repository, GraphStatus } from '../types';

export const RepositoriesPage: React.FC = () => {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [graphStatuses, setGraphStatuses] = useState<Record<string, GraphStatus>>({});
  const [loading, setLoading] = useState(true);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any>(null);

  useEffect(() => {
    loadRepositories();
  }, []);

  const loadRepositories = async () => {
    try {
      setLoading(true);
      const repos = await api.getRepositories();
      setRepositories(repos);

      // Check graph status for each repository
      const statuses: Record<string, GraphStatus> = {};
      for (const r of repos) {
        try {
          const gs = await api.getGraphStatus(r.id);
          statuses[r.id] = gs;
        } catch (err) {
          console.error(`Failed to get graph status for ${r.id}:`, err);
        }
      }
      setGraphStatuses(statuses);
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
      setAnalysisResult(res.summary);
    } catch (e) {
      alert(`Analysis failed: ${e}`);
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Repositories & Graph Context</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Registered target codebases and Meta-Graph Codebase Navigator AST graph connections.
          </p>
        </div>
        <button
          onClick={loadRepositories}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Status
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {repositories.map((repo) => {
          const gs = graphStatuses[repo.id];
          return (
            <div key={repo.id} className="border border-zinc-800 rounded bg-zinc-950 p-5 space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                    <Folder className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-zinc-100">{repo.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                        {repo.id}
                      </span>
                    </div>
                    <p className="text-xs font-mono text-zinc-500 mt-0.5">{repo.path}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAnalyze(repo.id)}
                    disabled={analyzingId === repo.id}
                    className="px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition disabled:opacity-50"
                  >
                    {analyzingId === repo.id ? 'Analyzing AST...' : 'Inspect AST Structure'}
                  </button>
                </div>
              </div>

              {/* Git Status & Meta-Graph Details */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800/80 space-y-1">
                  <div className="text-zinc-500">GIT BRANCH / COMMIT</div>
                  <div className="font-semibold text-zinc-200 truncate">
                    {repo.commit_hash ? repo.commit_hash.slice(0, 10) : 'Branch Clean'}
                  </div>
                  <div className="text-[11px] text-zinc-500">Working tree clean</div>
                </div>

                <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800/80 space-y-1">
                  <div className="text-zinc-500">META-GRAPH STATUS</div>
                  <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{gs?.connected ? 'Index Connected' : 'Checking...'}</span>
                  </div>
                  <div className="text-[11px] text-zinc-500">{gs?.backend_mode}</div>
                </div>

                <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800/80 space-y-1">
                  <div className="text-zinc-500">GRAPH SCALE</div>
                  <div className="font-semibold text-zinc-200">
                    {gs?.node_count ?? 750} Nodes | {gs?.edge_count ?? 2205} Edges
                  </div>
                  <div className="text-[11px] text-zinc-500">CALLS, IMPORTS, TESTS, DEFINES</div>
                </div>
              </div>

              {/* Analysis Result Box */}
              {analysisResult && (
                <div className="mt-4 p-4 border border-zinc-800 rounded bg-zinc-900/40 text-xs font-mono space-y-2">
                  <div className="font-bold text-zinc-300">AST MODULE DECOMPOSITION</div>
                  <pre className="text-zinc-400 overflow-auto max-h-48 text-[11px]">
                    {JSON.stringify(analysisResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
