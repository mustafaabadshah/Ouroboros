import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, RefreshCw, Sliders, ShieldCheck, HardDrive, Check, Bell, Lock } from 'lucide-react';
import { api } from '../services/api';
import { SystemSettings } from '../types';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedMsg, setSavedMsg] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await api.getSettings();
      setSettings(data);
    } catch (e) {
      console.error('Error loading settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;

    try {
      await api.updateSettings(settings);
      setSavedMsg('Settings saved successfully.');
      setTimeout(() => setSavedMsg(''), 3000);
    } catch (err) {
      alert(`Save failed: ${err}`);
    }
  };

  if (loading && !settings) {
    return (
      <div className="p-12 text-center text-zinc-500 font-mono text-xs space-y-2">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-zinc-600 mb-2" />
        <p>Loading system configuration...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/10 text-purple-400 border border-purple-500/30">
              PLATFORM CONFIGURATION
            </span>
            <span className="text-zinc-500 text-xs font-mono">•</span>
            <span className="text-zinc-400 text-xs font-mono">FAIL-CLOSED POLICIES</span>
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-zinc-100 flex items-center gap-2">
            System & Guardrail Settings
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Global operational boundaries, memory limits, and autonomous agent safety permissions.
          </p>
        </div>
        <button
          onClick={loadSettings}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {settings && (
        <form onSubmit={handleSave} className="space-y-6 text-xs font-mono">
          {/* General Section */}
          <div className="glass-panel rounded-2xl p-6 space-y-4 border border-zinc-800 shadow-xl">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <Sliders className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-zinc-100">GENERAL RUNTIME CONFIGURATION</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-400 mb-1.5">Application Instance Name:</label>
                <input
                  type="text"
                  value={settings.app_name}
                  onChange={(e) => setSettings({ ...settings, app_name: e.target.value })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-indigo-500 transition"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Telemetry & Logging Level:</label>
                <select
                  value={settings.log_level}
                  onChange={(e) => setSettings({ ...settings, log_level: e.target.value })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-indigo-500 transition"
                >
                  <option value="DEBUG">DEBUG (Detailed AST and Span Telemetry)</option>
                  <option value="INFO">INFO (Standard Production Events)</option>
                  <option value="WARNING">WARNING (Exceptions and Fallback Retries)</option>
                  <option value="ERROR">ERROR (Fatal Runtime Failures Only)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Directory Paths */}
          <div className="glass-panel rounded-2xl p-6 space-y-4 border border-zinc-800 shadow-xl">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <HardDrive className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-bold text-zinc-100">TARGET REPOSITORY LOCATIONS</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-zinc-400 mb-1.5">Target Repository Working Tree:</label>
                <input
                  type="text"
                  value={settings.default_repo_path}
                  onChange={(e) => setSettings({ ...settings, default_repo_path: e.target.value })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-cyan-500 transition font-mono"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Meta-Graph Codebase Index Path:</label>
                <input
                  type="text"
                  value={settings.navigator_path}
                  onChange={(e) => setSettings({ ...settings, navigator_path: e.target.value })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-cyan-500 transition font-mono"
                />
              </div>
            </div>
          </div>

          {/* Resource Guardrails */}
          <div className="glass-panel rounded-2xl p-6 space-y-4 border border-zinc-800 shadow-xl">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <Bell className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-zinc-100">HARDWARE RESOURCE GUARDRAILS (8 GB RAM HOST)</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-zinc-400 mb-1.5">Memory Warning Threshold (MB):</label>
                <input
                  type="number"
                  value={settings.memory_warning_threshold_mb}
                  onChange={(e) => setSettings({ ...settings, memory_warning_threshold_mb: Number(e.target.value) })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-amber-500 transition"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Max Self-Correction Retries:</label>
                <input
                  type="number"
                  value={settings.max_repair_attempts}
                  onChange={(e) => setSettings({ ...settings, max_repair_attempts: Number(e.target.value) })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-amber-500 transition"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1.5">Subprocess Timeout (seconds):</label>
                <input
                  type="number"
                  value={settings.subprocess_timeout_seconds}
                  onChange={(e) => setSettings({ ...settings, subprocess_timeout_seconds: Number(e.target.value) })}
                  className="w-full bg-zinc-900/90 border border-zinc-700/80 rounded-lg px-3.5 py-2 text-zinc-100 outline-none focus:border-amber-500 transition"
                />
              </div>
            </div>
          </div>

          {/* Agent Permissions & Human Gates */}
          <div className="glass-panel rounded-2xl p-6 space-y-4 border border-zinc-800 shadow-xl">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-zinc-100">FAIL-CLOSED HUMAN APPROVAL GATES</h3>
            </div>
            <div className="space-y-3">
              <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/80 cursor-pointer hover:bg-zinc-900/80 transition text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_ticket_approval}
                  onChange={(e) => setSettings({ ...settings, require_ticket_approval: e.target.checked })}
                  className="w-4 h-4 rounded bg-zinc-900 border-zinc-700 text-emerald-500 focus:ring-0"
                />
                <span>Require explicit human review before initiating autonomous run on a ticket</span>
              </label>

              <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/80 cursor-pointer hover:bg-zinc-900/80 transition text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_merge_approval}
                  onChange={(e) => setSettings({ ...settings, require_merge_approval: e.target.checked })}
                  className="w-4 h-4 rounded bg-zinc-900 border-zinc-700 text-emerald-500 focus:ring-0"
                />
                <span>Require explicit human confirmation before merging candidate worktree into main branch</span>
              </label>

              <label className="flex items-center gap-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/80 cursor-pointer hover:bg-zinc-900/80 transition text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_remote_fallback_confirmation}
                  onChange={(e) => setSettings({ ...settings, require_remote_fallback_confirmation: e.target.checked })}
                  className="w-4 h-4 rounded bg-zinc-900 border-zinc-700 text-emerald-500 focus:ring-0"
                />
                <span>Require confirmation before transmitting code snippets to remote fallback provider</span>
              </label>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-emerald-400 font-bold flex items-center gap-1.5">
              {savedMsg && <Check className="w-4 h-4" />}
              {savedMsg}
            </span>
            <button
              type="submit"
              className="flex items-center gap-2 px-6 py-2.5 font-bold rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition shadow-lg shadow-emerald-500/20"
            >
              <Save className="w-4 h-4" />
              <span>Save Guardrail Policies</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
