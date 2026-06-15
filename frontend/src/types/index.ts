export type Project = {
  id: string;
  name: string;
  description: string;
  repository_path: string;
  coding_rules: string;
  security_rules: string;
  tech_stack: string;
  excluded_paths: string;
  created_at: string;
};

export type ProjectInput = {
  name: string;
  description: string;
  repository_path: string;
  coding_rules: string;
  security_rules: string;
  tech_stack: string;
  excluded_paths: string;
};

export type ApprovalStatus = "pending" | "approved" | "rejected" | "revisions_requested";

export type AgentResponse = {
  id: string;
  session_id: string;
  agent_name: string;
  round_name: string;
  content: string;
  rating: number | null;
  concerns: string;
  approval_status: ApprovalStatus | string;
  created_at: string;
};

export type Consensus = {
  id: string;
  session_id: string;
  summary: string;
  agreed_solution: string;
  rejected_alternatives: string;
  risks: string;
  implementation_plan: string;
  test_plan: string;
  open_questions: string;
  approval_status: ApprovalStatus | string;
  created_at: string;
};

export type FinalPrompt = {
  id: string;
  session_id: string;
  prompt_text: string;
  version: number;
  approved_by_chatgpt: boolean;
  approved_by_claude: boolean;
  approved_by_compose2: boolean;
  created_at: string;
};

export type ImplementationResult = {
  id: string;
  session_id: string;
  status: string;
  changed_files: string[] | Record<string, unknown>;
  summary: string;
  review_result: string;
  created_at: string;
};

export type CouncilSession = {
  id: string;
  project_id: string;
  title: string;
  original_user_task: string;
  normalized_task: string;
  status: string;
  current_round: string;
  created_at: string;
  updated_at: string;
  agent_responses: AgentResponse[];
  consensus: Consensus | null;
  final_prompts: FinalPrompt[];
  implementation: ImplementationResult | null;
};

export type CouncilSessionSummary = {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  status: string;
  current_round: string;
  created_at: string;
  updated_at: string;
};

export type SessionInput = {
  project_id: string;
  title: string;
  original_user_task: string;
  affected_files?: string;
  desired_outcome?: string;
  constraints?: string;
};

export type RuntimeSettings = {
  compose2_mode: "manual" | "api";
  use_mock_providers: boolean;
  mock_active: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
  compose2_configured: boolean;
};

/** Lifecycle states an agent can be in within a round (for the live UI). */
export type AgentStatus = "waiting" | "running" | "done" | "error";

/** Status of a single council round. */
export type RoundStatus = "pending" | "running" | "completed" | "error";

export type WsEvent = {
  event: string;
  agent?: string;
  round?: string;
  error?: string;
  [key: string]: unknown;
};
