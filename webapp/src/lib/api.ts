const API_BASE = '/api';

export interface SwarmStatus {
  status: 'running' | 'paused' | 'stopped';
  tasks: number;
  phase: string;
  errors: number;
  lastUpdate: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: string;
  phase: string;
  priority?: string;
  agent?: string;
  source?: string;
  created_at?: string;
  updated_at?: string;
  artifact?: string;
  branch?: string;
  pr_url?: string;
  issue_url?: string;
}

export interface TaskEvent {
  timestamp: string;
  task_id: string;
  agent: string;
  action: string;
  diff: Record<string, { old: unknown; new: unknown }>;
}

export interface PhaseHistoryEntry {
  timestamp: string;
  from?: string;
  to: string;
  agent?: string;
}

export interface MetricsSummary {
  agents: Record<string, { calls_total: number; errors_total: number; avg_duration_seconds: number }>;
  tools: Record<string, { calls_total: number; errors_total: number; avg_duration_seconds: number }>;
}

export interface MetricsCosts {
  total: number;
  byAgent: Record<string, number>;
}

export interface MetricsTokens {
  total: number;
  byAgent: Record<string, number>;
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  swarm: {
    status: () => fetchJSON<SwarmStatus>(`${API_BASE}/swarm/status`),
    health: () => fetchJSON<{ healthy: boolean; details: Record<string, unknown> }>(`${API_BASE}/swarm/health`),
    stop: () => fetchJSON<{ success: boolean; message: string }>(`${API_BASE}/swarm/stop`),
  },
  tasks: {
    list: (params?: { status?: string; phase?: string }) =>
      fetchJSON<Task[]>(`${API_BASE}/tasks?${new URLSearchParams(params || {})}`),
    get: (id: string) => fetchJSON<Task>(`${API_BASE}/tasks/${id}`),
  },
  events: {
    list: (params?: { limit?: number; offset?: number }) =>
      fetchJSON<TaskEvent[]>(`${API_BASE}/events?${new URLSearchParams(Object.fromEntries(Object.entries(params || {}).map(([k, v]) => [k, String(v)])))}`),
    streamUrl: `${API_BASE}/events/stream`,
  },
  metrics: {
    summary: () => fetchJSON<MetricsSummary>(`${API_BASE}/metrics/summary`),
    costs: () => fetchJSON<MetricsCosts>(`${API_BASE}/metrics/costs`),
    tokens: () => fetchJSON<MetricsTokens>(`${API_BASE}/metrics/tokens`),
  },
};