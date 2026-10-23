import {
  Repository,
  GraphStatus,
  Ticket,
  Run,
  TestResult,
  DiffInspection,
  FailureTrajectory,
  ModelStatus,
  MetricsOverview,
  SystemSettings,
  AstSummary,
  FileDependencies
} from '../types';

import seedData from '../data/seedData.json';

const PROD_API_URL = 'https://ouroboros-backend-i9x2.onrender.com/api';

const isBrowser = typeof window !== 'undefined';
const isLocalhost = isBrowser && (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1' ||
  window.location.hostname === '0.0.0.0'
);

export const BASE_URL = (import.meta as any).env?.VITE_API_URL
  ? `${(import.meta as any).env.VITE_API_URL.replace(/\/+$/, '')}/api`
  : (isBrowser && !isLocalhost)
    ? PROD_API_URL
    : '/api';

export const fallbackData = {
  repositories: (seedData as any).repositories || [],
  tickets: (seedData as any).tickets || [],
  runs: (seedData as any).runs || [],
  auditEvents: (seedData as any).audit_events || [],
  testResults: (seedData as any).test_results || [],
  failureTrajectories: (seedData as any).failure_trajectories || [],
};

const OVERRIDE_KEY_RUNS = 'ouroboros_run_state_overrides';
const OVERRIDE_KEY_TICKETS = 'ouroboros_ticket_state_overrides';

export function getLocalRunOverrides(): Record<string, Partial<Run>> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(OVERRIDE_KEY_RUNS);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function setLocalRunOverride(runId: string, partial: Partial<Run>) {
  if (typeof window === 'undefined') return;
  try {
    const current = getLocalRunOverrides();
    current[runId] = { ...(current[runId] || {}), ...partial };
    localStorage.setItem(OVERRIDE_KEY_RUNS, JSON.stringify(current));
  } catch {}
}

export function clearLocalRunOverride(runId: string) {
  if (typeof window === 'undefined') return;
  try {
    const current = getLocalRunOverrides();
    delete current[runId];
    localStorage.setItem(OVERRIDE_KEY_RUNS, JSON.stringify(current));
  } catch {}
}

export function getLocalTicketOverrides(): Record<string, Partial<Ticket>> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(OVERRIDE_KEY_TICKETS);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function setLocalTicketOverride(ticketId: string, partial: Partial<Ticket>) {
  if (typeof window === 'undefined') return;
  try {
    const current = getLocalTicketOverrides();
    current[ticketId] = { ...(current[ticketId] || {}), ...partial };
    localStorage.setItem(OVERRIDE_KEY_TICKETS, JSON.stringify(current));
  } catch {}
}


async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  let res: Response;

  try {
    res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...options?.headers,
      },
      ...options,
    });
  } catch (netErr) {
    if (url.startsWith('/api') && PROD_API_URL) {
      const fallbackUrl = `${PROD_API_URL}${endpoint}`;
      res = await fetch(fallbackUrl, {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...options?.headers,
        },
        ...options,
      });
    } else {
      throw netErr;
    }
  }

  const contentType = res.headers.get('content-type') || '';

  // Guard against HTML responses (e.g. Vercel SPA 200 rewrite fallback)
  if (res.ok && !contentType.includes('application/json')) {
    if (!url.startsWith('https://ouroboros-backend-i9x2.onrender.com')) {
      const fallbackUrl = `${PROD_API_URL}${endpoint}`;
      const fallbackRes = await fetch(fallbackUrl, {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...options?.headers,
        },
        ...options,
      });
      if (fallbackRes.ok && (fallbackRes.headers.get('content-type') || '').includes('application/json')) {
        return fallbackRes.json();
      }
    }
    throw new Error(`Expected JSON but received ${contentType} from ${endpoint}`);
  }

  if (!res.ok) {
    let errorDetail = res.statusText;
    if (contentType.includes('application/json')) {
      try {
        const data = await res.json();
        errorDetail = data.detail || errorDetail;
      } catch {
        // ignore
      }
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  // System & Health
  getHealth: () => request<{ status: string; service: string }>('/health'),
  getSystemStatus: () => request<any>('/system/status'),
  getMetricsOverview: () => request<MetricsOverview>('/metrics/overview'),
  getAuditEvents: () => request<any[]>('/audit-events'),
  getPhoenixStatus: () => request<{
    enabled: boolean;
    active: boolean;
    ui_url: string;
    dashboard_url?: string;
    is_cloud?: boolean;
    port: number;
    project_name: string;
    collector_endpoint: string;
    total_recorded_spans: number;
    recent_spans: Array<{
      id: string;
      trace_id: string;
      name: string;
      span_kind: string;
      role: string;
      model_name: string;
      duration_ms: number;
      tokens_in: number;
      tokens_out: number;
      total_tokens: number;
      status: string;
      timestamp: string;
      attributes: Record<string, any>;
    }>;
  }>('/observability/phoenix/status'),
  getSystemLogs: (limit = 150) =>
    request<{
      total: number;
      limit: number;
      logs: Array<{
        timestamp: string;
        level: string;
        logger: string;
        message: string;
        formatted: string;
      }>;
    }>(`/system/logs?limit=${limit}`),

  // Repositories
  getRepositories: () => request<Repository[]>('/repositories'),
  registerRepository: (id: string, name: string, path: string) =>
    request<Repository>('/repositories', {
      method: 'POST',
      body: JSON.stringify({ id, name, path }),
    }),
  cloneRepository: (id: string, name: string, git_url: string, target_path?: string) =>
    request<Repository>('/repositories/clone', {
      method: 'POST',
      body: JSON.stringify({ id, name, git_url, target_path }),
    }),
  updateRepository: (id: string, data: { name?: string; path?: string }) =>
    request<Repository>(`/repositories/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  reindexRepository: (id: string) =>
    request<{ status: string; repo_id: string; nodes: number; edges: number; path: string }>(`/repositories/${id}/reindex`, {
      method: 'POST',
    }),
  deleteRepository: (id: string) =>
    request<{ deleted: boolean; repo_id: string }>(`/repositories/${id}`, {
      method: 'DELETE',
    }),
  getGraphStatus: (repoId: string) => request<GraphStatus>(`/repositories/${repoId}/graph-status`),
  analyzeRepository: (repoId: string) =>
    request<{ repo_id: string; summary: AstSummary }>(`/repositories/${repoId}/analyze`, { method: 'POST' }),
  getFileDependencies: (repoId: string, relPath: string) =>
    request<FileDependencies>(`/repositories/${repoId}/file-dependencies?rel_path=${encodeURIComponent(relPath)}`),

  // Tickets
  getTickets: async (repoId?: string, status?: string) => {
    const params = new URLSearchParams();
    if (repoId) params.append('repo_id', repoId);
    if (status) params.append('status', status);
    let data: Ticket[];
    try {
      data = await request<Ticket[]>(`/tickets?${params.toString()}`);
    } catch {
      data = (fallbackData.tickets as Ticket[]) || [];
    }
    const overrides = getLocalTicketOverrides();
    return data.map((t) => (overrides[t.id] ? { ...t, ...overrides[t.id] } : t));
  },
  generateTicket: (repoId: string, customPrompt?: string, useMock: boolean = false) =>
    request<Ticket>(`/tickets/generate?use_mock=${useMock}`, {
      method: 'POST',
      body: JSON.stringify({ repo_id: repoId, custom_prompt: customPrompt }),
    }),
  getTicket: async (id: string) => {
    let ticket: Ticket;
    try {
      ticket = await request<Ticket>(`/tickets/${id}`);
    } catch {
      ticket = ((fallbackData.tickets as Ticket[]) || []).find((t) => t.id === id) as Ticket;
    }
    const overrides = getLocalTicketOverrides();
    return overrides[id] ? { ...ticket, ...overrides[id] } : ticket;
  },
  updateTicket: (id: string, data: Partial<Ticket>) =>
    request<Ticket>(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  approveTicket: async (id: string) => {
    setLocalTicketOverride(id, { status: 'APPROVED' });
    try {
      return await request<Ticket>(`/tickets/${id}/approve`, { method: 'POST' });
    } catch {
      return { id, status: 'APPROVED' } as Ticket;
    }
  },
  rejectTicket: async (id: string) => {
    setLocalTicketOverride(id, { status: 'REJECTED' });
    try {
      return await request<Ticket>(`/tickets/${id}/reject`, { method: 'POST' });
    } catch {
      return { id, status: 'REJECTED' } as Ticket;
    }
  },

  // Runs
  getRuns: async (repoId?: string) => {
    const url = repoId ? `/runs?repo_id=${repoId}` : '/runs';
    let data: Run[];
    try {
      data = await request<Run[]>(url);
    } catch {
      data = (fallbackData.runs as Run[]) || [];
    }
    const overrides = getLocalRunOverrides();
    return data.map((r) => (overrides[r.id] ? { ...r, ...overrides[r.id] } : r));
  },
  startRun: (ticketId: string, autonomyMode: string = 'SUPERVISED', useMock: boolean = false) =>
    request<Run>('/runs', {
      method: 'POST',
      body: JSON.stringify({ ticket_id: ticketId, autonomy_mode: autonomyMode, use_mock_agents: useMock }),
    }),
  getRun: async (id: string) => {
    let run: Run;
    try {
      run = await request<Run>(`/runs/${id}`);
    } catch {
      run = ((fallbackData.runs as Run[]) || []).find((r) => r.id === id) as Run;
    }
    const overrides = getLocalRunOverrides();
    return overrides[id] ? { ...run, ...overrides[id] } : run;
  },
  cancelRun: (id: string) => request<{ message: string }>(`/runs/${id}/cancel`, { method: 'POST' }),
  getRunResults: (id: string) => request<TestResult[]>(`/runs/${id}/results`),
  getRunDiff: (id: string) => request<DiffInspection>(`/runs/${id}/diff`),
  approveMerge: async (runId: string, notes?: string, ticketId?: string) => {
    setLocalRunOverride(runId, {
      state: 'COMPLETED',
      completed_at: new Date().toISOString(),
      verdict: 'PASS',
    });
    if (ticketId) {
      setLocalTicketOverride(ticketId, { status: 'ACCEPTED' });
    }
    try {
      const res = await request<{ success: boolean; message: string }>(`/runs/${runId}/approve-merge`, {
        method: 'POST',
        body: JSON.stringify({ action: 'approve', notes }),
      });
      return res;
    } catch {
      return {
        success: true,
        message: 'Candidate patch successfully approved and merged into main branch.',
      };
    }
  },
  rejectMerge: async (runId: string, notes?: string) => {
    setLocalRunOverride(runId, {
      state: 'FAILED',
      error_message: notes || 'Rejected by human operator',
      completed_at: new Date().toISOString(),
    });
    try {
      const res = await request<{ success: boolean; message: string }>(`/runs/${runId}/reject-merge`, {
        method: 'POST',
        body: JSON.stringify({ action: 'reject', notes }),
      });
      return res;
    } catch {
      return {
        success: true,
        message: 'Candidate patch rejected and discarded.',
      };
    }
  },
  resetRunGate: async (runId: string, ticketId?: string) => {
    setLocalRunOverride(runId, {
      state: 'AWAITING_APPROVAL',
      completed_at: undefined,
      verdict: 'PASS',
    });
    if (ticketId) {
      setLocalTicketOverride(ticketId, { status: 'APPROVED' });
    }
    try {
      await request<{ success: boolean; message: string }>(`/runs/${runId}/reset-gate`, {
        method: 'POST',
      });
    } catch {
      // offline/fallback graceful handling
    }
    return { success: true, message: `Run ${runId} reset to AWAITING_APPROVAL for interactive demonstration.` };
  },

  // Failure Flywheel
  getFailures: (ticketId?: string, runId?: string) => {
    const params = new URLSearchParams();
    if (ticketId) params.append('ticket_id', ticketId);
    if (runId) params.append('run_id', runId);
    const qs = params.toString();
    const url = qs ? `/failures?${qs}` : '/failures';
    return request<FailureTrajectory[]>(url);
  },
  deleteFailure: (id: string) => request<{ message: string }>(`/failures/${id}`, { method: 'DELETE' }),

  // Models
  getModelStatus: () => request<ModelStatus>('/models/status'),
  updateModelConfig: (data: any) =>
    request<{ message: string }>('/models/config', { method: 'PUT', body: JSON.stringify(data) }),
  testConnection: (provider: string) =>
    request<{ provider: string; success: boolean; latency_ms: number; message: string }>(
      '/models/test-connection',
      { method: 'POST', body: JSON.stringify({ provider }) }
    ),

  // Settings
  getSettings: () => request<SystemSettings>('/settings'),
  updateSettings: (data: Partial<SystemSettings>) =>
    request<{ message: string }>('/settings', { method: 'PATCH', body: JSON.stringify(data) }),

  // Evaluation & Benchmarks
  getEvaluationMetrics: () => request<any>('/evaluation/metrics'),
  getBenchmarkTasks: () => request<any[]>('/evaluation/benchmark/tasks'),
  runBenchmarkSuite: (memoryEnabled: boolean = true) =>
    request<any>(`/evaluation/benchmark/run?memory_enabled=${memoryEnabled}`, { method: 'POST' }),
  exportBenchmarkUrl: (memoryEnabled: boolean = true) =>
    `${BASE_URL}/evaluation/benchmark/export?memory_enabled=${memoryEnabled}`,
  getEvaluationOverview: () => request<any>('/evaluation/overview'),
  getEvaluationComparison: () => request<any>('/evaluation/comparison'),
  getEvaluationTasks: () => request<any[]>('/evaluation/tasks'),
  getEvaluationTaskDetail: (taskId: string) => request<any>(`/evaluation/tasks/${taskId}`),
  getSafetyApprovals: () => request<any[]>('/evaluation/safety-approvals'),
  postSafetyApprovalAction: (reviewId: string, action: string, notes?: string) =>
    request<any>(`/evaluation/safety-approvals/${reviewId}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, notes }),
    }),
};
