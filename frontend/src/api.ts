const BASE = "/api";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`${r.status}: ${t}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export type Project = {
  id: string;
  name: string;
  description: string;
  repository_path: string;
  coding_rules: string;
  security_rules: string;
  created_at: string;
};

export type Session = {
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

export type AgentResponse = {
  id: string;
  agent_name: string;
  round_name: string;
  content: string;
  rating: number | null;
  concerns: string;
  approval_status: string;
  created_at: string;
};

export type Consensus = {
  summary: string;
  agreed_solution: string;
  risks: string;
  implementation_plan: string;
  test_plan: string;
  open_questions: string;
  approval_status: string;
};

export type FinalPrompt = {
  id: string;
  prompt_text: string;
  version: number;
  approved_by_chatgpt: boolean;
  approved_by_claude: boolean;
  approved_by_compose2: boolean;
};

export type ImplementationResult = {
  status: string;
  changed_files: string[] | Record<string, unknown>;
  summary: string;
  review_result: string;
};
