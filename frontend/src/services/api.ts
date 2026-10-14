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
  SystemSettings
} from '../types';

const BASE_URL = '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const data = await res.json();
      errorDetail = data.detail || errorDetail;
    } catch {
      // ignore
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

  // Repositories
  getRepositories: () => request<Repository[]>('/repositories'),
  registerRepository: (id: string, name: string, path: string) =>
    request<Repository>('/repositories', {
      method: 'POST',
      body: JSON.stringify({ id, name, path }),
    }),
  getGraphStatus: (repoId: string) => request<GraphStatus>(`/repositories/${repoId}/graph-status`),
  analyzeRepository: (repoId: string) => request<any>(`/repositories/${repoId}/analyze`, { method: 'POST' }),

  // Tickets
  getTickets: (repoId?: string, status?: string) => {
    const params = new URLSearchParams();
    if (repoId) params.append('repo_id', repoId);
    if (status) params.append('status', status);
    return request<Ticket[]>(`/tickets?${params.toString()}`);
  },
  generateTicket: (repoId: string, customPrompt?: string, useMock: boolean = false) =>
    request<Ticket>(`/tickets/generate?use_mock=${useMock}`, {
      method: 'POST',
      body: JSON.stringify({ repo_id: repoId, custom_prompt: customPrompt }),
    }),
  getTicket: (id: string) => request<Ticket>(`/tickets/${id}`),
  updateTicket: (id: string, data: Partial<Ticket>) =>
    request<Ticket>(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  approveTicket: (id: string) => request<Ticket>(`/tickets/${id}/approve`, { method: 'POST' }),
  rejectTicket: (id: string) => request<Ticket>(`/tickets/${id}/reject`, { method: 'POST' }),

  // Runs
  getRuns: (repoId?: string) => {
    const url = repoId ? `/runs?repo_id=${repoId}` : '/runs';
    return request<Run[]>(url);
  },
  startRun: (ticketId: string, autonomyMode: string = 'SUPERVISED', useMock: boolean = false) =>
    request<Run>('/runs', {
      method: 'POST',
      body: JSON.stringify({ ticket_id: ticketId, autonomy_mode: autonomyMode, use_mock_agents: useMock }),
    }),
  getRun: (id: string) => request<Run>(`/runs/${id}`),
  cancelRun: (id: string) => request<{ message: string }>(`/runs/${id}/cancel`, { method: 'POST' }),
  getRunResults: (id: string) => request<TestResult[]>(`/runs/${id}/results`),
  getRunDiff: (id: string) => request<DiffInspection>(`/runs/${id}/diff`),
  approveMerge: (runId: string, notes?: string) =>
    request<{ success: boolean; message: string }>(`/runs/${runId}/approve-merge`, {
      method: 'POST',
      body: JSON.stringify({ action: 'approve', notes }),
    }),
  rejectMerge: (runId: string, notes?: string) =>
    request<{ success: boolean; message: string }>(`/runs/${runId}/reject-merge`, {
      method: 'POST',
      body: JSON.stringify({ action: 'reject', notes }),
    }),

  // Failure Flywheel
  getFailures: (ticketId?: string) => {
    const url = ticketId ? `/failures?ticket_id=${ticketId}` : '/failures';
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
};
