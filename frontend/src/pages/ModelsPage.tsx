import React, { useState, useEffect } from 'react';
import { Cpu, Cloud, CheckCircle2, XCircle, Key, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import { ModelStatus } from '../types';

export const ModelsPage: React.FC = () => {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  // Form states
  const [groqKeyInput, setGroqKeyInput] = useState('');
  const [selectedLocalModel, setSelectedLocalModel] = useState('qwen2.5-coder:1.5b');
  const [selectedGroqModel, setSelectedGroqModel] = useState('llama-3.3-70b-versatile');
  const [allowFallback, setAllowFallback] = useState(true);
  const [requireConfirmation, setRequireConfirmation] = useState(false);
  const [savedMessage, setSavedMessage] = useState('');

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await api.getModelStatus();
      setStatus(data);
      setSelectedLocalModel(data.default_local_model);
      setSelectedGroqModel(data.groq_reasoning_model);
      setAllowFallback(data.allow_remote_fallback);
      setRequireConfirmation(data.require_fallback_confirmation);
    } catch (e) {
      console.error('Error fetching model status:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async (provider: 'ollama' | 'groq') => {
    try {
      setTesting(true);
      setTestResult(null);
      const res = await api.testConnection(provider);
      setTestResult(res);
    } catch (e) {
      setTestResult({ success: false, message: String(e) });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateModelConfig({
        local_model_name: selectedLocalModel,
        groq_api_key: groqKeyInput.trim() || undefined,
        groq_reasoning_model: selectedGroqModel,
        allow_remote_fallback: allowFallback,
        require_fallback_confirmation: requireConfirmation,
      });
      setSavedMessage('Configuration updated securely.');
      setGroqKeyInput('');
      setTimeout(() => setSavedMessage(''), 3000);
      await loadStatus();
    } catch (err) {
      alert(`Save failed: ${err}`);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-zinc-100">Models & Inference Providers</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Hardware-aware local quantized CPU runtime controls and secure Groq API remote fallback configuration.
          </p>
        </div>
        <button
          onClick={loadStatus}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Status
        </button>
      </div>

      {status && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Local Runtime Card (Ollama) */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-zinc-300" />
                <span className="font-bold text-sm text-zinc-100">Local CPU Runtime (Ollama)</span>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${
                  status.local_available
                    ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-500'
                }`}
              >
                {status.local_available ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>

            <div className="space-y-2 text-zinc-400">
              <div className="flex justify-between">
                <span>Default Local Model:</span>
                <span className="text-zinc-200 font-bold">qwen2.5-coder:1.5b (~986 MB)</span>
              </div>
              <div className="flex justify-between">
                <span>Context Window:</span>
                <span className="text-zinc-200">2048 tokens</span>
              </div>
              <div className="flex justify-between">
                <span>Concurrency Limit:</span>
                <span className="text-zinc-200">1 active model lock</span>
              </div>
              <div className="flex justify-between">
                <span>Automatic Downloads:</span>
                <span className="text-zinc-500 font-semibold">DISABLED (Confirmation Required)</span>
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => handleTestConnection('ollama')}
                disabled={testing}
                className="w-full py-2 rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition text-xs font-semibold"
              >
                Test Ollama Connection
              </button>
            </div>
          </div>

          {/* Remote Provider Card (Groq) */}
          <div className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <Cloud className="w-5 h-5 text-emerald-400" />
                <span className="font-bold text-sm text-zinc-100">Remote Reasoning (Groq API)</span>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${
                  status.groq_available
                    ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-500'
                }`}
              >
                {status.groq_available ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>

            <div className="space-y-2 text-zinc-400">
              <div className="flex justify-between">
                <span>API Key Status:</span>
                <span className="text-zinc-200 font-bold">{status.groq_masked_key}</span>
              </div>
              <div className="flex justify-between">
                <span>Reasoning Model:</span>
                <span className="text-zinc-200">{status.groq_reasoning_model}</span>
              </div>
              <div className="flex justify-between">
                <span>Fast Coding Model:</span>
                <span className="text-zinc-200">{status.groq_fast_model}</span>
              </div>
              <div className="flex justify-between">
                <span>Remote Fallback Policy:</span>
                <span className="text-emerald-400 font-semibold">
                  {status.allow_remote_fallback ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => handleTestConnection('groq')}
                disabled={testing}
                className="w-full py-2 rounded border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition text-xs font-semibold"
              >
                Test Groq API Connection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Connection Result Toast */}
      {testResult && (
        <div
          className={`p-4 rounded border font-mono text-xs flex items-center gap-2.5 ${
            testResult.success
              ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800 text-rose-300'
          }`}
        >
          {testResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
          <span>
            [{testResult.provider?.toUpperCase()}]: {testResult.message}{' '}
            {testResult.latency_ms > 0 ? `(${testResult.latency_ms} ms)` : ''}
          </span>
        </div>
      )}

      {/* Configuration Form */}
      <form onSubmit={handleSaveConfig} className="border border-zinc-800 rounded bg-zinc-950 p-6 space-y-5 text-xs font-mono">
        <div className="border-b border-zinc-800 pb-3">
          <h3 className="text-sm font-bold text-zinc-100">SAFE MODEL CONFIGURATION</h3>
          <p className="text-zinc-400 text-[11px] mt-0.5">
            Keys entered here are securely processed backend-only and never echoed in plain text.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-zinc-400 mb-1 font-semibold">Groq API Key (Backend-Only):</label>
            <input
              type="password"
              value={groqKeyInput}
              onChange={(e) => setGroqKeyInput(e.target.value)}
              placeholder="Enter new key to update (e.g. gsk_...)"
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-zinc-400 mb-1 font-semibold">Selected Local Model:</label>
            <select
              value={selectedLocalModel}
              onChange={(e) => setSelectedLocalModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-zinc-100 outline-none"
            >
              <option value="qwen2.5-coder:1.5b">qwen2.5-coder:1.5b (~986 MB, Recommended)</option>
              <option value="qwen2.5-coder:0.5b">qwen2.5-coder:0.5b (Ultra-lightweight)</option>
              <option value="qwen2.5-coder:3b">qwen2.5-coder:3b (~1.9 GB, Heavy for 8GB RAM)</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 pt-2">
          <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
            <input
              type="checkbox"
              checked={allowFallback}
              onChange={(e) => setAllowFallback(e.target.checked)}
              className="rounded bg-zinc-900 border-zinc-700 text-emerald-500"
            />
            <span>Allow Remote Fallback to Groq when local runtime is unavailable</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
            <input
              type="checkbox"
              checked={requireConfirmation}
              onChange={(e) => setRequireConfirmation(e.target.checked)}
              className="rounded bg-zinc-900 border-zinc-700 text-emerald-500"
            />
            <span>Require confirmation before remote fallback</span>
          </label>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-zinc-800">
          <span className="text-emerald-400 font-semibold">{savedMessage}</span>
          <button
            type="submit"
            className="px-4 py-2 font-bold rounded bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition"
          >
            Save Configuration
          </button>
        </div>
      </form>
    </div>
  );
};
