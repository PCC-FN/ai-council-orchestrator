import { api } from "./client";
import type {
  AgentResponse,
  Consensus,
  CouncilSession,
  CouncilSessionSummary,
  FinalPrompt,
  Project,
  ProjectInput,
  RuntimeSettings,
  SessionInput,
  SettingsUpdate,
} from "../types";

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});

export const Api = {
  // Runtime / settings
  getSettings: () => api<RuntimeSettings>("/settings"),
  updateSettings: (body: SettingsUpdate) =>
    api<RuntimeSettings>("/settings", { method: "PUT", body: JSON.stringify(body) }),

  // Projects
  listProjects: () => api<Project[]>("/projects"),
  getProject: (id: string) => api<Project>(`/projects/${id}`),
  createProject: (body: ProjectInput) => api<Project>("/projects", json(body)),
  updateProject: (id: string, body: Partial<ProjectInput>) =>
    api<Project>(`/projects/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProject: (id: string) => api<void>(`/projects/${id}`, { method: "DELETE" }),

  // Sessions
  listSessions: () => api<CouncilSessionSummary[]>("/sessions"),
  getSession: (id: string) => api<CouncilSession>(`/sessions/${id}`),
  createSession: (body: SessionInput) => api<CouncilSession>("/sessions", json(body)),

  startSession: (id: string) => api<CouncilSession>(`/sessions/${id}/start`, json({})),
  advancePhase: (id: string) =>
    api<CouncilSession>(`/tasks/${id}/advance-phase`, json({})),
  runNextRound: (id: string) =>
    api<CouncilSession>(`/tasks/${id}/advance-phase`, json({})),
  approveConsensus: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/approve`, json({})),
  generateConsensus: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/generate-consensus`, json({})),

  // Agent responses
  listResponses: (id: string) => api<AgentResponse[]>(`/sessions/${id}/responses`),

  // Consensus
  getConsensus: (id: string) => api<Consensus>(`/sessions/${id}/consensus`),

  // Final prompt
  getFinalPrompt: (id: string) => api<FinalPrompt>(`/sessions/${id}/final-prompt`),
  generateFinalPrompt: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/generate-final-prompt`, json({})),
  reviewFinalPrompt: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/review-final-prompt`, json({})),
  approveFinalPrompt: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/approve-final-prompt`, json({})),

  // Compose2 / implementation
  submitToCompose2: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/submit-to-compose2`, json({})),
  markImplemented: (id: string, changed_files: string[], summary: string) =>
    api<CouncilSession>(
      `/sessions/${id}/mark-implemented`,
      json({ changed_files, summary }),
    ),
  reviewImplementation: (id: string) =>
    api<CouncilSession>(`/sessions/${id}/review-implementation`, json({})),

  // Export
  exportMarkdown: (id: string) =>
    api<{ markdown: string }>(`/sessions/${id}/export-markdown`, json({})),
  orchestrateTask: (id: string) =>
    api<CouncilSession>(`/tasks/${id}/orchestrate`, json({})),
  getOrchestraDashboard: () =>
    import("./orchestra").then((m) => m.fetchOrchestraDashboard()),
  improvementPrompt: (id: string) =>
    api<{ markdown: string }>(`/sessions/${id}/improvement-prompt`),
};
