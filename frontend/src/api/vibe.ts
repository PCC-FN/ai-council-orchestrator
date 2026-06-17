import { api } from "./client";

export type CodingMode = "direct" | "ai_review" | "orchestra" | "autonomous";

export type CodingJobStatus =
  | "draft"
  | "analyzing"
  | "awaiting_approval"
  | "queued"
  | "preparing"
  | "running"
  | "awaiting_user_input"
  | "testing"
  | "reviewing"
  | "completed"
  | "failed"
  | "cancelled";

export interface VibeWorker {
  id: string;
  name: string;
  hostname: string;
  status: string;
  version: string;
  operating_system: string;
  capabilities: Record<string, unknown>;
  last_heartbeat_at: string | null;
  online: boolean;
  project_count: number;
}

export interface WorkerProject {
  id: string;
  worker_id: string;
  name: string;
  local_path: string;
  repository_url: string;
  default_branch: string;
  is_enabled: boolean;
  last_used_at: string | null;
}

export interface ChatMessage {
  id: string;
  job_id: string;
  sender_type: string;
  sender_name: string;
  content: string;
  message_type: string;
  created_at: string;
}

export interface FileChange {
  id: string;
  job_id: string;
  path: string;
  change_type: string;
  diff: string;
  content_after: string;
  is_approved: boolean | null;
  created_at: string;
}

export interface CodingJob {
  id: string;
  worker_id: string | null;
  project_id: string | null;
  mode: CodingMode;
  title: string;
  original_prompt: string;
  optimized_prompt: string;
  implementation_plan: Record<string, unknown>;
  status: CodingJobStatus;
  branch_name: string;
  current_step: string;
  progress_percent: number;
  review_rounds: number;
  max_review_rounds: number;
  adapter_type: string;
  started_at: string | null;
  finished_at: string | null;
  completion_report: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  file_changes: FileChange[];
}

export interface VibeJobEvent {
  id: string;
  job_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export function vibeJobSocketUrl(jobId: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/vibe/jobs/${jobId}`;
}

export function vibeGlobalSocketUrl(): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/vibe/jobs/global`;
}

export const vibeApi = {
  listWorkers: () => api<VibeWorker[]>("/vibe/workers"),
  listProjects: (workerId: string) => api<WorkerProject[]>(`/vibe/workers/${workerId}/projects`),
  createWorkerToken: (name = "Development-PC") =>
    api<{ worker_id: string; token: string }>(`/vibe/workers/register-token?name=${encodeURIComponent(name)}`, {
      method: "POST",
    }),
  listJobs: (params?: { status?: string; worker_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.worker_id) q.set("worker_id", params.worker_id);
    const qs = q.toString();
    return api<CodingJob[]>(`/coding/jobs${qs ? `?${qs}` : ""}`);
  },
  getJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}`),
  createJob: (body: {
    worker_id: string;
    project_id: string;
    prompt: string;
    mode: CodingMode;
    title?: string;
  }) =>
    api<CodingJob>("/coding/jobs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  analyzeJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/analyze`, { method: "POST" }),
  startJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/start`, { method: "POST" }),
  approveJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/approve`, { method: "POST" }),
  approveCorrection: (id: string) =>
    api<CodingJob>(`/coding/jobs/${id}/approve-correction`, { method: "POST" }),
  acceptResult: (id: string) =>
    api<CodingJob>(`/coding/jobs/${id}/accept-result`, { method: "POST" }),
  getReview: (id: string) =>
    api<{
      last_review: Record<string, unknown> | null;
      pending_correction: boolean;
      correction_prompt: string | null;
      review_rounds: number;
      max_review_rounds: number;
    }>(`/coding/jobs/${id}/review`),
  rejectJob: (id: string, reason?: string) =>
    api<CodingJob>(`/coding/jobs/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  sendMessage: (id: string, message: string) =>
    api<CodingJob>(`/coding/jobs/${id}/message`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  cancelJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/cancel`, { method: "POST" }),
  pauseJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/pause`, { method: "POST" }),
  resumeJob: (id: string) => api<CodingJob>(`/coding/jobs/${id}/resume`, { method: "POST" }),
  listEvents: (id: string) => api<VibeJobEvent[]>(`/coding/jobs/${id}/events`),
  getDiff: (id: string) => api<{ diff: string }>(`/coding/jobs/${id}/diff`),
  getTests: (id: string) =>
    api<{
      build_status: string;
      lint_status: string;
      tests: { passed: number; failed: number; skipped: number; details?: unknown[] };
    }>(`/coding/jobs/${id}/tests`),
  commitJob: (id: string, message: string) =>
    api<{ status: string; message: string }>(`/coding/jobs/${id}/commit`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  pushJob: (id: string) =>
    api<{ status: string; branch: string }>(`/coding/jobs/${id}/push`, { method: "POST" }),
  rollbackJob: (id: string) =>
    api<{ status: string }>(`/coding/jobs/${id}/rollback`, { method: "POST" }),
};
