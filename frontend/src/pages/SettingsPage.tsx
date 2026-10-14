import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, RefreshCw } from 'lucide-react';
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
    return <div className="p-8 text-center text-zinc-500 font-mono text-xs">Loading settings...</div>;
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">System & Guardrail Settings</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Global operational boundaries, directory paths, and autonomous agent permissions.
          </p>
        </div>
        <button
          onClick={loadSettings}
          className="p-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {settings && (
        <form onSubmit={handleSave} className="space-y-6 text-xs font-mono">
          {/* General Section */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-100 border-b border-zinc-800 pb-2">GENERAL CONFIGURATION</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-400 mb-1">Application Name:</label>
                <input
                  type="text"
                  value={settings.app_name}
                  onChange={(e) => setSettings({ ...settings, app_name: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1">Log Level:</label>
                <select
                  value={settings.log_level}
                  onChange={(e) => setSettings({ ...settings, log_level: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                >
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                </select>
              </div>
            </div>
          </div>

          {/* Directory Paths */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-100 border-b border-zinc-800 pb-2">REPOSITORY PATHS</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-zinc-400 mb-1">Target Repository (ChessMind Arena):</label>
                <input
                  type="text"
                  value={settings.default_repo_path}
                  onChange={(e) => setSettings({ ...settings, default_repo_path: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1">Meta-Graph Navigator Path:</label>
                <input
                  type="text"
                  value={settings.navigator_path}
                  onChange={(e) => setSettings({ ...settings, navigator_path: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Resource Guardrails */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-100 border-b border-zinc-800 pb-2">HARDWARE RESOURCE GUARDRAILS</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-zinc-400 mb-1">Memory Warning (MB):</label>
                <input
                  type="number"
                  value={settings.memory_warning_threshold_mb}
                  onChange={(e) => setSettings({ ...settings, memory_warning_threshold_mb: Number(e.target.value) })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1">Max Repair Attempts:</label>
                <input
                  type="number"
                  value={settings.max_repair_attempts}
                  onChange={(e) => setSettings({ ...settings, max_repair_attempts: Number(e.target.value) })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
              <div>
                <label className="block text-zinc-400 mb-1">Subprocess Timeout (sec):</label>
                <input
                  type="number"
                  value={settings.subprocess_timeout_seconds}
                  onChange={(e) => setSettings({ ...settings, subprocess_timeout_seconds: Number(e.target.value) })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Agent Permissions & Human Gates */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-3">
            <h3 className="text-sm font-bold text-zinc-100 border-b border-zinc-800 pb-2">HUMAN APPROVAL GATES</h3>
            <div className="space-y-2.5">
              <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_ticket_approval}
                  onChange={(e) => setSettings({ ...settings, require_ticket_approval: e.target.checked })}
                  className="rounded bg-zinc-900 border-zinc-700 text-emerald-500"
                />
                <span>Require explicit human review before initiating autonomous run on a ticket</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_merge_approval}
                  onChange={(e) => setSettings({ ...settings, require_merge_approval: e.target.checked })}
                  className="rounded bg-zinc-900 border-zinc-700 text-emerald-500"
                />
                <span>Require explicit human confirmation before merging candidate worktree into main branch</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                <input
                  type="checkbox"
                  checked={settings.require_remote_fallback_confirmation}
                  onChange={(e) => setSettings({ ...settings, require_remote_fallback_confirmation: e.target.checked })}
                  className="rounded bg-zinc-900 border-zinc-700 text-emerald-500"
                />
                <span>Require confirmation before transmitting code snippets to remote fallback provider</span>
              </label>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-emerald-400 font-semibold">{savedMsg}</span>
            <button
              type="submit"
              className="flex items-center gap-2 px-5 py-2 font-bold rounded bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition"
            >
              <Save className="w-4 h-4" /> Save All Settings
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
