export interface AgentAvailability {
  available: boolean;
  adapterType: string;
  message: string;
}

export interface CodingTask {
  jobId: string;
  sessionId: string;
  projectPath: string;
  projectName: string;
  branchName: string;
  prompt: string;
}

export interface AgentSession {
  sessionId: string;
  jobId: string;
}

export type AgentEventType =
  | "agent.started"
  | "agent.message"
  | "agent.question"
  | "agent.output"
  | "agent.error"
  | "file.created"
  | "file.changed"
  | "git.diff.updated"
  | "command.started"
  | "command.output"
  | "command.completed"
  | "test.started"
  | "test.completed"
  | "job.completed"
  | "job.failed";

export interface AgentEvent {
  type: AgentEventType;
  payload: Record<string, unknown>;
}

export interface CodingAgentAdapter {
  checkAvailability(): Promise<AgentAvailability>;
  startTask(task: CodingTask): Promise<AgentSession>;
  sendMessage(sessionId: string, message: string): Promise<void>;
  streamEvents(sessionId: string): AsyncIterable<AgentEvent>;
  cancelTask(sessionId: string): Promise<void>;
  resumeTask(sessionId: string): Promise<void>;
}

export type EventEmitter = (event: AgentEvent & { jobId: string; sessionId: string }) => void;
