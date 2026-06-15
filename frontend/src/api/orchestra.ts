import { api } from "./client";

export type AgentDefinition = {
  id: string;
  key: string;
  display_name: string;
  provider: string;
  model: string;
  role: string;
  temperature: number;
  priority: number;
  active: boolean;
};

export type WorkerRegistration = {
  id: string;
  name: string;
  worker_type: string;
  hostname: string;
  status: string;
  capabilities: Record<string, unknown>;
  current_job_id: string | null;
  last_heartbeat_at: string | null;
  registered_at: string;
};

export type OrchestraJob = {
  id: string;
  task_id: string;
  project_id: string;
  worker_id: string | null;
  job_type: string;
  branch: string;
  description: string;
  status: string;
  progress_message: string;
  created_at: string;
};

export type OrchestraEvent = {
  id: string;
  event_type: string;
  task_id: string | null;
  project_id: string | null;
  worker_id: string | null;
  job_id: string | null;
  agent_key: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type PhaseDefinition = {
  key: string;
  number: number;
  label: string;
  description: string;
};

export type PhaseExecution = {
  id: string;
  task_id: string;
  phase_key: string;
  phase_number: number;
  status: string;
  summary: string;
  started_at: string | null;
  completed_at: string | null;
};

export type OrchestraDashboard = {
  product: string;
  active_tasks: number;
  completed_tasks: number;
  active_workers: number;
  pending_jobs: number;
  running_jobs: number;
  recent_events: OrchestraEvent[];
  agents: AgentDefinition[];
  workers: WorkerRegistration[];
};

export async function fetchOrchestraDashboard(): Promise<OrchestraDashboard> {
  return api<OrchestraDashboard>("/orchestra/dashboard");
}

export async function fetchPhases(): Promise<PhaseDefinition[]> {
  return api<PhaseDefinition[]>("/orchestra/phases");
}

export async function fetchOrchestraEvents(limit = 50): Promise<OrchestraEvent[]> {
  return api<OrchestraEvent[]>(`/orchestra/events?limit=${limit}`);
}

export async function fetchOrchestraJobs(taskId?: string): Promise<OrchestraJob[]> {
  const q = taskId ? `?task_id=${taskId}` : "";
  return api<OrchestraJob[]>(`/orchestra/jobs${q}`);
}

export async function fetchTaskPhases(taskId: string): Promise<PhaseExecution[]> {
  return api<PhaseExecution[]>(`/tasks/${taskId}/phases`);
}

export async function orchestrateTask(taskId: string) {
  return api(`/tasks/${taskId}/orchestrate`, { method: "POST", body: "{}" });
}
